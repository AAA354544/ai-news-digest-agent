from __future__ import annotations

import time
from typing import Any

import feedparser
import requests

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import build_default_headers


class ArxivFetcher(BaseFetcher):
    API_ENDPOINT = 'http://export.arxiv.org/api/query'
    DEFAULT_QUERIES = [
        'cat:cs.AI',
        'cat:cs.CL',
        'cat:cs.LG',
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

            try:
                resp = requests.get(self.API_ENDPOINT, params=params, timeout=20, headers=build_default_headers())
            except requests.Timeout:
                print(f"[ArxivFetcher] timeout: {query}")
                continue
            except requests.RequestException as exc:
                print(f"[ArxivFetcher] request error ({query}): {exc}")
                continue

            if resp.status_code == 429:
                print(f"[ArxivFetcher] rate limited (429) on query '{query}'. Stop remaining arXiv queries.")
                break
            if resp.status_code in {403, 404}:
                print(f"[ArxivFetcher] HTTP {resp.status_code} on query '{query}'.")
                continue

            try:
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
            except Exception as exc:
                print(f"[ArxivFetcher] parse/response failed ({query}): {exc}")
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

            if len(items) < max_items:
                time.sleep(2.0)

        return items
