from __future__ import annotations

import time
from typing import Any

import feedparser

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import safe_get


class ArxivFetcher(BaseFetcher):
    API_ENDPOINT = 'http://export.arxiv.org/api/query'
    DEFAULT_QUERIES = [
        'cat:cs.AI',
        'cat:cs.CL',
        'cat:cs.LG',
        'cat:cs.CV',
        'cat:cs.IR',
        'cat:stat.ML',
        'all:large language model',
        'all:agent',
        'all:retrieval augmented generation',
    ]

    def __init__(self, source_config: SourceConfig | dict[str, Any], queries: list[str] | None = None, max_results_per_query: int = 5) -> None:
        super().__init__(source_config)
        self.queries = queries or self.DEFAULT_QUERIES
        self.max_results_per_query = max(1, min(max_results_per_query, 20))

    def fetch(self) -> list[CandidateNews]:
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()
        max_items = self.source_config.max_items or 20
        timeout = self.source_config.timeout_seconds or 20
        retries = self.source_config.max_retries if self.source_config.max_retries is not None else 1
        interval = self.source_config.request_interval_seconds if self.source_config.request_interval_seconds is not None else 2.0

        last_status = 'ok'
        for query in self.queries:
            if len(items) >= max_items:
                break
            params = {
                'search_query': query,
                'start': 0,
                'max_results': min(self.max_results_per_query, max_items - len(items)),
                'sortBy': 'submittedDate',
                'sortOrder': 'descending',
            }
            result = safe_get(
                self.API_ENDPOINT,
                params=params,
                timeout=timeout,
                max_retries=retries,
                request_interval_seconds=interval,
                cache_ttl_seconds=60,
            )
            if result.response is None:
                last_status = result.status
                if result.status == 'rate_limited':
                    break
                continue

            try:
                parsed = feedparser.parse(result.response.text)
            except Exception as exc:
                last_status = f'parse_error:{exc}'
                continue

            for entry in getattr(parsed, 'entries', []):
                title = (entry.get('title') or '').strip().replace('\n', ' ')
                link = (entry.get('link') or '').strip()
                if not title or not link or link in seen_urls:
                    continue
                seen_urls.add(link)
                authors = [a.get('name', '').strip() for a in entry.get('authors', []) if a.get('name')]
                summary = (entry.get('summary') or '').strip().replace('\n', ' ')
                if authors:
                    summary = f"authors={', '.join(authors[:5])}; {summary}"
                items.append(
                    CandidateNews(
                        id=self.build_candidate_id(link),
                        title=title,
                        url=link,
                        source_name=self.source_config.name,
                        source_type='arxiv',
                        region=self.source_config.region,
                        language=self.source_config.language,
                        category_hint='academic_paper',
                        published_at=entry.get('published'),
                        summary_or_snippet=summary,
                        content_text=None,
                        tags_hint=['arxiv', 'paper'],
                    )
                )
                if len(items) >= max_items:
                    break
            time.sleep(interval)

        self.set_health('ok' if items else ('empty' if last_status == 'ok' else last_status), f'items={len(items)}')
        return items
