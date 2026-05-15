from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import _structured_digest_groups
from src.config import AppConfig
from src.models import CategoryGroup, DailyDigest, DigestNewsItem, SourceStatistics
from src.processors.analyzer import enforce_digest_shape, finalize_digest_statistics
from src.processors.candidate_scorer import is_probable_ai_github_project


def _item(idx: int, source: str, link: str, tags: list[str] | None = None) -> DigestNewsItem:
    return DigestNewsItem(
        title=f"Signal {idx}｜信号 {idx}",
        links=[link],
        tags=tags or ["AI"],
        summary=f"Summary {idx}",
        mechanism=f"Mechanism {idx}",
        why_it_matters=f"Why {idx}",
        insights=f"Insight {idx}",
        source_names=[source],
    )


def _fake_digest() -> DailyDigest:
    research = [
        _item(idx, "arXiv AI/CL", f"https://arxiv.org/abs/2605.{idx}", ["arXiv", "benchmark"])
        for idx in range(1, 6)
    ]
    hn = [
        _item(idx, "Hacker News AI Search", f"https://news.ycombinator.com/item?id={idx}", ["HN", "AI"])
        for idx in range(6, 14)
    ]
    industry = [
        _item(idx, "OpenAI News", f"https://openai.com/index/example-{idx}", ["OpenAI"])
        for idx in range(14, 22)
    ]
    return DailyDigest(
        date="2026-05-15",
        topic="AI",
        main_digest=[
            CategoryGroup(category_name="论文与科研进展", items=research),
            CategoryGroup(category_name="模型与技术进展", items=hn),
            CategoryGroup(category_name="产业与公司动态", items=industry),
        ],
        appendix=[],
        source_statistics=SourceStatistics(total_candidates=40, cleaned_candidates=30),
    )


def main() -> None:
    digest = enforce_digest_shape(_fake_digest(), config=AppConfig(digest_lookback_hours=48))
    digest = finalize_digest_statistics(
        digest,
        stats_context={
            "final_llm_candidates": 30,
            "no_published_at_count": 6,
            "no_published_at_selected_count": 2,
            "source_distribution_after": {"arxiv": 5, "hn_algolia": 8, "rss": 8},
            "chinese_count": 0,
            "international_count": 30,
            "chinese_shortage_reason": "no_chinese_sources_enabled",
        },
    )

    main_count = sum(len(group.items) for group in digest.main_digest)
    hn_main_count = sum(
        1
        for group in digest.main_digest
        for item in group.items
        if "Hacker News" in " ".join(item.source_names)
    )

    assert main_count <= 18
    assert hn_main_count <= 4
    assert digest.source_statistics.selected_items == main_count
    assert digest.source_statistics.appendix_items == len(digest.appendix)
    assert digest.source_statistics.source_distribution["OpenAI News"] == 8
    assert digest.source_statistics.category_distribution["论文与科研进展"] == 5
    assert digest.source_statistics.final_candidate_source_distribution["hn_algolia"] == 8
    assert digest.source_statistics.chinese_shortage_reason == "no_chinese_sources_enabled"
    assert digest.source_statistics.moved_from_main_to_appendix >= 4

    groups = _structured_digest_groups(digest)
    assert groups[0]["category"] == "论文与科研进展"
    assert groups[0]["items"][0]["index"] == 1
    assert groups[0]["items"][0]["title_primary"] == "Signal 1"
    assert groups[0]["items"][0]["title_secondary"] == "信号 1"
    industry_group = next(group for group in groups if group["category"] == "产业与公司动态")
    assert industry_group["items"][0]["links"][0]["label"] == "OpenAI 原文"

    assert not is_probable_ai_github_project("telegraf", "metrics collection monitoring agent")
    assert is_probable_ai_github_project("agentic-rag", "LLM agent with RAG and tool calling")

    print("report statistics tests passed")


if __name__ == "__main__":
    main()
