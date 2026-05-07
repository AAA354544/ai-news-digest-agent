from __future__ import annotations

from typing import Any

import feedparser

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig

_INVALID_ENDPOINT_MARKERS = {"", "todo", "placeholder", "待确认", "tbd", "unknown"}


def _is_invalid_endpoint(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in _INVALID_ENDPOINT_MARKERS


class RSSFetcher(BaseFetcher):
    def __init__(self, source_config: SourceConfig | dict[str, Any]) -> None:
        super().__init__(source_config)

    def fetch(self) -> list[CandidateNews]:
        endpoint = (self.source_config.url_or_endpoint or "").strip()
        if _is_invalid_endpoint(endpoint):
            print(f"[RSSFetcher] Skip invalid endpoint for {self.source_config.name}: {endpoint!r}")
            return []

        try:
            parsed = feedparser.parse(endpoint)
        except Exception as exc:
            print(f"[RSSFetcher] Failed to fetch {self.source_config.name}: {exc}")
            return []

        if getattr(parsed, "bozo", False):
            print(f"[RSSFetcher] Parse warning for {self.source_config.name}: {getattr(parsed, 'bozo_exception', '')}")

        items: list[CandidateNews] = []
        for entry in getattr(parsed, "entries", []):
            title = (entry.get("title") or "").strip()
            url = (entry.get("link") or "").strip()
            if not title or not url:
                continue

            published = entry.get("published") or entry.get("updated")
            summary = entry.get("summary") or entry.get("description")

            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type="rss",
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint=self.source_config.category,
                    published_at=published,
                    summary_or_snippet=summary,
                    content_text=None,
                    tags_hint=[],
                )
            )
        return items
