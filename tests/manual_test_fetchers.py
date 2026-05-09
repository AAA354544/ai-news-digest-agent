from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_enabled_sources
from src.fetchers.arxiv_fetcher import ArxivFetcher
from src.fetchers.base import BaseFetcher
from src.fetchers.github_trending_fetcher import GitHubTrendingFetcher
from src.fetchers.hn_fetcher import HackerNewsFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.semantic_scholar_fetcher import SemanticScholarFetcher
from src.fetchers.web_extractor import extract_text_from_url
from src.models import CandidateNews
from src.utils.http_utils import is_placeholder_url
from src.utils.source_health import save_source_health


def build_fetcher(source: dict[str, Any]) -> BaseFetcher | None:
    source_type = source.get('type', '').strip()

    if source_type in {'rss', 'rss_or_web'}:
        return RSSFetcher(source)
    if source_type == 'hn_algolia':
        return HackerNewsFetcher(source)
    if source_type == 'arxiv':
        return ArxivFetcher(source)
    if source_type == 'github_trending':
        return GitHubTrendingFetcher(source)
    if source_type == 'semantic_scholar':
        return SemanticScholarFetcher(source)
    return None


def to_json_compatible(items: list[CandidateNews]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, 'model_dump'):
            data.append(item.model_dump(mode='json'))
        else:
            data.append(item.dict())
    return data


def main() -> None:
    topic = os.getenv('DIGEST_TOPIC', 'AI')
    enabled_sources = get_enabled_sources()
    print(f'enabled sources: {len(enabled_sources)}')
    print(f'topic for fetch test: {topic}')

    all_candidates: list[CandidateNews] = []
    health_records: list[dict[str, Any]] = []

    for source in enabled_sources:
        source_name = source.get('name', 'UNKNOWN')
        source_type = source.get('type', '')
        endpoint = str(source.get('url_or_endpoint', ''))

        if is_placeholder_url(endpoint):
            print(f'source={source_name} count=0 status=skipped_placeholder')
            health_records.append({'name': source_name, 'type': source_type, 'enabled': True, 'status': 'skipped_placeholder', 'count': 0, 'note': 'placeholder endpoint'})
            continue

        fetcher = build_fetcher(source)
        if fetcher is None:
            print(f'source={source_name} count=0 status=failed_but_continued')
            health_records.append({'name': source_name, 'type': source_type, 'enabled': True, 'status': 'failed_but_continued', 'count': 0, 'note': 'unsupported source type'})
            continue

        count = 0
        status = 'empty'
        note = ''
        try:
            items = fetcher.fetch(topic=topic)
            count = len(items)
            all_candidates.extend(items)
            health = fetcher.get_health()
            status = 'ok' if count > 0 else health.get('status', 'empty')
            note = health.get('note', '')
        except Exception as exc:
            status = 'failed_but_continued'
            note = str(exc)

        print(f'source={source_name} count={count} status={status}')
        health_records.append({'name': source_name, 'type': source_type, 'enabled': True, 'status': status, 'count': count, 'note': note})

    print(f'total candidates: {len(all_candidates)}')
    arxiv_status = next((x.get('status') for x in health_records if 'arxiv' in str(x.get('name', '')).lower()), 'N/A')
    sem_status = next((x.get('status') for x in health_records if 'semantic scholar' in str(x.get('name', '')).lower()), 'N/A')
    print(f'arxiv status: {arxiv_status}')
    print(f'semantic_scholar status: {sem_status}')

    if all_candidates:
        dist = Counter(item.source_type for item in all_candidates)
        print('source_type distribution:')
        for k in sorted(dist.keys()):
            print(f'  {k}: {dist[k]}')

        region_dist = Counter(item.region for item in all_candidates)
        print('region distribution:')
        for k in sorted(region_dist.keys()):
            print(f'  {k}: {region_dist[k]}')

        research_sources = {'arxiv', 'semantic_scholar', 'crossref', 'papers_with_code'}
        research_count = sum(1 for x in all_candidates if x.source_type in research_sources or (x.category_hint or '').lower() in {'academic_paper', 'research'})
        print(f'research candidates: {research_count}')

        print('top 5 candidates:')
        for idx, item in enumerate(all_candidates[:5], start=1):
            print(f'{idx}. {item.title} | {item.source_name} | {item.url}')

        demo_url = all_candidates[0].url
        extracted = extract_text_from_url(demo_url)
        preview = (extracted[:180] + '...') if extracted and len(extracted) > 180 else extracted
        print(f'demo extract url: {demo_url}')
        print(f"demo extract preview: {preview if preview else 'None'}")
    else:
        print('No candidates fetched. This is acceptable in manual test if network/source availability is limited.')

    out_dir = PROJECT_ROOT / 'data' / 'raw'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_raw_candidates.json"
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(to_json_compatible(all_candidates), f, ensure_ascii=False, indent=2)

    health_path = save_source_health(health_records, output_dir=str(out_dir))

    print(f'saved raw candidates: {out_path}')
    print(f'saved source health: {health_path}')
    print('Module 2 fetchers test completed.')


if __name__ == '__main__':
    main()
