from __future__ import annotations

from collections import defaultdict

from src.config import load_digest_policy
from src.models import CandidateNews

DEFAULT_SOURCE_QUOTAS: dict[str, int] = {
    'arxiv': 20,
    'hn_algolia': 18,
    'github_trending': 8,
    'rss': 12,
    'rss_or_web': 12,
    'official_blog': 12,
    'ai_media': 12,
}


def balance_candidates_by_source_type(
    candidates: list[CandidateNews],
    max_candidates: int,
    quotas: dict[str, int] | None = None,
    allow_overflow: bool = False,
) -> list[CandidateNews]:
    if max_candidates <= 0:
        return []
    if not candidates:
        return []

    if quotas is None:
        policy = load_digest_policy()
        configured = policy.get("candidate_quotas", {})
        quotas = configured if isinstance(configured, dict) else DEFAULT_SOURCE_QUOTAS

    grouped: dict[str, list[CandidateNews]] = defaultdict(list)

    def _bucket_key(item: CandidateNews) -> str:
        category_hint = (item.category_hint or "").strip()
        if item.source_type in {"rss", "rss_or_web"} and category_hint in quotas:
            return category_hint
        return item.source_type

    for item in candidates:
        grouped[_bucket_key(item)].append(item)

    selected: list[CandidateNews] = []
    selected_ids: set[str] = set()

    for source_type, items in grouped.items():
        quota = quotas.get(source_type, quotas.get('rss_or_web', max_candidates))
        for item in items[: max(0, quota)]:
            if item.id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item.id)
            if len(selected) >= max_candidates:
                return selected[:max_candidates]

    # Optional fallback overflow: if enabled, fill from remaining candidates in original order.
    # Default is strict quota mode to avoid one source dominating.
    if allow_overflow and len(selected) < max_candidates:
        for item in candidates:
            if item.id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item.id)
            if len(selected) >= max_candidates:
                break

    return selected[:max_candidates]
