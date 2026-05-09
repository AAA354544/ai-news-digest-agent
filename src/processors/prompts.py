from __future__ import annotations

import json
from typing import Any

from src.config import load_digest_policy
from src.models import CandidateNews
from src.processors.event_clusterer import EventCluster


def _clip_text(value: str | None, max_chars: int = 220) -> str:
    text = (value or '').strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '...'


def _preferred_categories() -> list[str]:
    policy = load_digest_policy()
    categories = policy.get('main_digest_policy', {}).get('preferred_categories', [])
    if isinstance(categories, list) and categories:
        return [str(x) for x in categories]
    return [
        '技术与模型进展',
        '科研与论文前沿',
        'Agent 与 AI 工具',
        '产业与公司动态',
        '开源生态与开发者趋势',
        '算力、芯片与基础设施',
        '安全、政策与监管',
        '其他',
    ]


def _skeleton(categories: list[str]) -> dict[str, Any]:
    return {
        'date': 'YYYY-MM-DD',
        'topic': 'AI',
        'main_digest': [{'category_name': c, 'items': []} for c in categories],
        'appendix': [],
        'source_statistics': {
            'total_candidates': 0,
            'cleaned_candidates': 0,
            'selected_items': 0,
            'source_count': 0,
            'international_count': 0,
            'chinese_count': 0,
            'raw_candidates': 0,
            'cluster_input_candidates': 0,
            'event_clusters': 0,
            'final_llm_events': 0,
            'appendix_items': 0,
        },
    }


def build_digest_system_prompt() -> str:
    return (
        '你是专业 AI 情报编辑、技术分析师、产业观察员。'
        '定位是“AI 科研最新进展 + AI 技术/产业风向日报”。'
        '只基于输入内容分析，不得编造外部事实。'
        '优先按“事件”组织信息：同一事件的多来源必须尽量合并为一条。'
        '输出必须是 RFC 8259 标准 JSON；所有 key 和字符串必须双引号。'
        '不要 Markdown，不要代码块，不要 JSON 外解释文字，不要尾随逗号。'
        'main_digest 必须是 category group 结构，不能是扁平列表。'
        '每个 digest item 必须包含 title, links, tags, summary, why_it_matters, insights, source_names。'
        'links 必须来自输入链接。'
        'appendix 每条必须是 {title, link, source, brief_summary}。'
        '不要使用 appendix 的 url/links/source_name/source_names/summary 字段名。'
        'appendix 不能与 main_digest 重复链接。'
        '正文不应被单一来源主导；HN 不应主导；论文类原则上不超过约 40%。'
        'source_statistics.selected_items 必须等于 main_digest 实际条目总数。'
    )


def build_digest_user_prompt(
    candidates: list[CandidateNews],
    topic: str,
    date: str,
    min_items: int,
    max_items: int,
    appendix_max_items: int,
    stats_context: dict[str, int] | None = None,
) -> str:
    packed: list[dict[str, Any]] = []
    for item in candidates:
        packed.append(
            {
                'id': item.id,
                'title': item.title,
                'url': item.url,
                'source_name': item.source_name,
                'source_type': item.source_type,
                'region': item.region,
                'language': item.language,
                'published_at': str(item.published_at) if item.published_at is not None else None,
                'summary_or_snippet': _clip_text(item.summary_or_snippet, max_chars=200),
            }
        )

    categories = _preferred_categories()
    skeleton = _skeleton(categories)

    return (
        f'date: {date}\n'
        f'topic: {topic}\n'
        f'candidate_count: {len(candidates)}\n'
        f'main_digest_item_range: {min_items}-{max_items}\n'
        f'appendix_max_items: {appendix_max_items}\n'
        f'stats_context: {json.dumps(stats_context or {}, ensure_ascii=False)}\n\n'
        '当前输入是候选新闻列表。请尽量识别同一事件并合并，不要重复写同一事件。\n'
        '正文精选规则：\n'
        '- N>=15 时精选 10-12 条；\n'
        '- 8<=N<=14 时精选 6-8 条；\n'
        '- N<8 时最多 N 条。\n'
        'appendix 保留未进正文但有价值的候选，最多 appendix_max_items 条。\n'
        '返回严格 JSON，不要任何额外文本。\n'
        f'分类建议：{categories}\n'
        f'JSON 骨架：\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n'
        f'candidates:\n{json.dumps(packed, ensure_ascii=False)}'
    )


def build_digest_user_prompt_from_clusters(
    clusters: list[EventCluster],
    topic: str,
    date: str,
    min_items: int,
    max_items: int,
    appendix_max_items: int,
    stats_context: dict[str, int] | None = None,
) -> str:
    packed: list[dict[str, Any]] = []
    for cluster in clusters:
        evidence_snippets: list[str] = []
        for source in cluster.sources[:4]:
            evidence_snippets.append(_clip_text(source.summary_or_snippet, max_chars=180))

        packed.append(
            {
                'event_id': cluster.event_id,
                'representative_title': cluster.representative_title,
                'category_hint': cluster.category_hint,
                'importance_score': cluster.importance_score,
                'topic_relevance_score': cluster.topic_relevance_score,
                'region_hint': cluster.region_hint,
                'evidence_count': cluster.evidence_count,
                'source_names': cluster.source_names,
                'source_types': cluster.source_types,
                'links': cluster.links,
                'evidence_snippets': evidence_snippets,
            }
        )

    categories = _preferred_categories()
    skeleton = _skeleton(categories)

    return (
        f'date: {date}\n'
        f'topic: {topic}\n'
        f'event_cluster_count: {len(clusters)}\n'
        f'main_digest_item_range: {min_items}-{max_items}\n'
        f'appendix_max_items: {appendix_max_items}\n'
        f'stats_context: {json.dumps(stats_context or {}, ensure_ascii=False)}\n\n'
        '当前输入已经是事件聚类（同一事件多来源已初步聚合）。\n'
        '请按事件写日报，不要把同一事件拆成多条。\n'
        '每条正文可包含多个 links 和多个 source_names。\n'
        'summary 写事件事实；why_it_matters 写重要性；insights 写趋势判断和启示。\n'
        '附录保留未入正文但值得关注的事件，不要重复正文链接。\n'
        '返回严格 JSON，不要任何额外文本。\n'
        f'分类建议：{categories}\n'
        f'JSON 骨架：\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n'
        f'event_clusters:\n{json.dumps(packed, ensure_ascii=False)}'
    )


def extract_json_text(response_text: str) -> str:
    text = (response_text or '').strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        while lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        return '\n'.join(lines).strip()
    return text
