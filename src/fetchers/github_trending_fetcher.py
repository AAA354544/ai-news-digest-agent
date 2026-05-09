from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import safe_get


class GitHubTrendingFetcher(BaseFetcher):
    DEFAULT_ENDPOINT = 'https://github.com/trending'
    KEYWORDS = ('ai', 'llm', 'agent', 'rag', 'transformer', 'diffusion', 'model')

    def __init__(self, source_config: SourceConfig | dict[str, Any]) -> None:
        super().__init__(source_config)

    def fetch(self, topic: str | None = None) -> list[CandidateNews]:
        endpoint = (self.source_config.url_or_endpoint or self.DEFAULT_ENDPOINT).strip() or self.DEFAULT_ENDPOINT
        items: list[CandidateNews] = []
        max_items = self.source_config.max_items or 10

        result = safe_get(
            endpoint,
            timeout=self.source_config.timeout_seconds,
            max_retries=self.source_config.max_retries,
            request_interval_seconds=self.source_config.request_interval_seconds,
        )
        if result.response is None:
            self.set_health(result.status, result.note)
            return []

        try:
            soup = BeautifulSoup(result.response.text, 'html.parser')
            articles = soup.select('article.Box-row')
        except Exception as exc:
            self.set_health('failed_but_continued', f'parse error: {exc}')
            return []

        keywords = list(self.KEYWORDS)
        if topic and topic.strip():
            keywords.extend([x.lower() for x in topic.split() if x.strip()])

        for article in articles:
            a_tag = article.select_one('h2 a')
            if not a_tag:
                continue
            repo_path = (a_tag.get('href') or '').strip()
            if not repo_path:
                continue
            title = ' '.join(a_tag.get_text(' ', strip=True).split())
            url = urljoin('https://github.com', repo_path)
            description_tag = article.select_one('p')
            description = description_tag.get_text(' ', strip=True) if description_tag else ''

            searchable = f'{title} {description}'.lower()
            if not any(keyword in searchable for keyword in keywords):
                continue

            items.append(
                CandidateNews(
                    id=self.build_candidate_id(url),
                    title=title,
                    url=url,
                    source_name=self.source_config.name,
                    source_type='github_trending',
                    region=self.source_config.region,
                    language=self.source_config.language,
                    category_hint='open_source_project',
                    published_at=None,
                    summary_or_snippet=description,
                    content_text=None,
                    tags_hint=['github', 'trending', 'open-source'],
                )
            )
            if len(items) >= max_items:
                break

        self.set_health('ok' if items else 'empty', f'items={len(items)}')
        return items
