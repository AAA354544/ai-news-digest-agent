from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_digest_policy


def main() -> None:
    policy = load_digest_policy()
    quotas = policy.get('candidate_quotas', {})
    preferred = policy.get('main_digest_policy', {}).get('preferred_categories', [])
    max_ratio = policy.get('main_digest_policy', {}).get('max_research_ratio')

    print('candidate_quotas:', quotas)
    print('preferred_categories:', preferred)

    assert isinstance(quotas, dict) and 'arxiv' in quotas
    assert max_ratio is not None

    print('Module digest policy test passed.')


if __name__ == '__main__':
    main()
