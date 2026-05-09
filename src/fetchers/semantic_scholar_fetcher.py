from __future__ import annotations

from typing import Any

from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, SourceConfig
from src.utils.http_utils import safe_get


class SemanticScholarFetcher(BaseFetcher):
    API_ENDPOINT = 'https://api.semanticscholar.org/graph/v1/paper/search'

    def __init__(self, source_config: SourceConfig | dict[str, Any], max_results_per_query: int = 8) -> None:
        super().__init__(source_config)
        self.max_results_per_query = max(1, min(max_results_per_query, 20))

    def _queries(self, topic: str | None) -> list[str]:
        base = ['large language model', 'agent memory', 'tool use', 'multi-agent systems', 'RAG']
        if not topic or not topic.strip():
            return base

        t = topic.lower()
        expanded = [topic.strip()]
        if any(x in t for x in ['reasoning', 'long', 'context', 'memory', 'workflow', 'tool', 'rag']):
            expanded.extend(
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
                ]
            )
        merged = expanded + base
        deduped: list[str] = []
        seen: set[str] = set()
        for q in merged:
            if q.lower() in seen:
                continue
            seen.add(q.lower())
            deduped.append(q)
        return deduped

    def fetch(self, topic: str | None = None) -> list[CandidateNews]:
        max_items = self.source_config.max_items or 16
        items: list[CandidateNews] = []
        seen_urls: set[str] = set()
        last_status = 'ok'

        for q in self._queries(topic):
            if len(items) >= max_items:
                break

            params = {
                'query': q,
                'limit': min(self.max_results_per_query, max_items - len(items)),
                'fields': 'title,abstract,url,year,publicationDate,authors,externalIds',
            }
            result = safe_get(
                self.API_ENDPOINT,
                params=params,
                timeout=self.source_config.timeout_seconds,
                max_retries=self.source_config.max_retries,
                request_interval_seconds=max(1.2, self.source_config.request_interval_seconds),
            )
            if result.response is None:
                last_status = result.status
                if result.status == 'rate_limited':
                    break
                continue

            try:
                payload = result.response.json()
                rows = payload.get('data', []) if isinstance(payload, dict) else []
            except Exception as exc:
                last_status = f'parse_error:{exc}'
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue
                title = str(row.get('title') or '').strip()
                url = str(row.get('url') or '').strip()
                if not url:
                    ext = row.get('externalIds') or {}
                    arxiv = ext.get('ArXiv') if isinstance(ext, dict) else None
                    if arxiv:
                        url = f'https://arxiv.org/abs/{arxiv}'
                if not title or not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                summary = str(row.get('abstract') or '').strip()
                items.append(
                    CandidateNews(
                        id=self.build_candidate_id(url),
                        title=title,
                        url=url,
                        source_name=self.source_config.name,
                        source_type='semantic_scholar',
                        region=self.source_config.region,
                        language=self.source_config.language,
                        category_hint='academic_paper',
                        published_at=row.get('publicationDate') or row.get('year'),
                        summary_or_snippet=summary,
                        content_text=None,
                        tags_hint=['paper', 'research', 'semantic_scholar'],
                    )
                )
                if len(items) >= max_items:
                    break

        self.set_health('ok' if items else ('empty' if last_status == 'ok' else last_status), f'items={len(items)}')
        return items
