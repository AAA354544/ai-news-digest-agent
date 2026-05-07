from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import DailyDigest
from src.processors.analyzer import normalize_digest_payload


def main() -> None:
    payload = {
        "date": "2026-05-07",
        "topic": "AI",
        "main_digest": [
            {
                "title": "示例新闻",
                "links": "https://example.com",
                "tags": "大模型",
                "summary": "摘要",
                "why_it_matters": "重要性",
                "insights": "启示",
                "source_names": "Example Source",
            }
        ],
        "appendix": [],
        "source_statistics": {
            "total_candidates": 1,
            "cleaned_candidates": 1,
            "selected_items": 1,
            "source_count": 1,
            "international_count": 1,
            "chinese_count": 0,
        },
    }

    normalized = normalize_digest_payload(payload)
    if hasattr(DailyDigest, "model_validate"):
        digest = DailyDigest.model_validate(normalized)
    else:
        digest = DailyDigest(**normalized)

    selected_count = sum(len(group.items) for group in digest.main_digest)
    print(f"normalized category count: {len(digest.main_digest)}")
    print(f"normalized selected item count: {selected_count}")
    print("Module 4 payload normalizer test passed.")


if __name__ == "__main__":
    main()
