from __future__ import annotations

from typing import Any

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import safe_get


class CrossrefFetcher(BaseFetcher):
    API_ENDPOINT = 'https://api.crossref.org/works'

    def __init__(self, source_config: SourceConfig | dict[str, Any], query: str = 'artificial intelligence') -> None:
        super().__init__(source_config)
        self.query = query

    def fetch(self) -> list[CandidateNews]:
        max_items = self.source_config.max_items or 10
        params = {'query': self.query, 'rows': max_items, 'sort': 'published', 'order': 'desc'}
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
        for obj in data.get('message', {}).get('items', []):
            title_list = obj.get('title') or []
            title = title_list[0].strip() if title_list else ''
            doi = (obj.get('DOI') or '').strip()
            url = f'https://doi.org/{doi}' if doi else (obj.get('URL') or '').strip()
            if not title or not url:
                continue
            snippet = f"publisher={obj.get('publisher', '')}; type={obj.get('type', '')}"
            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type='crossref',
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint='research',
                    summary_or_snippet=snippet,
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
