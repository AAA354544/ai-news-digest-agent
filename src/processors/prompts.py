from __future__ import annotations

import json
from typing import Any

from src.models import CandidateNews


def _clip_text(value: str | None, max_chars: int = 200) -> str:
    text = (value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def build_digest_system_prompt() -> str:
    return (
        "你是专业 AI 新闻编辑和技术分析师。"
        "你只能基于用户提供的候选新闻进行分析，不得编造外部事实。"
        "任务包括：语义去重、多源事件合并、分类、筛选、总结。"
        "不需要展示推理过程，直接输出最终 JSON。"
        "输出必须是严格 JSON。"
        "不要返回解释，不要返回 Markdown，不要返回 ```json 代码块。"
        "输出语言必须是中文。"
        "main_digest 不能是扁平新闻数组。"
        "main_digest 必须是分类数组，每个分类对象必须包含 category_name 和 items。"
        "分类名称只能使用：大模型、Agent、开源项目、论文、产业公司、政策监管、工具产品、其他。"
        "允许空分类（items 可为空数组），但最终所有分类合计应精选 10-15 条。"
        "每条正文项必须包含：title、links、tags、summary、why_it_matters、insights、source_names。"
        "links 必须来自候选新闻的 url，不能编造新链接。"
        "附录每条包含：title、link、source、brief_summary。"
    )


def build_digest_user_prompt(
    candidates: list[CandidateNews], topic: str, date: str, min_items: int, max_items: int
) -> str:
    packed: list[dict[str, Any]] = []
    for item in candidates:
        packed.append(
            {
                "id": item.id,
                "title": item.title,
                "url": item.url,
                "source_name": item.source_name,
                "source_type": item.source_type,
                "published_at": str(item.published_at) if item.published_at is not None else None,
                "summary_or_snippet": _clip_text(item.summary_or_snippet, max_chars=200),
            }
        )

    skeleton = {
        "date": "YYYY-MM-DD",
        "topic": "AI",
        "main_digest": [
            {"category_name": "大模型", "items": []},
            {"category_name": "Agent", "items": []},
            {"category_name": "开源项目", "items": []},
            {"category_name": "论文", "items": []},
            {"category_name": "产业公司", "items": []},
            {"category_name": "政策监管", "items": []},
            {"category_name": "工具产品", "items": []},
            {"category_name": "其他", "items": []},
        ],
        "appendix": [],
        "source_statistics": {
            "total_candidates": 0,
            "cleaned_candidates": 0,
            "selected_items": 0,
            "source_count": 0,
            "international_count": 0,
            "chinese_count": 0,
        },
    }

    return (
        f"date: {date}\n"
        f"topic: {topic}\n"
        f"candidate_count: {len(candidates)}\n"
        f"main_digest_item_range: {min_items}-{max_items}\n\n"
        "这是模块 4 的链路测试，请优先保证结构正确和可解析。\n"
        "请基于以下候选新闻生成 DailyDigest JSON。\n"
        "JSON 顶层字段必须是：date、topic、main_digest、appendix、source_statistics。\n"
        "main_digest 必须是分类数组，绝不能是扁平新闻数组。\n"
        "每个分类对象必须包含 category_name 和 items。\n"
        "每个 items 元素必须包含：title, links, tags, summary, why_it_matters, insights, source_names。\n"
        "若候选不足 10 条，可精选 3-5 条；若候选充足，尽量遵循 main_digest_item_range。\n"
        "不要返回 Markdown，不要返回 ```json 代码块，不要返回任何解释文本，只返回 JSON。\n"
        "不要编造候选新闻之外的信息；links 必须来自候选新闻 url。\n"
        f"必须严格按以下 JSON 骨架返回（可填充具体内容）：\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n"
        f"candidates:\n{json.dumps(packed, ensure_ascii=False)}"
    )


def extract_json_text(response_text: str) -> str:
    text = (response_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text
