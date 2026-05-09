from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.config import load_digest_policy
from src.models import CandidateNews
from src.processors.balancer import DEFAULT_SOURCE_QUOTAS, balance_candidates_by_source_type
from src.processors.cleaner import clean_candidates

_TRACKING_PARAMS = {
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'utm_term',
    'utm_content',
    'fbclid',
    'gclid',
}

_SOURCE_PRIORITY = {
    'rss': 5,
    'hn_algolia': 4,
    'github_trending': 4,
    'arxiv': 4,
    'rss_or_web': 3,
}

_KEYWORDS = (
    'ai',
    'llm',
    'agent',
    'rag',
    'model',
    'openai',
    'deepmind',
    'gemini',
    'claude',
    '机器学习',
    '大模型',
    '智能体',
)

_RESEARCH_HINTS = (
    'arxiv',
    'paper',
    'research',
    'benchmark',
    'doi',
    'semantic scholar',
    'crossref',
    'agent memory',
    'tool use',
    'workflow',
    'planning',
    'rag',
)


def _is_research_candidate(item: CandidateNews) -> bool:
    if item.source_type in {'arxiv', 'semantic_scholar', 'crossref', 'papers_with_code'}:
        return True
    category = (item.category_hint or '').lower()
    if category in {'academic_paper', 'research'}:
        return True
    text = f"{item.title} {item.summary_or_snippet or ''}".lower()
    return any(k in text for k in _RESEARCH_HINTS)


def normalize_url(url: str) -> str:
    raw = (url or '').strip()
    if not raw:
        return ''
    parts = urlsplit(raw)
    scheme = parts.scheme.lower() if parts.scheme else ''
    netloc = parts.netloc.lower()
    filtered_pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS]
    query = urlencode(filtered_pairs, doseq=True)
    return urlunsplit((scheme, netloc, parts.path, query, ''))


def deduplicate_by_url(candidates: list[CandidateNews]) -> list[CandidateNews]:
    seen: set[str] = set()
    deduped: list[CandidateNews] = []
    for candidate in candidates:
        norm = normalize_url(candidate.url)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        deduped.append(candidate.model_copy(update={'url': norm}))
    return deduped


def rank_candidates_lightweight(candidates: list[CandidateNews], topic: str | None = None) -> list[CandidateNews]:
    topic_tokens = [x.lower() for x in (topic or '').split() if x.strip()]

    def _score(item: CandidateNews) -> tuple[int, int, int, int]:
        has_time = 1 if item.published_at else 0
        source_score = _SOURCE_PRIORITY.get(item.source_type, 1)
        text = f"{item.title} {item.summary_or_snippet or ''}".lower()
        keyword_score = sum(1 for kw in _KEYWORDS if kw in text)
        topic_score = sum(1 for tk in topic_tokens if tk in text)
        return (topic_score, has_time, source_score, keyword_score)

    return sorted(candidates, key=_score, reverse=True)


def trim_candidates(candidates: list[CandidateNews], max_candidates: int) -> list[CandidateNews]:
    if max_candidates <= 0:
        return []
    return candidates[:max_candidates]


def prepare_llm_candidates(
    candidates: list[CandidateNews],
    lookback_hours: int,
    max_candidates: int,
    topic: str | None = None,
    allow_overflow: bool = True,
) -> list[CandidateNews]:
    cleaned = clean_candidates(candidates, lookback_hours=lookback_hours)
    deduped = deduplicate_by_url(cleaned)
    ranked = rank_candidates_lightweight(deduped, topic=topic)

    policy = load_digest_policy()
    quotas = policy.get('candidate_quotas', DEFAULT_SOURCE_QUOTAS)
    if not isinstance(quotas, dict):
        quotas = DEFAULT_SOURCE_QUOTAS

    balanced = balance_candidates_by_source_type(
        ranked,
        max_candidates=max_candidates,
        quotas=quotas,
        allow_overflow=allow_overflow,
    )

    # Keep a minimum research slice before final trim.
    research_min = min(max_candidates, max(3, round(max_candidates * 0.25), 8 if max_candidates >= 30 else 3))
    research_min = min(research_min, 12)
    research_items = [x for x in balanced if _is_research_candidate(x)]
    non_research_items = [x for x in balanced if not _is_research_candidate(x)]

    selected: list[CandidateNews] = []
    selected.extend(research_items[:research_min])
    for item in non_research_items:
        if len(selected) >= max_candidates:
            break
        selected.append(item)
    if len(selected) < max_candidates:
        for item in research_items[research_min:]:
            if len(selected) >= max_candidates:
                break
            selected.append(item)

    return trim_candidates(selected, max_candidates=max_candidates)
