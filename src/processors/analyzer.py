from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from src.config import AppConfig, load_app_config
from src.models import CandidateNews, DailyDigest, SourceStatistics
from src.processors.event_clusterer import EventCluster
from src.processors.prompts import (
    build_digest_system_prompt,
    build_digest_user_prompt,
    build_digest_user_prompt_from_clusters,
    extract_json_text,
)
from src.processors.digest_quality import enforce_digest_quality_policy


def _extract_json_core(text: str) -> str:
    raw = (text or '').strip()
    if not raw:
        return raw
    start_obj = raw.find('{')
    start_arr = raw.find('[')
    starts = [x for x in [start_obj, start_arr] if x != -1]
    if not starts:
        return raw
    start = min(starts)
    end_obj = raw.rfind('}')
    end_arr = raw.rfind(']')
    end = max(end_obj, end_arr)
    if end == -1 or end <= start:
        return raw[start:]
    return raw[start : end + 1]


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r',\s*([}\]])', r'\1', text)


def local_repair_json_text(text: str) -> str:
    fixed = (text or '')
    # Remove BOM and other invisible chars that often break parsing.
    fixed = fixed.replace('\ufeff', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    fixed = fixed.replace('\xa0', ' ')
    fixed = fixed.strip()
    fixed = extract_json_text(fixed)
    fixed = _extract_json_core(fixed)

    # Normalize Chinese quotes and smart quotes.
    fixed = fixed.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")

    # Quote missing leading quote before key: links": -> "links":
    fixed = re.sub(
        r'(?m)^(\s*)([A-Za-z_][A-Za-z0-9_]*)"\s*:',
        lambda m: f'{m.group(1)}"{m.group(2)}":',
        fixed,
    )

    # Quote unquoted keys: links: -> "links":
    fixed = re.sub(
        r'([{\[,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:',
        lambda m: f'{m.group(1)}"{m.group(2)}":',
        fixed,
    )
    fixed = re.sub(
        r'(?m)^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:',
        lambda m: f'{m.group(1)}"{m.group(2)}":',
        fixed,
    )

    # Single-quoted key/value pairs to JSON-style double quotes.
    fixed = re.sub(r"(?m)'([A-Za-z_][A-Za-z0-9_]*)'\s*:", r'"\1":', fixed)
    fixed = re.sub(r':\s*\'([^\'\\]*(?:\\.[^\'\\]*)*)\'', r': "\1"', fixed)

    fixed = _remove_trailing_commas(fixed)
    return fixed


def parse_llm_json_safely(json_text: str, config: AppConfig | None = None) -> dict:
    digest_date = date.today().isoformat()
    debug_dir = Path('data/digested')
    debug_dir.mkdir(parents=True, exist_ok=True)

    cleaned = local_repair_json_text(json_text)

    try:
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError('Parsed JSON is not an object.')
        return payload
    except Exception as exc:
        failed_path = debug_dir / f'{digest_date}_llm_json_parse_failed.txt'
        failed_path.write_text(json_text or '', encoding='utf-8')
        local_repaired_path = debug_dir / f'{digest_date}_llm_local_repaired_text.txt'
        local_repaired_path.write_text(cleaned or '', encoding='utf-8')
        print(f'[analyzer] json parse failed, raw json text saved: {failed_path}')
        print(f'[analyzer] parse error: {exc}')

        try:
            from json_repair import repair_json

            repaired = repair_json(cleaned or json_text or '')
            repaired_core = local_repair_json_text(repaired)
            payload = json.loads(repaired_core)
            if not isinstance(payload, dict):
                raise ValueError('Repaired JSON is not an object.')

            repaired_path = debug_dir / f'{digest_date}_llm_repaired_response.json'
            repaired_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            return payload
        except Exception:
            pass

        # Optional LLM repair layer with safe fallback.
        cfg = config or load_app_config()
        if cfg.llm_repair_enabled:
            try:
                from src.processors.llm_client import LLMClient
                from src.processors.prompts import build_json_repair_prompts

                client = LLMClient(config=cfg)
                repair_system, repair_user = build_json_repair_prompts(cleaned or json_text or '')
                repaired_text = client.chat_json(repair_system, repair_user, stage='repair')
                repair_raw_path = debug_dir / f'{digest_date}_llm_repair_raw_response.txt'
                repair_raw_path.write_text(repaired_text or '', encoding='utf-8')
                repaired_core = local_repair_json_text(repaired_text)
                payload = json.loads(repaired_core)
                if not isinstance(payload, dict):
                    raise ValueError('LLM repaired JSON is not an object.')
                repaired_path = debug_dir / f'{digest_date}_llm_repaired_response.json'
                repaired_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
                return payload
            except Exception as repair_exc:
                raise RuntimeError(
                    f'Failed to parse LLM JSON even after repair. '
                    f'Please inspect: {failed_path}, {local_repaired_path}'
                ) from repair_exc

        raise RuntimeError(
            f'Failed to parse LLM JSON. Please inspect: {failed_path}, {local_repaired_path}'
        )


def normalize_digest_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload

    if 'source_statistics' not in payload or not isinstance(payload.get('source_statistics'), dict):
        payload['source_statistics'] = {
            'total_candidates': 0,
            'cleaned_candidates': 0,
            'dedup_candidates': 0,
            'selected_items': 0,
            'source_count': 0,
            'international_count': 0,
            'chinese_count': 0,
            'raw_candidates': 0,
            'cluster_input_candidates': 0,
            'event_clusters': 0,
            'final_llm_events': 0,
            'appendix_items': 0,
            'raw_research_candidates': 0,
            'cleaned_research_candidates': 0,
            'research_event_clusters': 0,
            'selected_research_count': 0,
            'appendix_research_count': 0,
            'research_quota_met': False,
        }

    def _clean_appendix_text(value: str) -> str:
        text = str(value or '').strip()
        bad_phrases = [
            '降级至附录', '属于职业焦虑类内容', '属于泛业务实践内容', '属于泛技术实践内容', '属于泛生活内容',
            '属于泛商业新闻', '属于弱相关内容', '与AI主题无关', '与AI无关', '避免重复', '仅AI部分相关',
            '其余降级至附录', 'low value', 'noise', 'penalty', 'downgrade', 'dropped', 'debug',
        ]
        lowered = text.lower()
        for phrase in bad_phrases:
            if phrase.lower() in lowered:
                text = re.sub(re.escape(phrase), '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    appendix = payload.get('appendix')
    if not isinstance(appendix, list):
        payload['appendix'] = []
    else:
        normalized_appendix: list[dict[str, str]] = []
        for item in appendix:
            if not isinstance(item, dict):
                continue
            title = str(item.get('title') or 'Untitled appendix item').strip() or 'Untitled appendix item'

            link_value = item.get('link') or item.get('url')
            if not link_value:
                links_value = item.get('links')
                if isinstance(links_value, list) and links_value:
                    link_value = links_value[0]
                elif isinstance(links_value, str):
                    link_value = links_value
            link = str(link_value or '').strip()

            source_value = item.get('source') or item.get('source_name')
            if not source_value:
                source_names_value = item.get('source_names')
                if isinstance(source_names_value, list) and source_names_value:
                    source_value = ', '.join(str(x).strip() for x in source_names_value if str(x).strip())
                elif isinstance(source_names_value, str):
                    source_value = source_names_value
            source = str(source_value or '').strip()

            brief_value = item.get('brief_summary') or item.get('summary') or item.get('description') or item.get('snippet') or ''
            brief_summary = _clean_appendix_text(brief_value)
            if not brief_summary:
                brief_summary = '该条目提供了与 AI 生态相关的补充背景信息。'

            normalized_appendix.append(
                {'title': title, 'link': link, 'source': source, 'brief_summary': brief_summary}
            )
        payload['appendix'] = normalized_appendix

    main_digest = payload.get('main_digest')
    if not isinstance(main_digest, list):
        payload['main_digest'] = []
        return payload

    if all(isinstance(group, dict) and 'category_name' in group and 'items' in group for group in main_digest):
        return payload

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in main_digest:
        if not isinstance(item, dict):
            continue
        category = str(item.get('category_name') or item.get('category') or '其他').strip() or '其他'

        links = item.get('links')
        if isinstance(links, str):
            links = [links]
        elif not isinstance(links, list):
            links = []

        tags = item.get('tags')
        if isinstance(tags, str):
            tags = [tags]
        elif not isinstance(tags, list):
            tags = []

        source_names = item.get('source_names')
        if isinstance(source_names, str):
            source_names = [source_names]
        elif not isinstance(source_names, list):
            source_names = []

        cleaned_item = {
            'title': str(item.get('title', '')).strip(),
            'links': [str(x).strip() for x in links if str(x).strip()],
            'tags': [str(x).strip() for x in tags if str(x).strip()],
            'summary': str(item.get('summary', '')).strip(),
            'why_it_matters': str(item.get('why_it_matters', '')).strip(),
            'insights': str(item.get('insights', '')).strip(),
            'source_names': [str(x).strip() for x in source_names if str(x).strip()],
        }

        if not cleaned_item['links'] and item.get('link'):
            cleaned_item['links'] = [str(item.get('link')).strip()]

        grouped.setdefault(category, []).append(cleaned_item)

    payload['main_digest'] = [{'category_name': c, 'items': items} for c, items in grouped.items()] if grouped else []
    return payload


def finalize_digest_statistics(
    digest: DailyDigest,
    *,
    raw_candidates: int | None = None,
    cleaned_candidates: int | None = None,
    cluster_input_candidates: int | None = None,
    event_clusters: int | None = None,
    final_llm_events: int | None = None,
) -> DailyDigest:
    actual_selected_items = sum(len(group.items) for group in digest.main_digest)
    appendix_items = len(digest.appendix)

    stats = digest.source_statistics if digest.source_statistics is not None else SourceStatistics()

    if raw_candidates is not None:
        stats.raw_candidates = raw_candidates
    if cleaned_candidates is not None:
        stats.cleaned_candidates = cleaned_candidates
    if cluster_input_candidates is not None:
        stats.cluster_input_candidates = cluster_input_candidates
    if event_clusters is not None:
        stats.event_clusters = event_clusters
    if final_llm_events is not None:
        stats.final_llm_events = final_llm_events

    if stats.total_candidates == 0 and raw_candidates is not None:
        stats.total_candidates = raw_candidates

    stats.selected_items = actual_selected_items
    stats.appendix_items = appendix_items

    digest.source_statistics = stats
    return digest


def _maybe_preprocess_clusters_with_llm(clusters: list[EventCluster], config: AppConfig) -> list[EventCluster]:
    if not config.llm_preprocess_enabled or not clusters:
        return clusters

    from src.processors.llm_client import LLMClient

    try:
        client = LLMClient(config=config)
        payload = [
            {
                'event_id': c.event_id,
                'title': c.representative_title,
                'importance_score': c.importance_score,
                'topic_relevance_score': c.topic_relevance_score,
                'evidence_count': c.evidence_count,
                'source_types': c.source_types,
            }
            for c in clusters[:80]
        ]
        system_prompt = '你是事件筛选助手。输出严格 JSON。只返回 {"scores": [{"event_id":"...","score":0-1}]}。'
        user_prompt = f'请给事件打分，越值得进入主日报分数越高：{json.dumps(payload, ensure_ascii=False)}'
        raw = client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, stage='preprocess')
        parsed = parse_llm_json_safely(extract_json_text(raw))
        scores_raw = parsed.get('scores', [])
        score_map: dict[str, float] = {}
        if isinstance(scores_raw, list):
            for item in scores_raw:
                if not isinstance(item, dict):
                    continue
                event_id = str(item.get('event_id', '')).strip()
                if not event_id:
                    continue
                try:
                    score = float(item.get('score', 0.0))
                except Exception:
                    score = 0.0
                score_map[event_id] = max(0.0, min(1.0, score))

        for c in clusters:
            if c.event_id in score_map:
                c.importance_score = round(0.7 * c.importance_score + 0.3 * score_map[c.event_id], 4)
        return sorted(clusters, key=lambda x: (x.importance_score, x.evidence_count), reverse=True)
    except Exception as exc:
        print(f'[analyzer] preprocess layer failed, fallback to deterministic ranking: {exc}')
        return clusters


def analyze_candidates_with_llm(
    candidates: list[CandidateNews],
    config: AppConfig | None = None,
    topic_override: str | None = None,
    event_clusters: list[EventCluster] | None = None,
    stats_context: dict[str, int] | None = None,
) -> DailyDigest:
    from src.processors.llm_client import LLMClient

    cfg = config or load_app_config()
    digest_date = date.today().isoformat()
    topic = (topic_override or cfg.digest_topic or 'AI').strip() or 'AI'

    inferred_stats = {
        'raw_candidates': len(candidates),
        'cleaned_candidates': len(candidates),
        'cluster_input_candidates': len(candidates),
        'event_clusters': len(event_clusters or []),
        'final_llm_events': len(event_clusters or candidates),
        'source_count': len({c.source_name for c in candidates}),
        'international_count': sum(1 for c in candidates if c.region.lower() == 'international'),
        'chinese_count': sum(1 for c in candidates if c.region.lower() in {'chinese', 'china', 'zh'}),
    }
    merged_stats = dict(inferred_stats)
    if stats_context:
        merged_stats.update(stats_context)

    clusters = event_clusters or []
    if cfg.llm_pipeline_mode == 'layered' and clusters:
        clusters = _maybe_preprocess_clusters_with_llm(clusters, cfg)

    system_prompt = build_digest_system_prompt()
    if cfg.llm_pipeline_mode == 'layered' and clusters:
        user_prompt = build_digest_user_prompt_from_clusters(
            clusters=clusters,
            topic=topic,
            date=digest_date,
            min_items=cfg.main_digest_min_items,
            max_items=cfg.main_digest_max_items,
            appendix_max_items=cfg.appendix_max_items,
            stats_context=merged_stats,
        )
    else:
        user_prompt = build_digest_user_prompt(
            candidates=candidates,
            topic=topic,
            date=digest_date,
            min_items=cfg.main_digest_min_items,
            max_items=cfg.main_digest_max_items,
            appendix_max_items=cfg.appendix_max_items,
            stats_context=merged_stats,
        )

    client = LLMClient(config=cfg)
    raw_response = client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, stage='final')
    merged_stats['final_model_used'] = client.last_final_model_used
    merged_stats['final_fallback_used'] = client.last_final_fallback_used
    merged_stats['final_fallback_reason'] = client.last_final_fallback_reason

    try:
        json_text = extract_json_text(raw_response)
        payload = parse_llm_json_safely(json_text, config=cfg)
        payload = normalize_digest_payload(payload)
        payload['topic'] = topic
        if hasattr(DailyDigest, 'model_validate'):
            digest = DailyDigest.model_validate(payload)
        else:
            digest = DailyDigest(**payload)
        digest, quality_metrics = enforce_digest_quality_policy(digest=digest, cfg=cfg, candidates=candidates)
        digest = finalize_digest_statistics(
            digest,
            raw_candidates=merged_stats.get('raw_candidates'),
            cleaned_candidates=merged_stats.get('cleaned_candidates'),
            cluster_input_candidates=merged_stats.get('cluster_input_candidates'),
            event_clusters=merged_stats.get('event_clusters'),
            final_llm_events=merged_stats.get('final_llm_events'),
        )
        digest.source_statistics.source_count = merged_stats.get('source_count', digest.source_statistics.source_count)
        digest.source_statistics.international_count = merged_stats.get(
            'international_count', digest.source_statistics.international_count
        )
        digest.source_statistics.chinese_count = merged_stats.get('chinese_count', digest.source_statistics.chinese_count)
        digest.source_statistics.selected_international_count = quality_metrics.get('selected_international_count')
        digest.source_statistics.selected_chinese_count = quality_metrics.get('selected_chinese_count')
        digest.source_statistics.appendix_count = quality_metrics.get('appendix_count')
        digest.source_statistics.dropped_low_value_count = quality_metrics.get('dropped_low_value_count')
        digest.source_statistics.duplicate_removed_from_appendix_count = quality_metrics.get(
            'duplicate_removed_from_appendix_count'
        )
        digest.source_statistics.raw_research_candidates = merged_stats.get('raw_research_candidates')
        digest.source_statistics.cleaned_research_candidates = merged_stats.get('cleaned_research_candidates')
        digest.source_statistics.research_event_clusters = merged_stats.get('research_event_clusters')
        digest.source_statistics.dedup_candidates = merged_stats.get('dedup_candidates')
        digest.source_statistics.selected_research_count = quality_metrics.get('selected_research_count')
        digest.source_statistics.appendix_research_count = quality_metrics.get('appendix_research_count')
        digest.source_statistics.research_quota_met = quality_metrics.get('research_quota_met')
        digest.source_statistics.research_shortage_reason = quality_metrics.get('research_shortage_reason')
        digest.source_statistics.shortage_reason = quality_metrics.get('shortage_reason')
        digest.source_statistics.ratio_fallback_reason = quality_metrics.get('ratio_fallback_reason')
        digest.source_statistics.appendix_shortage_reason = quality_metrics.get('appendix_shortage_reason')
        digest.source_statistics.arxiv_status = merged_stats.get('arxiv_status')
        digest.source_statistics.semantic_scholar_status = merged_stats.get('semantic_scholar_status')
        digest.source_statistics.total_source_count = digest.source_statistics.source_count
        digest.source_statistics.final_model_used = merged_stats.get('final_model_used')
        digest.source_statistics.final_fallback_used = merged_stats.get('final_fallback_used')
        digest.source_statistics.final_fallback_reason = merged_stats.get('final_fallback_reason')
        return digest
    except Exception as exc:
        debug_dir = Path('data/digested')
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f'{digest_date}_llm_raw_response.txt'
        debug_path.write_text(raw_response, encoding='utf-8')
        raise RuntimeError(f'Failed to parse/validate LLM digest JSON. Raw response saved to: {debug_path}') from exc


def save_digest(digest: DailyDigest, output_dir: str = 'data/digested') -> Path:
    digest = finalize_digest_statistics(digest)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{digest.date}_digest.json'
    out_path = out_dir / filename
    if hasattr(digest, 'model_dump'):
        payload = digest.model_dump(mode='json')
    else:
        payload = digest.dict()
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return out_path
