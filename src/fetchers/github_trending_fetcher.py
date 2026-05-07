from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig


class GitHubTrendingFetcher(BaseFetcher):
    DEFAULT_ENDPOINT = "https://github.com/trending"
    KEYWORDS = ("ai", "llm", "agent", "rag", "transformer", "diffusion", "model")

    def __init__(self, source_config: SourceConfig | dict[str, Any], timeout: int = 12) -> None:
        super().__init__(source_config)
        self.timeout = timeout

    def fetch(self) -> list[CandidateNews]:
        endpoint = (self.source_config.url_or_endpoint or self.DEFAULT_ENDPOINT).strip() or self.DEFAULT_ENDPOINT
        items: list[CandidateNews] = []

        try:
            resp = requests.get(endpoint, timeout=self.timeout, headers={"User-Agent": "ai-news-digest-agent/0.1"})
            resp.raise_for_status()
        except Exception as exc:
            print(f"[GitHubTrendingFetcher] Request failed: {exc}")
            return []

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.select("article.Box-row")
        except Exception as exc:
            print(f"[GitHubTrendingFetcher] Parse failed: {exc}")
            return []

        if not articles:
            print("[GitHubTrendingFetcher] No trending entries found.")
            return []

        for article in articles:
            a_tag = article.select_one("h2 a")
            if not a_tag:
                continue
            repo_path = (a_tag.get("href") or "").strip()
            if not repo_path:
                continue
            title = " ".join(a_tag.get_text(" ", strip=True).split())
            url = urljoin("https://github.com", repo_path)
            description_tag = article.select_one("p")
            description = description_tag.get_text(" ", strip=True) if description_tag else ""

            searchable = f"{title} {description}".lower()
            if not any(keyword in searchable for keyword in self.KEYWORDS):
                continue

            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type="github_trending",
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint="open_source_project",
                    published_at=None,
                    summary_or_snippet=description,
                    content_text=None,
                    tags_hint=["github", "trending", "open-source"],
                )
            )
        return items
