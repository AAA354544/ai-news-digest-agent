from __future__ import annotations

from typing import Any

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import safe_get


class SemanticScholarFetcher(BaseFetcher):
    API_ENDPOINT = 'https://api.semanticscholar.org/graph/v1/paper/search'

    def __init__(self, source_config: SourceConfig | dict[str, Any], query: str = 'artificial intelligence') -> None:
        super().__init__(source_config)
        self.query = query

    def fetch(self) -> list[CandidateNews]:
        max_items = self.source_config.max_items or 10
        params = {'query': self.query, 'limit': max_items, 'fields': 'title,url,year,abstract'}
        result = safe_get(self.API_ENDPOINT, params=params, timeout=self.source_config.timeout_seconds or 20, max_retries=self.source_config.max_retries or 1)
        if result.response is None:
            self.set_health(result.status, result.note)
            return []
        try:
            data = result.response.json()
        except Exception as exc:
            self.set_health('failed_but_continued', f'json parse error: {exc}')
            return []

        items: list[CandidateNews] = []
        for paper in data.get('data', []):
            title = (paper.get('title') or '').strip()
            url = (paper.get('url') or '').strip()
            if not title or not url:
                continue
            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type='semantic_scholar',
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint='research',
                    summary_or_snippet=paper.get('abstract') or '',
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
