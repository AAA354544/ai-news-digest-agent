from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig


class ArxivFetcher(BaseFetcher):
    API_ENDPOINT = "http://export.arxiv.org/api/query"
    DEFAULT_QUERIES = [
        "cat:cs.AI",
        "cat:cs.CL",
        "cat:cs.LG",
        "all:large language model",
        "all:agent",
        "all:retrieval augmented generation",
    ]

    def __init__(
        self,
        source_config: SourceConfig | dict[str, Any],
        queries: list[str] | None = None,
        max_results_per_query: int = 5,
        timeout: int = 12,
    ) -> None:
        super().__init__(source_config)
        self.queries = queries or self.DEFAULT_QUERIES
        self.max_results_per_query = max(1, min(max_results_per_query, 20))
        self.timeout = timeout

    def fetch(self) -> list[CandidateNews]:
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()

        for query in self.queries:
            params = (
                f"search_query={quote_plus(query)}"
                f"&start=0&max_results={self.max_results_per_query}"
                "&sortBy=submittedDate&sortOrder=descending"
            )
            url = f"{self.API_ENDPOINT}?{params}"

            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
            except Exception as exc:
                print(f"[ArxivFetcher] Query failed ({query}): {exc}")
                continue

            for entry in getattr(parsed, "entries", []):
                title = (entry.get("title") or "").strip().replace("\n", " ")
                link = (entry.get("link") or "").strip()
                if not title or not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                authors = [author.get("name", "").strip() for author in entry.get("authors", []) if author.get("name")]
                summary = (entry.get("summary") or "").strip().replace("\n", " ")
                if authors:
                    summary = f"authors={', '.join(authors[:5])}; {summary}"

                items.append(
                    CandidateNews(
                        id=self.build_candidate_id(link),
                        title=title,
                        url=link,
                        source_name=self.source_config.name,
                        source_type="arxiv",
                        region=self.source_config.region,
                        language=self.source_config.language,
                        category_hint="academic_paper",
                        published_at=entry.get("published"),
                        summary_or_snippet=summary,
                        content_text=None,
                        tags_hint=["arxiv", "paper"],
                    )
                )
        return items
