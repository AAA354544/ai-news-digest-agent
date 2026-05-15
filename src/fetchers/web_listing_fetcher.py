from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import is_placeholder_url, safe_get


class WebListingFetcher(BaseFetcher):
    """Lightweight parser for public listing pages without stable RSS feeds."""

    def __init__(self, source_config: SourceConfig | dict[str, Any]) -> None:
        super().__init__(source_config)

    def fetch(self) -> list[CandidateNews]:
        endpoint = (self.source_config.url_or_endpoint or "").strip()
        if is_placeholder_url(endpoint):
            print(f"[WebListingFetcher] skip placeholder endpoint: {self.source_config.name}")
            return []

        resp = safe_get(endpoint, timeout=20, max_retries=2)
        if resp is None:
            return []

        parsed_endpoint = urlparse(endpoint)
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()
        soup = BeautifulSoup(resp.text, "html.parser")
        for anchor in soup.find_all("a"):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            href = str(anchor.get("href") or "").strip()
            if len(title) < 8 or not href:
                continue
            url = urljoin(endpoint, href)
            parsed_url = urlparse(url)
            if parsed_url.netloc and parsed_url.netloc != parsed_endpoint.netloc:
                continue
            normalized = url.rstrip("/")
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type="web_listing",
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint=self.source_config.category,
                    published_at=None,
                    summary_or_snippet=None,
                    content_text=None,
                    tags_hint=[],
                )
            )
            if len(items) >= (self.source_config.max_items or 20):
                break
        return items
