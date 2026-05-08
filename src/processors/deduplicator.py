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

# Balance research with news/industry/dev trends.
_SOURCE_PRIORITY = {
    'hn_algolia': 4,
    'rss': 4,
    'official_blog': 4,
    'ai_media': 4,
    'github_trending': 3,
    'rss_or_web': 3,
    'arxiv': 2,
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


def rank_candidates_lightweight(candidates: list[CandidateNews]) -> list[CandidateNews]:
    def _score(item: CandidateNews) -> tuple[int, int, int]:
        has_time = 1 if item.published_at else 0
        source_score = _SOURCE_PRIORITY.get(item.source_type, 1)
        text = f"{item.title} {item.summary_or_snippet or ''}".lower()
        keyword_score = sum(1 for kw in _KEYWORDS if kw in text)
        return (has_time, source_score, keyword_score)

    return sorted(candidates, key=_score, reverse=True)


def trim_candidates(candidates: list[CandidateNews], max_candidates: int) -> list[CandidateNews]:
    if max_candidates <= 0:
        return []
    return candidates[:max_candidates]


def prepare_llm_candidates(candidates: list[CandidateNews], lookback_hours: int, max_candidates: int) -> list[CandidateNews]:
    cleaned = clean_candidates(candidates, lookback_hours=lookback_hours)
    deduped = deduplicate_by_url(cleaned)
    ranked = rank_candidates_lightweight(deduped)

    policy = load_digest_policy()
    quotas = policy.get('candidate_quotas', DEFAULT_SOURCE_QUOTAS)
    if not isinstance(quotas, dict):
        quotas = DEFAULT_SOURCE_QUOTAS

    balanced = balance_candidates_by_source_type(ranked, max_candidates=max_candidates, quotas=quotas)
    return trim_candidates(balanced, max_candidates=max_candidates)
