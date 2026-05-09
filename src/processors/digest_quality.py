from __future__ import annotations

import difflib
import html
import re
from urllib.parse import urlsplit

from src.config import AppConfig
from src.models import AppendixItem, CandidateNews, CategoryGroup, DailyDigest, DigestNewsItem

ALLOWED_CATEGORIES = [
    '技术与模型进展',
    '论文与科研进展',
    'Agent 与 AI 工具',
    '开源生态与开发者趋势',
    '产业与公司动态',
    '算力、芯片与基础设施',
    '政策、安全与治理',
]

AI_STRONG_KEYWORDS = (
    'ai', 'llm', 'agent', 'rag', 'model', 'openai', 'anthropic', 'gemini', 'claude', 'deepseek', 'qwen',
    'mistral', 'vllm', 'langchain', 'llamaindex', 'benchmark', 'arxiv',
    '大模型', '智能体', '机器学习', '推理', '多模态', '芯片', '算力', '安全',
)

HARD_REJECT_PATTERNS = (
    'runway', 'airport accident', 'hiv', 'aids', 'ipo filing', 'car review', 'celebrity',
    'ufo', 'discord tui', 'terminal music', 'jane street', 'saas loading time', 'ipv6 proxy',
    'dirtyfrag', 'ipcomp', 'xfrm', 'solar radiation', 'heat flux', '9点1氪', '9am 1kr',
    '机场', '跑道', '事故', '艾滋', '援助削减', '汽车评测', '娱乐八卦',
)

LOW_VALUE_KEYWORDS = (
    '情绪价值', '焦虑', '陪伴', '恋爱', '生活方式', '营销', '软文', 'lifestyle', 'anxiety',
)

INTERNAL_POLICY_PATTERNS = (
    '降级至附录',
    '属于弱相关内容',
    '与ai无关',
    '与AI无关',
    '避免重复',
    'debug',
    'dropped',
    'filtered',
)


def _normalize_text(value: str | None) -> str:
    return re.sub(r'\s+', ' ', (value or '').strip())


def _normalize_title(title: str) -> str:
    return _normalize_text(title).lower()


def _is_hard_reject_text(text: str) -> bool:
    lowered = (text or '').lower()
    return any(p.lower() in lowered for p in HARD_REJECT_PATTERNS)


def _is_strong_ai_related_text(text: str) -> bool:
    lowered = (text or '').lower()
    return any(k in lowered for k in AI_STRONG_KEYWORDS)


def _is_low_value(item: DigestNewsItem) -> bool:
    text = f"{item.title} {item.summary} {item.why_it_matters} {item.insights}".lower()
    return any(k in text for k in LOW_VALUE_KEYWORDS)


def _topic_keywords(topic: str) -> tuple[str, ...]:
    tl = (topic or '').lower()
    keys = {x.strip() for x in re.split(r'[,/]+', tl) if x.strip()}
    if any(x in tl for x in ['reasoning', 'long context', 'memory', 'rag', 'tool use', 'workflow', 'agent']):
        keys.update(
            {
                'reasoning', 'long context', 'long-context', 'memory', 'agent memory', 'persistent memory',
                'working memory', 'rag', 'retrieval', 'tool use', 'planning', 'context compression',
                'workflow agents', 'source attribution', 'citation faithfulness', 'document processing',
            }
        )
    return tuple(k for k in keys if k)


def _topic_relevance(item: DigestNewsItem, topic: str) -> float:
    keys = _topic_keywords(topic)
    if not keys:
        return 0.0
    text = f"{item.title} {item.summary} {item.why_it_matters} {item.insights} {' '.join(item.tags)}".lower()
    hits = sum(1 for k in keys if k in text)
    return hits / max(1, min(12, len(keys)))


