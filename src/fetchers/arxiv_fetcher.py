from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
        'cat:cs.IR',
        'cat:stat.ML',
        'all:large language model',
        'all:agent',
        'all:retrieval augmented generation',
    ]

    def __init__(
        self,
        source_config: SourceConfig | dict[str, Any],
        queries: list[str] | None = None,
        max_results_per_query: int = 5,
    ) -> None:
        super().__init__(source_config)
        self.queries = queries or self.DEFAULT_QUERIES
        self.max_results_per_query = max(1, min(max_results_per_query, 20))
        self.cache_dir = Path('data/cache')
        self.cache_path = self.cache_dir / 'arxiv_latest.json'

    def _resolve_queries(self, topic: str | None) -> list[str]:
        if not topic or not topic.strip():
            return self.queries

        topic_lower = topic.lower()
        expanded_terms: list[str] = [topic.strip()]
        if any(x in topic_lower for x in ['agent', 'tool', 'memory', 'workflow', 'rag', 'planning']):
            expanded_terms.extend(
                [
                    'LLM reasoning',
                    'long context language models',
                    'long-context LLM',
                    'LLM memory',
                    'memory augmented language models',
                    'retrieval augmented generation',
                    'RAG memory',
                    'agent memory',
                    'tool use language models',
                    'chain-of-thought reasoning',
                    'planning with language models',
                    'context compression',
                    'working memory agents',
                    'continual learning language models',
                    'AI agents',
                    'LLM agents',
                    'multi-agent systems',
                ]
            )

        merged = [f'all:{term}' for term in expanded_terms if term] + self.queries
        deduped: list[str] = []
        seen: set[str] = set()
        for q in merged:
            if q in seen:
                continue
            seen.add(q)
            deduped.append(q)
        return deduped

    def _save_cache(self, items: list[CandidateNews]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                'saved_at': datetime.now(timezone.utc).isoformat(),
                'items': [x.model_dump(mode='json') if hasattr(x, 'model_dump') else x.dict() for x in items],
            }
            self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            return

    def _load_recent_cache(self, max_age_days: int = 3) -> list[CandidateNews]:
        if not self.cache_path.exists():
            return []
        try:
            payload = json.loads(self.cache_path.read_text(encoding='utf-8'))
            saved_at = payload.get('saved_at')
            if not saved_at:
                return []
            saved_dt = datetime.fromisoformat(saved_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) - saved_dt > timedelta(days=max_age_days):
                return []
            raw_items = payload.get('items', [])
            items: list[CandidateNews] = []
            for entry in raw_items:
                if hasattr(CandidateNews, 'model_validate'):
                    items.append(CandidateNews.model_validate(entry))
                else:
                    items.append(CandidateNews(**entry))
            return items
        except Exception:
            return []

    def fetch(self, topic: str | None = None) -> list[CandidateNews]:
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()
        max_items = self.source_config.max_items or 20

        last_status = 'ok'
        rate_limited_hit = False
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
                    rate_limited_hit = True
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
                        tags_hint=['arxiv', 'paper', 'research'],
                    )
                )
                if len(items) >= max_items:
                    break

            time.sleep(max(2.0, self.source_config.request_interval_seconds))

        if items:
            self._save_cache(items)
            self.set_health('ok', f'items={len(items)}')
            return items

        cache_items = self._load_recent_cache(max_age_days=3)
        if cache_items:
            reason = 'arxiv_rate_limited' if rate_limited_hit else (last_status or 'temporary_failure')
            self.set_health('cache_fallback', f'reason={reason}; items={len(cache_items)}')
            return cache_items[:max_items]

        self.set_health('empty' if last_status == 'ok' else last_status, f'items={len(items)}')
        return items
