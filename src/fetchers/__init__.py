"""Fetchers package."""

from src.fetchers.arxiv_fetcher import ArxivFetcher
from src.fetchers.crossref_fetcher import CrossrefFetcher
from src.fetchers.gdelt_fetcher import GDELTFetcher
from src.fetchers.github_api_fetcher import GitHubAPIFetcher
from src.fetchers.github_trending_fetcher import GitHubTrendingFetcher
from src.fetchers.hn_fetcher import HackerNewsFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.rsshub_fetcher import RSSHubFetcher
from src.fetchers.semantic_scholar_fetcher import SemanticScholarFetcher
from src.fetchers.web_extractor import extract_text_from_url

__all__ = [
    'ArxivFetcher',
    'CrossrefFetcher',
    'GDELTFetcher',
    'GitHubAPIFetcher',
    'GitHubTrendingFetcher',
    'HackerNewsFetcher',
    'RSSFetcher',
    'RSSHubFetcher',
    'SemanticScholarFetcher',
    'extract_text_from_url',
]
