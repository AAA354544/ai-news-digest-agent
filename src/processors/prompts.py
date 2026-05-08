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
        '输出必须是 RFC 8259 标准 JSON。'
        '所有对象 key 必须使用双引号，所有字符串必须使用双引号。'
        '不要单引号，不要尾随逗号，不要注释。'
        '不要 Markdown，不要代码块，不要 JSON 前后解释文字。'
        'main_digest 是精选正文，不是候选全集。'
        'main_digest 必须是 category group 结构，不能是扁平新闻数组。'
        '每个 group 必须包含 category_name 和 items。'
        '每个 item 必须包含 title, links, tags, summary, why_it_matters, insights, source_names。'
        'links 必须来自候选 URL。'
        '报告不应变成论文摘要列表。'
        '论文内容应提炼研究方向、技术趋势和工程启示，而非仅翻译 abstract。'
        '产业/产品内容应提炼公司战略、商业化趋势、开发者生态和基础设施变化。'
        '官方博客通常代表公司战略、产品更新和模型能力变化。'
        '科技媒体通常代表产业动态和商业化趋势。'
        'arXiv 代表科研前沿，GitHub Trending 代表开发者生态。'
        'HN 代表工程社区讨论，不应主导整份日报。'
        '中文来源代表国内 AI 生态与产业动态。'
        'insights 必须体现趋势判断或启示，不得重复 summary。'
        '科研与论文前沿在正文中原则上不超过 40%，除非候选几乎全是论文。'
        'HN 来源在正文中原则上不超过一半。'
        '正文不应被单一来源主导，应在官方博客、产业媒体、开源生态、研究论文之间尽量平衡。'
        'appendix 必须是数组，每个 item 必须严格包含 title、link、source、brief_summary。'
        'appendix 不要使用 url、links、source_name、source_names、summary 字段名。'
        'appendix 不应重复 main_digest 同一 URL。'
        'appendix 是未进入正文但仍值得关注的候选；若没有合适项可返回空数组。'
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
        '输出必须是 RFC 8259 标准 JSON：key 和字符串都必须是双引号；不要单引号；不要尾随逗号；不要注释。\n'
        'main_digest 必须是 category group 结构，不能是扁平数组。\n'
        '请结合来源类型平衡信息密度：官方博客/产业媒体/开源生态/研究论文尽量均衡。\n'
        'HN 来源在正文中原则上不超过一半；论文类正文原则上不超过约 40%。\n'
        '如果某类来源候选很少，可自然减少该类。\n'
        '正文精选数量规则：\n'
        '- 当候选数 N >= 15 时，main_digest 精选 10-12 条；\n'
        '- 当候选数 8 <= N <= 14 时，main_digest 精选 6-8 条；\n'
        '- 当候选数 N < 8 时，main_digest 最多选择 N 条。\n'
        'appendix 应保留未进入正文但仍值得关注的候选，且链接不要重复 main_digest。\n'
        'appendix item 必须严格使用以下字段：title, link, source, brief_summary。\n'
        '不要使用 appendix 字段名 url/links/source_name/source_names/summary。\n'
        '若没有合适 appendix，可返回 []，不要返回字段不完整对象。\n'
        'source_statistics.selected_items 必须等于 main_digest 所有 items 总数（程序会再次校验修正）。\n'
        '如果候选总数不足 max_items，selected_items 必须小于等于候选总数。\n'
        '不要输出任何 JSON 之外的文本，不要 Markdown，不要 ```json 代码块。\n'
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
