from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import CategoryGroup, DailyDigest, DigestNewsItem, SourceStatistics
from src.processors.digest_validator import validate_digest


def test_digest_validator_accepts_quality_mechanism_content() -> None:
    item = DigestNewsItem(
        title="AI Agent 评测框架更新｜智能体基准扩大",
        links=["https://example.com/ai-agent-benchmark"],
        tags=["AI", "benchmark"],
        summary=(
            "该信号描述了一个 AI 智能体评测框架的更新，候选材料明确给出项目来源和评测目标。"
            "摘要包含事件本身、适用对象和可确认的信息边界，避免把尚未验证的影响写成结论。"
        ),
        mechanism="机制上，评测框架通过任务集、工具调用和结果校验影响模型开发者的优化方向。",
        why_it_matters="它能帮助开发者判断模型在真实任务链路中的可靠性，而不只看单轮问答表现。",
        insights="趋势上，AI 能力评估正在从静态榜单转向多步骤任务和生态工具配合。",
        source_names=["Example AI Source"],
    )
    digest = DailyDigest(
        date="2026-05-15",
        topic="AI",
        main_digest=[CategoryGroup(category_name="Agent 与 AI 工具", items=[item])],
        appendix=[],
        source_statistics=SourceStatistics(selected_items=1, chinese_count=1),
    )

    report = validate_digest(digest, lookback_hours=24)

    assert report["summary"]["main_count"] == 1
    assert not report["errors"]
    assert not any(issue["code"] == "mechanism_missing_or_short" for issue in report["issues"])
