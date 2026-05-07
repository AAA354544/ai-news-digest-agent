from __future__ import annotations

from typing import Any

import requests

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig


class HackerNewsFetcher(BaseFetcher):
    API_ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"
    DEFAULT_QUERIES = ["AI", "LLM", "Agent", "RAG", "OpenAI", "Anthropic", "DeepMind", "Gemini", "Claude"]

    def __init__(
        self,
        source_config: SourceConfig | dict[str, Any],
        queries: list[str] | None = None,
        hits_per_page: int = 8,
        timeout: int = 10,
    ) -> None:
        super().__init__(source_config)
        self.queries = queries or self.DEFAULT_QUERIES
        self.hits_per_page = max(1, min(hits_per_page, 20))
        self.timeout = timeout

    def fetch(self) -> list[CandidateNews]:
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()

        for query in self.queries:
            params = {"query": query, "tags": "story", "hitsPerPage": self.hits_per_page}
            try:
                resp = requests.get(self.API_ENDPOINT, params=params, timeout=self.timeout)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                print(f"[HackerNewsFetcher] Query failed ({query}): {exc}")
                continue

            for hit in payload.get("hits", []):
                title = (hit.get("title") or hit.get("story_title") or "").strip()
                hn_object_id = str(hit.get("objectID") or "").strip()
                url = (hit.get("url") or hit.get("story_url") or "").strip()
                if not url and hn_object_id:
                    url = f"https://news.ycombinator.com/item?id={hn_object_id}"

                if not title or not url:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                author = hit.get("author", "unknown")
                points = hit.get("points", 0)
                comments = hit.get("num_comments", 0)
                snippet = f"author={author}; points={points}; comments={comments}; query={query}"

                items.append(
                    CandidateNews(
                        id=self.build_candidate_id(url),
                        title=title,
                        url=url,
                        source_name=self.source_config.name,
                        source_type="hn_algolia",
                        region=self.source_config.region,
                        language=self.source_config.language,
                        category_hint=self.source_config.category,
                        published_at=hit.get("created_at"),
                        summary_or_snippet=snippet,
                        content_text=None,
                        tags_hint=["hackernews", query.lower()],
                    )
                )
        return items
