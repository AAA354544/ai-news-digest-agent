from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import AppConfig
from src.models import AppendixItem, CategoryGroup, DailyDigest, DigestNewsItem, SourceStatistics
from src.processors.analyzer import enforce_digest_shape, finalize_digest_statistics
from src.processors.prompts import recommend_digest_shape


def _fake_item(idx: int) -> DigestNewsItem:
    return DigestNewsItem(
        title=f"Signal {idx}",
        links=[f"https://example.com/news/{idx}"],
        tags=["ai"],
        summary=f"Summary for signal {idx}.",
        mechanism=f"Mechanism for signal {idx}.",
        why_it_matters="It matters for the AI ecosystem.",
        insights="This points to a useful trend.",
        source_names=["Example"],
    )


def _fake_digest() -> DailyDigest:
    groups = [
        CategoryGroup(category_name="论文与科研进展", items=[_fake_item(idx) for idx in range(1, 16)]),
        CategoryGroup(category_name="模型与技术进展", items=[_fake_item(idx) for idx in range(16, 31)]),
    ]
    return DailyDigest(
        date="2026-05-15",
        topic="AI",
        main_digest=groups,
        appendix=[
            AppendixItem(
                title="Duplicate of main",
                link="https://example.com/news/1",
                source="Example",
                brief_summary="Should be removed.",
            ),
            AppendixItem(
                title="Existing appendix",
                link="https://example.com/appendix/1",
                source="Example",
                brief_summary="Should remain if there is room.",
            ),
        ],
        source_statistics=SourceStatistics(selected_items=999),
    )


def _main_count(digest: DailyDigest) -> int:
    return sum(len(group.items) for group in digest.main_digest)


def _assert_shape(hours: int) -> None:
    cfg = AppConfig(digest_lookback_hours=hours)
    shape = recommend_digest_shape(hours)
    digest = enforce_digest_shape(_fake_digest(), config=cfg)
    digest = finalize_digest_statistics(digest)

    main_count = _main_count(digest)
    main_links = {
        link.rstrip("/").lower()
        for group in digest.main_digest
        for item in group.items
        for link in item.links
    }
    appendix_links = {item.link.rstrip("/").lower() for item in digest.appendix}

    assert main_count <= int(shape["main_max"]), (hours, main_count, shape["main_max"])
    assert len(digest.appendix) <= int(shape["appendix_max"]), (hours, len(digest.appendix), shape["appendix_max"])
    assert digest.source_statistics.selected_items == main_count
    assert not (main_links & appendix_links)


def main() -> None:
    _assert_shape(24)
    _assert_shape(36)
    _assert_shape(72)
    print("digest shape tests passed")


if __name__ == "__main__":
    main()
