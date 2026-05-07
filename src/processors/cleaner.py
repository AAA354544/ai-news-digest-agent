from __future__ import annotations

import re
from datetime import datetime, timedelta

from src.models import CandidateNews

_MIN_TITLE_LENGTH = 8
_BAD_TITLE_TOKENS = {"login", "sign in", "subscribe", "404", "not found"}


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def is_valid_candidate(candidate: CandidateNews) -> bool:
    title = normalize_text(candidate.title)
    url = normalize_text(candidate.url)
    if not title or not url:
        return False
    if len(title) < _MIN_TITLE_LENGTH:
        return False
    lowered = title.lower()
    if any(token in lowered for token in _BAD_TITLE_TOKENS):
        return False
    return True


def parse_candidate_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        variants = [raw, raw.replace("Z", "+00:00"), raw.replace("z", "+00:00")]
        for item in variants:
            try:
                return datetime.fromisoformat(item)
            except ValueError:
                continue
        known_formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in known_formats:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    return None


def is_within_lookback(candidate: CandidateNews, lookback_hours: int, now: datetime | None = None) -> bool:
    published = parse_candidate_datetime(candidate.published_at)
    if published is None:
        return True
    if now is None:
        now = datetime.now(tz=published.tzinfo) if published.tzinfo else datetime.now()
    delta = now - published
    return delta <= timedelta(hours=lookback_hours)


def clean_candidates(candidates: list[CandidateNews], lookback_hours: int) -> list[CandidateNews]:
    cleaned: list[CandidateNews] = []
    for candidate in candidates:
        normalized = candidate.model_copy(
            update={
                "title": normalize_text(candidate.title),
                "summary_or_snippet": normalize_text(candidate.summary_or_snippet),
                "content_text": normalize_text(candidate.content_text),
            }
        )
        if not is_valid_candidate(normalized):
            continue
        if not is_within_lookback(normalized, lookback_hours):
            continue
        cleaned.append(normalized)
    return cleaned
