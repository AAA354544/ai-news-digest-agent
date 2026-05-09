from __future__ import annotations

from typing import Any

import feedparser

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import is_placeholder_url, safe_get


class RSSFetcher(BaseFetcher):
    def __init__(self, source_config: SourceConfig | dict[str, Any]) -> None:
        super().__init__(source_config)

    def fetch(self) -> list[CandidateNews]:
        endpoint = (self.source_config.url_or_endpoint or '').strip()
        if is_placeholder_url(endpoint):
            self.set_health('skipped_placeholder', 'placeholder endpoint')
            return []

        max_items = self.source_config.max_items or 30
        timeout = self.source_config.timeout_seconds or 20
        retries = self.source_config.max_retries if self.source_config.max_retries is not None else 2
        interval = self.source_config.request_interval_seconds if self.source_config.request_interval_seconds is not None else 0.5
        cache_ttl = self.source_config.cache_ttl_seconds if self.source_config.cache_ttl_seconds is not None else 300

        result = safe_get(
            endpoint,
            timeout=timeout,
            max_retries=retries,
            request_interval_seconds=interval,
            cache_ttl_seconds=cache_ttl,
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
                    tags_hint=[],
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
