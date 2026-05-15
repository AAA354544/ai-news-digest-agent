from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.config import load_digest_policy
from src.models import CandidateNews
from src.processors.balancer import DEFAULT_SOURCE_QUOTAS, balance_candidates_by_source_type
from src.processors.candidate_scorer import is_probable_ai_github_project, score_candidate
from src.processors.cleaner import clean_candidates, parse_candidate_datetime

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

_TITLE_SUFFIX_PATTERNS = (
    r"\s+[-|]\s+hacker\s+news\s*$",
    r"\s+[-|]\s+techcrunch\s*$",
    r"\s+[-|]\s+the\s+verge\s*$",
    r"\s+[-|]\s+venturebeat\s*$",
    r"\s+[-|]\s+mit\s+technology\s+review\s*$",
    r"\s+[-|]\s+openai\s*$",
)

_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
}

_LAST_SELECTION_REPORT: dict[str, object] = {}


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


def normalize_title(title: str) -> str:
    raw = (title or "").strip().lower()
    if not raw:
        return ""
    for pattern in _TITLE_SUFFIX_PATTERNS:
        raw = re.sub(pattern, "", raw)
    raw = re.sub(r"https?://\S+", " ", raw)
    raw = re.sub(r"[^\w\u4e00-\u9fff]+", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _title_tokens(title: str) -> set[str]:
    normalized = normalize_title(title)
    return {
        token
        for token in normalized.split()
        if len(token) > 1 and token not in _TITLE_STOPWORDS
    }


def _title_similarity(left: CandidateNews, right: CandidateNews) -> float:
    left_norm = normalize_title(left.title)
    right_norm = normalize_title(right.title)
    if not left_norm or not right_norm:
        return 0.0

    left_tokens = _title_tokens(left.title)
    right_tokens = _title_tokens(right.title)
    jaccard = 0.0
    if left_tokens and right_tokens:
        jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    return max(jaccard, sequence)


def _similarity_threshold(left: CandidateNews, right: CandidateNews) -> float:
    protected_types = {"arxiv", "github_trending"}
    if left.source_type in protected_types or right.source_type in protected_types:
        return 0.96
    return 0.86


def _is_title_duplicate(left: CandidateNews, right: CandidateNews) -> bool:
    similarity = _title_similarity(left, right)
    if similarity < _similarity_threshold(left, right):
        return False

    protected_types = {"arxiv", "github_trending"}
    if left.source_type in protected_types or right.source_type in protected_types:
        # Be deliberately conservative for paper titles and repo names.
        return normalize_title(left.title) == normalize_title(right.title)
    return True


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


def deduplicate_by_title(candidates: list[CandidateNews]) -> tuple[list[CandidateNews], list[dict[str, object]]]:
    kept: list[CandidateNews] = []
    kept_scores: list[float] = []
    dropped_samples: list[dict[str, object]] = []

    for candidate in candidates:
        candidate_score = score_candidate(candidate).score
        duplicate_index = None
        duplicate_similarity = 0.0
        for idx, existing in enumerate(kept):
            similarity = _title_similarity(candidate, existing)
            if similarity >= _similarity_threshold(candidate, existing) and _is_title_duplicate(candidate, existing):
                duplicate_index = idx
                duplicate_similarity = similarity
                break

        if duplicate_index is None:
            kept.append(candidate)
            kept_scores.append(candidate_score)
            continue

        existing = kept[duplicate_index]
        existing_score = kept_scores[duplicate_index]
        if candidate_score > existing_score:
            kept[duplicate_index] = candidate
            kept_scores[duplicate_index] = candidate_score
            dropped = existing
            kept_item = candidate
            dropped_score = existing_score
            kept_score = candidate_score
        else:
            dropped = candidate
            kept_item = existing
            dropped_score = candidate_score
            kept_score = existing_score

        if len(dropped_samples) < 20:
            dropped_samples.append(
                {
                    "dropped_title": dropped.title,
                    "dropped_source": dropped.source_name,
                    "dropped_source_type": dropped.source_type,
                    "dropped_score": round(dropped_score, 4),
                    "kept_title": kept_item.title,
                    "kept_source": kept_item.source_name,
                    "kept_source_type": kept_item.source_type,
                    "kept_score": round(kept_score, 4),
                    "similarity": round(duplicate_similarity, 4),
                }
            )

    return kept, dropped_samples


def rank_candidates_lightweight(candidates: list[CandidateNews]) -> list[CandidateNews]:
    def _score(item: CandidateNews) -> tuple[float, int, int, str]:
        quality = score_candidate(item).score
        source_score = _SOURCE_PRIORITY.get(item.source_type, 1)
        text = f"{item.title} {item.summary_or_snippet or ''}".lower()
        keyword_score = sum(1 for kw in _KEYWORDS if kw in text)
        return (quality, source_score, keyword_score, item.title)

    return sorted(candidates, key=_score, reverse=True)


def trim_candidates(candidates: list[CandidateNews], max_candidates: int) -> list[CandidateNews]:
    if max_candidates <= 0:
        return []
    return candidates[:max_candidates]


def _source_distribution(candidates: list[CandidateNews]) -> dict[str, int]:
    return dict(sorted(Counter(item.source_type or "unknown" for item in candidates).items()))


def _filter_github_ai_false_positives(candidates: list[CandidateNews]) -> tuple[list[CandidateNews], int]:
    filtered: list[CandidateNews] = []
    dropped = 0
    for item in candidates:
        if item.source_type == "github_trending" and not is_probable_ai_github_project(
            item.title,
            item.summary_or_snippet or "",
        ):
            dropped += 1
            continue
        filtered.append(item)
    return filtered, dropped


def _has_published_at(item: CandidateNews) -> bool:
    return parse_candidate_datetime(item.published_at) is not None


def _limit_no_date_candidates(
    selected: list[CandidateNews],
    ranked: list[CandidateNews],
    max_candidates: int,
) -> list[CandidateNews]:
    no_date_cap = max(2, round(max_candidates * 0.18))
    final: list[CandidateNews] = []
    selected_ids: set[str] = set()
    no_date_count = 0

    for item in selected:
        has_date = _has_published_at(item)
        if not has_date and no_date_count >= no_date_cap:
            continue
        final.append(item)
        selected_ids.add(item.id)
        if not has_date:
            no_date_count += 1
        if len(final) >= max_candidates:
            return final[:max_candidates]

    for item in ranked:
        if item.id in selected_ids or not _has_published_at(item):
            continue
        final.append(item)
        selected_ids.add(item.id)
        if len(final) >= max_candidates:
            break

    return final[:max_candidates]


def _scaled_quotas_for_limit(quotas: dict[str, object], max_candidates: int) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in quotas.items():
        try:
            quota = int(value)
        except (TypeError, ValueError):
            continue
        if quota > 0:
            normalized[str(key)] = quota

    if not normalized:
        return DEFAULT_SOURCE_QUOTAS

    total_quota = sum(normalized.values())
    if total_quota <= 0 or total_quota >= max_candidates:
        return normalized

    scale = max_candidates / total_quota
    return {key: max(value, round(value * scale)) for key, value in normalized.items()}


def _fill_balanced_overflow(
    ranked: list[CandidateNews],
    selected: list[CandidateNews],
    max_candidates: int,
    max_source_ratio: float = 0.55,
) -> list[CandidateNews]:
    if len(selected) >= max_candidates:
        return selected[:max_candidates]

    selected_ids = {item.id for item in selected}
    source_counts = Counter(item.source_type or "unknown" for item in selected)
    source_cap = max(1, round(max_candidates * max_source_ratio))
    filled = list(selected)

    for item in ranked:
        if item.id in selected_ids:
            continue
        source_type = item.source_type or "unknown"
        if source_counts[source_type] >= source_cap:
            continue
        filled.append(item)
        selected_ids.add(item.id)
        source_counts[source_type] += 1
        if len(filled) >= max_candidates:
            break

    return filled[:max_candidates]


def _candidate_sample(candidates: list[CandidateNews], limit: int = 12) -> list[dict[str, object]]:
    sample: list[dict[str, object]] = []
    for item in candidates[:limit]:
        scored = score_candidate(item)
        sample.append(
            {
                "title": item.title,
                "source_name": item.source_name,
                "source_type": item.source_type,
                "url": item.url,
                "score": scored.score,
                "score_reasons": scored.score_reasons[:8],
            }
        )
    return sample


def get_last_selection_report() -> dict[str, object]:
    return dict(_LAST_SELECTION_REPORT)


def prepare_llm_candidates(candidates: list[CandidateNews], lookback_hours: int, max_candidates: int) -> list[CandidateNews]:
    global _LAST_SELECTION_REPORT

    cleaned = clean_candidates(candidates, lookback_hours=lookback_hours)
    url_deduped = deduplicate_by_url(cleaned)
    title_deduped, dropped_duplicates_sample = deduplicate_by_title(url_deduped)
    ai_filtered, github_false_positive_count = _filter_github_ai_false_positives(title_deduped)
    ranked = rank_candidates_lightweight(ai_filtered)

    policy = load_digest_policy()
    quotas = policy.get('candidate_quotas', DEFAULT_SOURCE_QUOTAS)
    if not isinstance(quotas, dict):
        quotas = DEFAULT_SOURCE_QUOTAS

    scaled_quotas = _scaled_quotas_for_limit(quotas, max_candidates)
    balanced = balance_candidates_by_source_type(ranked, max_candidates=max_candidates, quotas=scaled_quotas)
    overflow_filled = _fill_balanced_overflow(ranked, balanced, max_candidates=max_candidates)
    date_capped = _limit_no_date_candidates(overflow_filled, ranked, max_candidates=max_candidates)
    final_candidates = trim_candidates(date_capped, max_candidates=max_candidates)

    _LAST_SELECTION_REPORT = {
        "raw_count": len(candidates),
        "cleaned_count": len(cleaned),
        "url_dedup_count": len(url_deduped),
        "title_dedup_count": len(title_deduped),
        "github_false_positive_count": github_false_positive_count,
        "no_published_at_count": sum(1 for item in ai_filtered if not _has_published_at(item)),
        "no_published_at_selected_count": sum(1 for item in final_candidates if not _has_published_at(item)),
        "candidate_limit": max_candidates,
        "final_count": len(final_candidates),
        "source_distribution_before": _source_distribution(ai_filtered),
        "source_distribution_after_strict_quota": _source_distribution(balanced),
        "source_distribution_after": _source_distribution(final_candidates),
        "dropped_duplicates_sample": dropped_duplicates_sample,
        "final_candidates_sample": _candidate_sample(final_candidates),
    }
    return final_candidates
