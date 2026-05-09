from __future__ import annotations

import os
from typing import Any

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import build_default_headers, safe_get


class GitHubAPIFetcher(BaseFetcher):
    API_ENDPOINT = 'https://api.github.com/search/repositories'

    def __init__(self, source_config: SourceConfig | dict[str, Any], query: str = 'topic:ai pushed:>2026-01-01') -> None:
        super().__init__(source_config)
        self.query = query

    def fetch(self) -> list[CandidateNews]:
        max_items = self.source_config.max_items or 10
        params = {'q': self.query, 'sort': 'updated', 'order': 'desc', 'per_page': max_items}
        headers = build_default_headers()
        token = os.getenv('GITHUB_TOKEN', '').strip()
        if token:
            headers['Authorization'] = f'Bearer {token}'

        result = safe_get(self.API_ENDPOINT, params=params, timeout=self.source_config.timeout_seconds or 20, max_retries=self.source_config.max_retries or 1, headers=headers)
        if result.response is None:
            self.set_health(result.status, result.note)
            return []

        try:
            data = result.response.json()
        except Exception as exc:
            self.set_health('failed_but_continued', f'json parse error: {exc}')
            return []

        items: list[CandidateNews] = []
        for repo in data.get('items', []):
            title = (repo.get('full_name') or '').strip()
            url = (repo.get('html_url') or '').strip()
            if not title or not url:
                continue
            snippet = (repo.get('description') or '').strip()
            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type='github_api',
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint='open_source_project',
                    summary_or_snippet=snippet,
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
