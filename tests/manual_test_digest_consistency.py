from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import CategoryGroup, DailyDigest, DigestNewsItem, SourceStatistics
from src.processors.analyzer import finalize_digest_statistics, normalize_digest_payload


def main() -> None:
    digest = DailyDigest(
        date="2026-05-08",
        topic="AI",
        main_digest=[
            CategoryGroup(
                category_name="技术与模型进展",
                items=[
                    DigestNewsItem(title="A", links=["https://example.com/a"]),
                    DigestNewsItem(title="B", links=["https://example.com/b"]),
                ],
            )
        ],
        appendix=[],
        source_statistics=SourceStatistics(selected_items=99),
    )

    fixed = finalize_digest_statistics(digest)
    assert fixed.source_statistics.selected_items == 2

    payload = {
        "date": "2026-05-08",
        "topic": "AI",
        "main_digest": [],
        "appendix": [
            {
                "title": "示例附录",
                "url": "https://example.com",
                "source_name": "Example Source",
                "summary": "这是一个 summary 字段，不是 brief_summary。",
            }
        ],
        "source_statistics": {
            "total_candidates": 1,
            "cleaned_candidates": 1,
            "selected_items": 99,
            "source_count": 1,
            "international_count": 1,
            "chinese_count": 0,
        },
    }

    normalized = normalize_digest_payload(payload)
    if hasattr(DailyDigest, "model_validate"):
        digest2 = DailyDigest.model_validate(normalized)
    else:
        digest2 = DailyDigest(**normalized)
    digest2 = finalize_digest_statistics(digest2)

    assert digest2.appendix[0].link == "https://example.com"
    assert digest2.appendix[0].source == "Example Source"
    assert "summary 字段" in digest2.appendix[0].brief_summary
    assert digest2.source_statistics.selected_items == 0

    print("Module digest consistency test passed.")


if __name__ == "__main__":
    main()
