from __future__ import annotations

import json
from typing import Any

from src.config import load_digest_policy
from src.models import CandidateNews


def _clip_text(value: str | None, max_chars: int = 200) -> str:
    text = (value or '').strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '...'


def _preferred_categories() -> list[str]:
    policy = load_digest_policy()
    categories = policy.get('main_digest_policy', {}).get('preferred_categories', [])
    if isinstance(categories, list) and categories:
        return [str(x) for x in categories]
    return [
        '技术与模型进展',
        '科研与论文前沿',
        'Agent 与 AI 工具',
        '产业与公司动态',
        '开源生态与开发者趋势',
        '算力、芯片与基础设施',
        '安全、政策与监管',
        '其他',
    ]


def build_digest_system_prompt() -> str:
    return (
        '你是专业 AI 新闻编辑与科研趋势分析师。'
        '定位是“AI 科研最新进展 + AI 技术/产业风向日报”。'
        '你只能基于用户提供的候选新闻分析，不得编造外部事实。'
        '不要展示推理过程，直接输出最终 JSON。'
        '输出必须是严格 JSON；不要 Markdown；不要代码块；不要解释文字。'
        'main_digest 必须是 category group 结构，不能是扁平新闻数组。'
        '每个 group 必须包含 category_name 和 items。'
        '每个 item 必须包含 title, links, tags, summary, why_it_matters, insights, source_names。'
        'links 必须来自候选 URL。'
        '报告不应变成论文摘要列表。'
        '论文内容应提炼研究方向、技术趋势和工程启示，而非仅翻译 abstract。'
        '产业/产品内容应提炼公司战略、商业化趋势、开发者生态和基础设施变化。'
        'insights 必须体现趋势判断或启示，不得重复 summary。'
        '科研与论文前沿在正文中原则上不超过 40%，除非候选几乎全是论文。'
        'appendix 不应重复 main_digest 同一 URL。'
        'source_statistics.selected_items 必须等于 main_digest 所有 items 总数。'
    )


def build_digest_user_prompt(candidates: list[CandidateNews], topic: str, date: str, min_items: int, max_items: int) -> str:
    packed: list[dict[str, Any]] = []
    for item in candidates:
        packed.append(
            {
                'id': item.id,
                'title': item.title,
                'url': item.url,
                'source_name': item.source_name,
                'source_type': item.source_type,
                'published_at': str(item.published_at) if item.published_at is not None else None,
                'summary_or_snippet': _clip_text(item.summary_or_snippet, max_chars=200),
            }
        )

    categories = _preferred_categories()
    skeleton = {
        'date': 'YYYY-MM-DD',
        'topic': 'AI',
        'main_digest': [{'category_name': c, 'items': []} for c in categories],
        'appendix': [],
        'source_statistics': {
            'total_candidates': 0,
            'cleaned_candidates': 0,
            'selected_items': 0,
            'source_count': 0,
            'international_count': 0,
            'chinese_count': 0,
        },
    }

    return (
        f'date: {date}\n'
        f'topic: {topic}\n'
        f'candidate_count: {len(candidates)}\n'
        f'main_digest_item_range: {min_items}-{max_items}\n\n'
        '请基于候选新闻输出“AI 科研进展 + 产业风向”结构化日报。\n'
        'main_digest 必须是 category group 结构，不能是扁平数组。\n'
        '如果候选总数不足 max_items，selected_items 必须小于等于候选总数。\n'
        '不要输出任何 JSON 之外的文本。\n'
        f'分类建议：{categories}\n'
        f'请按如下 JSON 骨架返回：\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n'
        f'candidates:\n{json.dumps(packed, ensure_ascii=False)}'
    )


def extract_json_text(response_text: str) -> str:
    text = (response_text or '').strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        while lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        return '\n'.join(lines).strip()
    return text
