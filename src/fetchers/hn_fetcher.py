from __future__ import annotations

from typing import Any

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import safe_get


class HackerNewsFetcher(BaseFetcher):
    API_ENDPOINT = 'https://hn.algolia.com/api/v1/search_by_date'
    DEFAULT_QUERIES = ['AI', 'LLM', 'Agent', 'RAG', 'OpenAI', 'Anthropic', 'DeepMind', 'Gemini', 'Claude']

    def __init__(self, source_config: SourceConfig | dict[str, Any], queries: list[str] | None = None, hits_per_page: int = 8) -> None:
        super().__init__(source_config)
        self.queries = queries or self.DEFAULT_QUERIES
        self.hits_per_page = max(1, min(hits_per_page, 20))

    def fetch(self) -> list[CandidateNews]:
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()
        max_items = self.source_config.max_items or 60

        for query in self.queries:
            if len(items) >= max_items:
                break
            remaining = max_items - len(items)
            params = {'query': query, 'tags': 'story', 'hitsPerPage': min(self.hits_per_page, remaining)}
            resp = safe_get(self.API_ENDPOINT, params=params, timeout=20, max_retries=2)
            if resp is None:
                print(f"[HackerNewsFetcher] query failed/empty: {query}")
                continue

            try:
                payload = resp.json()
            except Exception as exc:
                print(f"[HackerNewsFetcher] invalid json for query {query}: {exc}")
                continue

            for hit in payload.get('hits', []):
                title = (hit.get('title') or hit.get('story_title') or '').strip()
                hn_object_id = str(hit.get('objectID') or '').strip()
                url = (hit.get('url') or hit.get('story_url') or '').strip()
                if not url and hn_object_id:
                    url = f'https://news.ycombinator.com/item?id={hn_object_id}'

                if not title or not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                author = hit.get('author', 'unknown')
                points = hit.get('points', 0)
                comments = hit.get('num_comments', 0)
                snippet = f'author={author}; points={points}; comments={comments}; query={query}'

                items.append(
                    CandidateNews(
                        id=self.build_candidate_id(url),
                        title=title,
                        url=url,
                        source_name=self.source_config.name,
                        source_type='hn_algolia',
                        region=self.source_config.region,
                        language=self.source_config.language,
                        category_hint=self.source_config.category,
                        published_at=hit.get('created_at'),
                        summary_or_snippet=snippet,
                        content_text=None,
                        tags_hint=['hackernews', query.lower()],
                    )
                )
                if len(items) >= max_items:
                    break
        return items
