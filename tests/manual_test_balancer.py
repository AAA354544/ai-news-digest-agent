from __future__ import annotations

from collections import Counter
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import CandidateNews
from src.processors.balancer import balance_candidates_by_source_type


def _make_items(source_type: str, n: int) -> list[CandidateNews]:
    items: list[CandidateNews] = []
    for i in range(n):
        items.append(
            CandidateNews(
                id=f"{source_type}-{i}",
                title=f"{source_type} title {i}",
                url=f"https://example.com/{source_type}/{i}",
                source_name=source_type,
                source_type=source_type,
                summary_or_snippet="placeholder",
            )
        )
    return items


def main() -> None:
    candidates = []
    candidates.extend(_make_items('arxiv', 30))
    candidates.extend(_make_items('hn_algolia', 25))
    candidates.extend(_make_items('github_trending', 15))
    candidates.extend(_make_items('rss', 10))

    balanced = balance_candidates_by_source_type(candidates, max_candidates=50)
    dist = Counter(item.source_type for item in balanced)

    print(f"total balanced count: {len(balanced)}")
    print("source_type distribution:")
    for k in sorted(dist.keys()):
        print(f"  {k}: {dist[k]}")

    assert len(balanced) <= 50
    assert dist.get('arxiv', 0) <= 20
    assert dist.get('hn_algolia', 0) <= 18
    assert dist.get('github_trending', 0) <= 8

    print('Module source balancer test passed.')


if __name__ == '__main__':
    main()
