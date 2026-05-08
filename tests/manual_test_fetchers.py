from __future__ import annotations

import json
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
from src.fetchers.github_trending_fetcher import GitHubTrendingFetcher
from src.fetchers.hn_fetcher import HackerNewsFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.web_extractor import extract_text_from_url
from src.models import CandidateNews
from src.utils.http_utils import is_placeholder_url
from src.utils.source_health import save_source_health


def run_fetcher(source: dict[str, Any]) -> list[CandidateNews]:
    source_type = source.get('type', '').strip()

    if source_type == 'rss':
        return RSSFetcher(source).fetch()
    if source_type == 'hn_algolia':
        return HackerNewsFetcher(source).fetch()
    if source_type == 'arxiv':
        return ArxivFetcher(source).fetch()
    if source_type == 'github_trending':
        return GitHubTrendingFetcher(source).fetch()
    if source_type == 'rss_or_web':
        return RSSFetcher(source).fetch()

    return []


def to_json_compatible(items: list[CandidateNews]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, 'model_dump'):
            data.append(item.model_dump(mode='json'))
        else:
            data.append(item.dict())
    return data


def main() -> None:
    enabled_sources = get_enabled_sources()
    print(f'enabled sources: {len(enabled_sources)}')

    all_candidates: list[CandidateNews] = []
    health_records: list[dict[str, Any]] = []

    for source in enabled_sources:
        source_name = source.get('name', 'UNKNOWN')
        source_type = source.get('type', '')
        endpoint = str(source.get('url_or_endpoint', ''))

        if is_placeholder_url(endpoint):
            print(f'source={source_name} count=0 status=skipped_placeholder')
            health_records.append(
                {
                    'name': source_name,
                    'type': source_type,
                    'enabled': bool(source.get('enabled', True)),
                    'status': 'skipped_placeholder',
                    'count': 0,
                    'note': 'placeholder endpoint',
                }
            )
            continue

        status = 'empty'
        note = ''
        count = 0
        try:
            items = run_fetcher(source)
            count = len(items)
            all_candidates.extend(items)
            status = 'ok' if count > 0 else 'empty'
        except TimeoutError:
            status = 'timeout'
            note = 'timeout'
        except Exception as exc:
            msg = str(exc).lower()
            if '429' in msg or 'rate' in msg:
                status = 'rate_limited'
            elif '404' in msg:
                status = 'http_404'
            elif 'timeout' in msg:
                status = 'timeout'
            else:
                status = 'failed_but_continued'
            note = str(exc)

        print(f'source={source_name} count={count} status={status}')
        health_records.append(
            {
                'name': source_name,
                'type': source_type,
                'enabled': bool(source.get('enabled', True)),
                'status': status,
                'count': count,
                'note': note,
            }
        )

    print(f'total candidates: {len(all_candidates)}')

    if all_candidates:
        dist = Counter(item.source_type for item in all_candidates)
        print('source_type distribution:')
        for k in sorted(dist.keys()):
            print(f'  {k}: {dist[k]}')

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
