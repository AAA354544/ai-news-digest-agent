from __future__ import annotations

from typing import Any

import feedparser

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import is_placeholder_url, safe_get


class RSSHubFetcher(BaseFetcher):
    def __init__(self, source_config: SourceConfig | dict[str, Any], rsshub_base_url: str, enabled: bool = False) -> None:
        super().__init__(source_config)
        self.rsshub_base_url = (rsshub_base_url or '').rstrip('/')
        self.enabled = enabled

    def fetch(self) -> list[CandidateNews]:
        if not self.enabled:
            self.set_health('skipped_disabled', 'rsshub disabled')
            return []
        route = (self.source_config.url_or_endpoint or '').strip()
        if is_placeholder_url(route) or not route.startswith('/'):
            self.set_health('skipped_placeholder', 'rsshub route missing/invalid')
            return []
        if not self.rsshub_base_url:
            self.set_health('skipped_disabled', 'rsshub base url not configured')
            return []

        endpoint = f"{self.rsshub_base_url}{route}"
        result = safe_get(endpoint, timeout=self.source_config.timeout_seconds or 20, max_retries=self.source_config.max_retries or 1)
        if result.response is None:
            self.set_health(result.status, result.note)
            return []

        parsed = feedparser.parse(result.response.text)
        max_items = self.source_config.max_items or 15
        items: list[CandidateNews] = []
        for entry in getattr(parsed, 'entries', []):
            title = (entry.get('title') or '').strip()
            url = (entry.get('link') or '').strip()
            if not title or not url:
                continue
            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type='rsshub',
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint=self.source_config.category,
                    published_at=entry.get('published') or entry.get('updated'),
                    summary_or_snippet=entry.get('summary') or '',
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