def _clean_reader_text(text: str | None) -> str:
    cleaned = _normalize_text(text)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = html.unescape(cleaned)
    lowered = cleaned.lower()
    for p in INTERNAL_POLICY_PATTERNS:
        if p.lower() in lowered:
            cleaned = re.sub(re.escape(p), '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(query|author|points|num_comments)\s*=\s*[^;\s,]+', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_text(cleaned)
    if len(cleaned) > 300:
        cleaned = cleaned[:300].rstrip() + '...'
    return _normalize_text(cleaned)


def _guess_category(item: DigestNewsItem) -> str:
    text = f"{item.title} {item.summary} {' '.join(item.tags)}".lower()
    if any(k in text for k in ['paper', 'arxiv', 'doi', 'benchmark', 'method', '论文']):
        return '论文与科研进展'
    if any(k in text for k in ['gpu', 'chip', '算力', '数据中心', '基础设施', 'cloud']):
        return '算力、芯片与基础设施'
    if any(k in text for k in ['agent', 'memory', 'tool use', 'workflow', 'mcp', 'claude code']):
        return 'Agent 与 AI 工具'
    if any(k in text for k in ['open source', 'github', '开源']):
        return '开源生态与开发者趋势'
    if any(k in text for k in ['policy', 'regulation', '治理', '安全']):
        return '政策、安全与治理'
    if any(k in text for k in ['model', 'reasoning', 'long context', 'context compression', '推理']):
        return '技术与模型进展'
    return '产业与公司动态'


def _is_research_item(category_name: str, item: DigestNewsItem) -> bool:
    if category_name == '论文与科研进展':
        return True
    text = f"{item.title} {item.summary} {' '.join(item.tags)} {' '.join(item.source_names)} {' '.join(item.links)}".lower()
    return any(
        k in text
        for k in (
            'arxiv.org',
            'arxiv',
            'paper',
            'doi',
            'semantic scholar',
            'papers with code',
            'benchmark',
            'method',
            'research',
            'reasoning',
            'long context',
            'memory',
            'rag',
            'evaluation',
            'moe',
            'rl',
        )
    )


def _infer_region(item: DigestNewsItem, source_region_map: dict[str, str]) -> str:
    for s in item.source_names:
        region = source_region_map.get(s.lower())
        if region in {'chinese', 'china', 'zh'}:
            return 'chinese'
    for u in item.links:
        host = urlsplit(u).netloc.lower()
        if host.endswith('.cn') or '.com.cn' in host:
            return 'chinese'
    return 'international'


def _score_item(item: DigestNewsItem, category_name: str, topic: str) -> float:
    score = 0.0
    if _is_strong_ai_related_text(f"{item.title} {item.summary} {' '.join(item.tags)}"):
        score += 2.0
    score += min(2.0, len(item.links) * 0.3)
    score += min(2.0, len(item.source_names) * 0.4)
    score += 2.5 * _topic_relevance(item, topic)
    if _is_research_item(category_name, item):
        score += 1.5
    if len(item.summary or '') >= 40:
        score += 0.8
    if _is_low_value(item):
        score -= 3.0
    if _is_hard_reject_text(f"{item.title} {item.summary}"):
        score -= 10.0
    return score


def _to_appendix_item(item: DigestNewsItem) -> AppendixItem:
    link = item.links[0] if item.links else ''
    source = ', '.join(item.source_names) if item.source_names else ''
    brief = _clean_reader_text(item.summary) or _clean_reader_text(item.why_it_matters) or _clean_reader_text(item.insights)
    if not brief:
        brief = '该条目提供与主题相关的补充信息。'
    return AppendixItem(title=item.title or 'Untitled', link=link, source=source, brief_summary=brief)


def _candidate_to_appendix_item(candidate: CandidateNews) -> AppendixItem:
    title = _normalize_text(candidate.title) or 'Untitled'
    link = _normalize_text(candidate.url)
    source = _normalize_text(candidate.source_name)
    brief = _clean_reader_text(candidate.summary_or_snippet or candidate.content_text or '')
    if not brief:
        brief = ''
    return AppendixItem(title=title, link=link, source=source, brief_summary=brief)


def _candidate_to_research_digest_item(candidate: CandidateNews) -> DigestNewsItem:
    summary = _clean_reader_text(candidate.summary_or_snippet or candidate.content_text or '')
    if not summary:
        summary = '该研究条目与主题相关，建议查看原文获取方法与评测细节。'
    return DigestNewsItem(
        title=_normalize_text(candidate.title) or 'Untitled',
        links=[_normalize_text(candidate.url)] if _normalize_text(candidate.url) else [],
        tags=[x for x in (candidate.tags_hint or []) if x][:4] or ['research'],
        summary=summary,
        why_it_matters='该条目提供与主题相关的研究证据或评测信息。',
        insights='建议结合方法设定与评测指标判断其实际可迁移性。',
        source_names=[_normalize_text(candidate.source_name)] if _normalize_text(candidate.source_name) else [],
    )


def _similar_title(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio() >= 0.97


def _is_appendix_relevant(item: AppendixItem, topic: str) -> bool:
    text = f"{item.title} {item.brief_summary} {item.source}".strip()
    if not text or _is_hard_reject_text(text):
        return False
    if not _is_strong_ai_related_text(text):
        return False
    topic_norm = (topic or '').strip().lower()
    if topic_norm in {'ai', 'artificial intelligence', '人工智能'}:
        return True
    topic_item = DigestNewsItem(title=item.title, links=[item.link] if item.link else [], tags=[], summary=item.brief_summary, why_it_matters='', insights='', source_names=[item.source] if item.source else [])
    return _topic_relevance(topic_item, topic) >= 0.04


def enforce_digest_quality_policy(digest: DailyDigest, cfg: AppConfig, candidates: list[CandidateNews]) -> tuple[DailyDigest, dict[str, int | bool | str]]:
    source_region_map = {(c.source_name or '').lower(): (c.region or '').lower() for c in candidates}

    main_target = max(10, min(15, int(cfg.main_digest_max_items or 12)))
    main_min = max(10, int(cfg.main_digest_min_items or 10))
    append_limit = max(1, int(cfg.appendix_max_items or 10))
    append_min = max(0, int(getattr(cfg, 'appendix_min_items', 5) or 5))
    append_target = max(append_min, min(append_limit, int(getattr(cfg, 'appendix_target_items', 8) or 8)))

    rows: list[tuple[str, DigestNewsItem, str, float]] = []
    dropped_low_value_count = 0
    for group in digest.main_digest:
        for item in group.items:
            cat = group.category_name if group.category_name in ALLOWED_CATEGORIES else _guess_category(item)
            if _is_hard_reject_text(f"{item.title} {item.summary}"):
                dropped_low_value_count += 1
                continue
            if _is_low_value(item):
                dropped_low_value_count += 1
                continue
            region = _infer_region(item, source_region_map)
            score = _score_item(item, cat, digest.topic or cfg.digest_topic)
            rows.append((cat, item, region, score))

    rows.sort(key=lambda x: x[3], reverse=True)

    # Initial pick by score.
    selected = rows[:main_target]

    # Research quota enforcement.
    research_min_cfg = int(getattr(cfg, 'research_min_main_items', 3) or 3)
    research_target = 3 if main_target >= 13 else 2
    research_min = min(research_min_cfg, research_target)
    research_pool = [r for r in rows if _is_research_item(r[0], r[1])]
    selected_research = [r for r in selected if _is_research_item(r[0], r[1])]
    research_shortage_reason = ''
    if len(selected_research) < research_min and research_pool:
        need = research_min - len(selected_research)
        selected_non_research = [r for r in selected if not _is_research_item(r[0], r[1])]
        replacements = [r for r in research_pool if all(id(r[1]) != id(s[1]) for s in selected)][:need]
        if replacements and selected_non_research:
            selected_non_research.sort(key=lambda x: x[3])
            remove_ids = {id(x[1]) for x in selected_non_research[:len(replacements)]}
            selected = [r for r in selected if id(r[1]) not in remove_ids] + replacements
    if len(research_pool) < research_min:
        research_shortage_reason = f'insufficient_research_candidates:{len(research_pool)}<{research_min}'

    # If LLM main digest lacks research, backfill from raw candidates pool.
    selected_ids = {id(r[1]) for r in selected}
    selected_research_now = [r for r in selected if _is_research_item(r[0], r[1])]
    if len(selected_research_now) < research_min and candidates:
        need = research_min - len(selected_research_now)
        candidate_research_items: list[tuple[str, DigestNewsItem, str, float]] = []
        for c in candidates:
            url = (c.url or '').lower()
            text = f"{c.title} {c.summary_or_snippet or ''} {c.source_name}".lower()
            is_research_like = (
                c.source_type in {'arxiv', 'semantic_scholar', 'crossref', 'papers_with_code'}
                or 'arxiv.org' in url
                or any(
                    k in text
                    for k in ('paper', 'benchmark', 'method', 'reasoning', 'long context', 'memory', 'rag', 'evaluation', 'moe', 'rl')
                )
            )
            if not is_research_like:
                continue
            di = _candidate_to_research_digest_item(c)
            cat = '论文与科研进展'
            region = _infer_region(di, source_region_map)
            score = _score_item(di, cat, digest.topic or cfg.digest_topic) + 0.5
            candidate_research_items.append((cat, di, region, score))

        candidate_research_items.sort(key=lambda x: x[3], reverse=True)
        replacements = [x for x in candidate_research_items if all(x[1].title != s[1].title for s in selected)]
        if replacements and need > 0:
            selected_non_research = [r for r in selected if not _is_research_item(r[0], r[1])]
            selected_non_research.sort(key=lambda x: x[3])
            remove_count = min(need, len(selected_non_research), len(replacements))
            remove_ids = {id(x[1]) for x in selected_non_research[:remove_count]}
            selected = [r for r in selected if id(r[1]) not in remove_ids]
            selected.extend(replacements[:remove_count])

    # Region ratio preference (no emptying).
    target_cn = max(0, round(main_target * float(getattr(cfg, 'target_chinese_ratio', 0.3))))
    cn_items = [r for r in selected if r[2] == 'chinese']
    intl_items = [r for r in selected if r[2] != 'chinese']
    demoted_for_appendix: list[DigestNewsItem] = []
    if len(cn_items) > target_cn and len(intl_items) >= main_min - target_cn:
        cn_keep = cn_items[:target_cn]
        cn_drop = cn_items[target_cn:]
        demoted_for_appendix.extend([x[1] for x in cn_drop])
        selected = intl_items + cn_keep

    # Backfill to main_min.
    selected_ids = {id(r[1]) for r in selected}
    backfill_pool = [r for r in rows if id(r[1]) not in selected_ids and r[3] > -2.0]
    for r in backfill_pool:
        if len(selected) >= main_min:
            break
        selected.append(r)
        selected_ids.add(id(r[1]))

    selected = sorted(selected, key=lambda x: x[3], reverse=True)[:main_target]

    # Build groups.
    buckets: dict[str, list[DigestNewsItem]] = {c: [] for c in ALLOWED_CATEGORIES}
    for cat, item, _region, _score in selected:
        use_cat = cat if cat in buckets else _guess_category(item)
        buckets[use_cat].append(item)
    main_groups = [CategoryGroup(category_name=c, items=arr) for c, arr in buckets.items() if arr]

    # Collect main stats.
    main_urls: set[str] = set()
    main_titles: list[str] = []
    selected_international_count = 0
    selected_chinese_count = 0
    selected_research_count = 0
    for group in main_groups:
        for item in group.items:
            main_titles.append(item.title)
            main_urls.update([u for u in item.links if u])
            if _infer_region(item, source_region_map) == 'chinese':
                selected_chinese_count += 1
            else:
                selected_international_count += 1
            if _is_research_item(group.category_name, item):
                selected_research_count += 1

    # Appendix.
    appendix_pool: list[AppendixItem] = [
        AppendixItem(
            title=_normalize_text(a.title),
            link=_normalize_text(a.link),
            source=_normalize_text(a.source),
            brief_summary=_clean_reader_text(a.brief_summary),
        )
        for a in digest.appendix
    ]
    appendix_pool.extend(_to_appendix_item(x[1]) for x in rows if id(x[1]) not in {id(s[1]) for s in selected})
    appendix_pool.extend(_to_appendix_item(x) for x in demoted_for_appendix)

    deduped_appendix: list[AppendixItem] = []
    seen_urls: set[str] = set()
    duplicate_removed_from_appendix_count = 0
    for ap in appendix_pool:
        title = (ap.title or '').strip()
        url = (ap.link or '').strip()
        if not title:
            duplicate_removed_from_appendix_count += 1
            continue
        if url and (url in main_urls or url in seen_urls):
            duplicate_removed_from_appendix_count += 1
            continue
        if any(_similar_title(title, t) for t in main_titles):
            duplicate_removed_from_appendix_count += 1
            continue
        if any(_similar_title(title, x.title) for x in deduped_appendix):
            duplicate_removed_from_appendix_count += 1
            continue
        if not _is_appendix_relevant(ap, digest.topic or cfg.digest_topic):
            duplicate_removed_from_appendix_count += 1
            continue
        if url:
            seen_urls.add(url)
        deduped_appendix.append(ap)
        if len(deduped_appendix) >= append_target:
            break

    # Backfill appendix from candidates when LLM appendix is too sparse.
    if len(deduped_appendix) < append_min and candidates:
        selected_main_urls = set(main_urls)
        selected_main_titles = {t.lower().strip() for t in main_titles}
        for c in candidates:
            if len(deduped_appendix) >= append_target:
                break
            ap = _candidate_to_appendix_item(c)
            title = (ap.title or '').strip()
            url = (ap.link or '').strip()
            if not title:
                continue
            if url and (url in selected_main_urls or url in seen_urls):
                continue
            if title.lower().strip() in selected_main_titles:
                continue
            if any(_similar_title(title, t) for t in main_titles):
                continue
            if any(_similar_title(title, x.title) for x in deduped_appendix):
                continue
            if not _is_appendix_relevant(ap, digest.topic or cfg.digest_topic):
                continue
            if url:
                seen_urls.add(url)
            deduped_appendix.append(ap)

    appendix_shortage_reason = ''
    if len(deduped_appendix) < append_min:
        appendix_shortage_reason = f'insufficient_high_quality_appendix_candidates:{len(deduped_appendix)}<{append_min}'

    appendix_research_count = sum(1 for ap in deduped_appendix if any(k in f"{ap.title} {ap.brief_summary} {ap.source}".lower() for k in ('paper', 'arxiv', 'doi', 'research', 'benchmark')))

    digest.main_digest = main_groups
    digest.appendix = deduped_appendix

    metrics = {
        'selected_international_count': selected_international_count,
        'selected_chinese_count': selected_chinese_count,
        'appendix_count': len(deduped_appendix),
        'dropped_low_value_count': dropped_low_value_count,
        'duplicate_removed_from_appendix_count': duplicate_removed_from_appendix_count,
        'selected_research_count': selected_research_count,
        'appendix_research_count': appendix_research_count,
        'research_quota_met': (selected_research_count >= research_min) if research_pool else False,
        'research_shortage_reason': research_shortage_reason,
        'appendix_shortage_reason': appendix_shortage_reason,
        'shortage_reason': '' if sum(len(g.items) for g in main_groups) >= main_min else f'main_digest_insufficient:{sum(len(g.items) for g in main_groups)}<{main_min}',
        'ratio_fallback_reason': '' if selected_international_count >= selected_chinese_count else 'international_insufficient_used_chinese_backfill',
    }
    return digest, metrics
