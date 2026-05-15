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

from src.config import load_app_config
from src.models import CandidateNews
from src.processors.cleaner import clean_candidates
from src.processors.deduplicator import deduplicate_by_url, prepare_llm_candidates
from src.processors.prompts import recommend_llm_candidate_limit


def _find_latest_raw_file(raw_dir: Path) -> Path | None:
    files = sorted(raw_dir.glob('*_raw_candidates.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_candidates(path: Path) -> list[CandidateNews]:
    with path.open('r', encoding='utf-8') as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        return []

    candidates: list[CandidateNews] = []
    for idx, item in enumerate(payload):
        try:
            if hasattr(CandidateNews, 'model_validate'):
                candidates.append(CandidateNews.model_validate(item))
            else:
                candidates.append(CandidateNews(**item))
        except Exception as exc:
            print(f'skip invalid item at index {idx}: {exc}')
    return candidates


def _to_json_compatible(items: list[CandidateNews]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, 'model_dump'):
            result.append(item.model_dump(mode='json'))
        else:
            result.append(item.dict())
    return result


def main() -> None:
    cfg = load_app_config()

    raw_dir = PROJECT_ROOT / 'data' / 'raw'
    latest_raw = _find_latest_raw_file(raw_dir)
    if latest_raw is None:
        print('No raw candidates file found. Please run: python tests/manual_test_fetchers.py')
        return

    raw_candidates = _load_candidates(latest_raw)
    cleaned_only = clean_candidates(raw_candidates, lookback_hours=cfg.digest_lookback_hours)
    deduped_only = deduplicate_by_url(cleaned_only)
    candidate_limit = recommend_llm_candidate_limit(cfg.digest_lookback_hours, cfg.max_llm_candidates)
    final_candidates = prepare_llm_candidates(
        raw_candidates,
        lookback_hours=cfg.digest_lookback_hours,
        max_candidates=candidate_limit,
    )

    print(f'raw candidates count: {len(raw_candidates)}')
    print(f'after cleaning count: {len(cleaned_only)}')
    print(f'after URL dedup count: {len(deduped_only)}')
    print(f'final cleaned candidates count: {len(final_candidates)}')
    print(f'max llm candidates: {candidate_limit}')

    dist = Counter(item.source_type for item in final_candidates)
    print('source_type distribution:')
    for source_type in sorted(dist.keys()):
        print(f'  {source_type}: {dist[source_type]}')

    out_dir = PROJECT_ROOT / 'data' / 'cleaned'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_cleaned_candidates.json"
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(_to_json_compatible(final_candidates), f, ensure_ascii=False, indent=2)

    print('top 5 cleaned candidates:')
    for idx, item in enumerate(final_candidates[:5], start=1):
        print(f'{idx}. {item.title} | {item.source_name} | {item.source_type} | {item.url}')

    print('Module 3 cleaner test completed.')


if __name__ == '__main__':
    main()
