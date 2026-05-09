from __future__ import annotations

from typing import Any

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import safe_get


class GDELTFetcher(BaseFetcher):
    API_ENDPOINT = 'https://api.gdeltproject.org/api/v2/doc/doc'

    def __init__(self, source_config: SourceConfig | dict[str, Any], query: str = 'artificial intelligence OR large language model') -> None:
        super().__init__(source_config)
        self.query = query

    def fetch(self) -> list[CandidateNews]:
        max_items = self.source_config.max_items or 10
        params = {
            'query': self.query,
            'mode': 'artlist',
            'format': 'json',
            'maxrecords': max_items,
            'sort': 'datedesc',
        }
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
        for obj in data.get('articles', []):
            title = (obj.get('title') or '').strip()
            url = (obj.get('url') or '').strip()
            if not title or not url:
                continue
            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type='gdelt',
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint='ai_media',
                    published_at=obj.get('seendate'),
                    summary_or_snippet=obj.get('domain') or '',
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
