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

    def _resolve_queries(self, topic: str | None) -> list[str]:
        if topic and topic.strip():
            topic_query = f'all:{topic.strip()}'
            return [topic_query] + self.queries
        return self.queries

    def fetch(self, topic: str | None = None) -> list[CandidateNews]:
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()
        max_items = self.source_config.max_items or 20

        last_status = 'ok'
        for query in self._resolve_queries(topic):
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
                timeout=self.source_config.timeout_seconds,
                max_retries=self.source_config.max_retries,
                request_interval_seconds=max(2.0, self.source_config.request_interval_seconds),
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

                authors = [author.get('name', '').strip() for author in entry.get('authors', []) if author.get('name')]
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

            time.sleep(max(1.5, self.source_config.request_interval_seconds))

        self.set_health('ok' if items else ('empty' if last_status == 'ok' else last_status), f'items={len(items)}')
        return items
