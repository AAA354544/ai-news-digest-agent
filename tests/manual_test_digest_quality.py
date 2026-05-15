from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import CategoryGroup, DailyDigest, DigestNewsItem, SourceStatistics
from src.processors.digest_validator import validate_digest


def _item(idx: int, source: str, link: str) -> DigestNewsItem:
    return DigestNewsItem(
        title=f"AI 模型更新 {idx}｜中文标题 {idx}",
        links=[link],
        tags=["AI", "大模型"],
        summary=(
            "这条新闻说明一个 AI 模型或产品出现了可验证更新，候选材料给出了发布时间、来源和核心变化。"
            "摘要不会只复述标题，而是交代更新内容、适用场景和当前信息边界。"
        ),
        mechanism=(
            "机制上，这类变化通常来自模型能力、工具调用链路或开发者生态的改进，影响会先传导到应用开发和评测基准。"
        ),
        why_it_matters="它帮助读者判断该信号是否会影响产品路线、开源生态或研究方向。",
        insights="趋势上，AI 系统正在从单点模型发布转向工具链、评测和真实应用共同驱动。",
        source_names=[source],
    )


def main() -> None:
    digest = DailyDigest(
        date="2026-05-15",
        topic="AI",
        main_digest=[
            CategoryGroup(
                category_name="模型与技术进展",
                items=[
                    _item(1, "OpenAI News", "https://openai.com/news/example"),
                    _item(2, "arXiv AI/CL", "https://arxiv.org/abs/2605.00001"),
                ],
            )
        ],
        appendix=[],
        source_statistics=SourceStatistics(
            total_candidates=10,
            cleaned_candidates=8,
            final_llm_candidates=5,
            selected_items=2,
            chinese_count=1,
            international_count=7,
        ),
    )
    report = validate_digest(digest, lookback_hours=48)
    assert report["summary"]["main_count"] == 2
    assert report["status"] in {"pass", "warning"}
    assert not report["errors"]
    assert not any(issue["code"] == "mechanism_missing_or_short" for issue in report["issues"])
    print("digest quality tests passed")


if __name__ == "__main__":
    main()
