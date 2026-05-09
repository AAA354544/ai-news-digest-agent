from __future__ import annotations

from typing import Any

import feedparser

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import is_placeholder_url, safe_get


class RSSFetcher(BaseFetcher):
    def __init__(self, source_config: SourceConfig | dict[str, Any]) -> None:
        super().__init__(source_config)

    def fetch(self, topic: str | None = None) -> list[CandidateNews]:
        endpoint = (self.source_config.url_or_endpoint or '').strip()
        if is_placeholder_url(endpoint):
            self.set_health('skipped_placeholder', 'placeholder endpoint')
            return []

        result = safe_get(
            endpoint,
            timeout=self.source_config.timeout_seconds,
            max_retries=self.source_config.max_retries,
            request_interval_seconds=self.source_config.request_interval_seconds,
        )
        if result.response is None:
            self.set_health(result.status, result.note)
            return []

        try:
            parsed = feedparser.parse(result.response.text)
        except Exception as exc:
            self.set_health('failed_but_continued', f'feed parse error: {exc}')
            return []

        items: list[CandidateNews] = []
        max_items = self.source_config.max_items or 30
        for entry in getattr(parsed, 'entries', []):
            title = (entry.get('title') or '').strip()
            url = (entry.get('link') or '').strip()
            if not title or not url:
                continue

            published = entry.get('published') or entry.get('updated')
            summary = entry.get('summary') or entry.get('description')

            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type='rss',
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint=self.source_config.category,
                    published_at=published,
                    summary_or_snippet=summary,
                    content_text=None,
                    tags_hint=list(self.source_config.tags),
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
