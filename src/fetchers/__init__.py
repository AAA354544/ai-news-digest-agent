"""Fetchers package."""

from src.fetchers.arxiv_fetcher import ArxivFetcher
from src.fetchers.github_trending_fetcher import GitHubTrendingFetcher
from src.fetchers.hn_fetcher import HackerNewsFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.web_extractor import extract_text_from_url

__all__ = [
    "ArxivFetcher",
    "GitHubTrendingFetcher",
    "HackerNewsFetcher",
    "RSSFetcher",
    "extract_text_from_url",
]
