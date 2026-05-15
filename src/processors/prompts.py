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
        '论文与科研进展',
        '模型与技术进展',
        'Agent 与 AI 工具',
        '开源项目与开发者生态',
        '产业与公司动态',
        '政策安全与风险',
    ]


def recommend_digest_shape(lookback_hours: int) -> dict[str, object]:
    hours = max(1, int(lookback_hours or 24))
    if hours <= 24:
        return {
            'window_label': f'过去 {hours} 小时' if hours != 24 else '过去 24 小时',
            'report_type': '标准日报',
            'main_min': 12,
            'main_max': 15,
            'appendix_min': 5,
            'appendix_max': 10,
        }
    if hours <= 48:
        return {
            'window_label': f'过去 {hours} 小时',
            'report_type': '周中补看',
            'main_min': 15,
            'main_max': 18,
            'appendix_min': 10,
            'appendix_max': 18,
        }
    if hours <= 72:
        return {
            'window_label': f'过去 {hours} 小时',
            'report_type': '三日汇总',
            'main_min': 18,
            'main_max': 22,
            'appendix_min': 15,
            'appendix_max': 25,
        }
    if hours <= 168:
        return {
            'window_label': f'过去 {hours} 小时',
            'report_type': '周报',
            'main_min': 25,
            'main_max': 35,
            'appendix_min': 30,
            'appendix_max': 50,
        }
    return {
        'window_label': f'过去 {hours} 小时',
        'report_type': '长周期汇总',
        'main_min': 30,
        'main_max': 40,
        'appendix_min': 35,
        'appendix_max': 60,
    }


def recommend_llm_candidate_limit(lookback_hours: int, configured_limit: int | None = None) -> int:
    hours = max(1, int(lookback_hours or 24))
    if hours <= 24:
        recommended = 50
    elif hours <= 48:
        recommended = 60
    elif hours <= 72:
        recommended = 75
    elif hours <= 168:
        recommended = 110
    else:
        recommended = 120

    if configured_limit is None:
        return recommended
    return max(recommended, int(configured_limit))


def build_digest_system_prompt() -> str:
    return (
        '你是专业 AI 新闻编辑与科研趋势分析师。'
        '定位是“AI 科研最新进展 + AI 技术/产业风向日报”。'
        '你只能基于用户提供的候选新闻分析，不得编造外部事实。'
        '禁止编造发布时间、公司声明、融资金额、论文结论、实验结果或产品能力。'
        '若证据不足，必须使用保守措辞（例如“可能”“显示为”“候选信息显示”）。'
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
        '不得生成候选中不存在的新链接。'
        '正文标题允许保留英文原题，但 title 字段必须采用“英文原题｜中文副标题”格式；如果原题已是中文，可只写中文标题。'
        'summary、why_it_matters、insights 必须全部使用中文，不得输出英文段落。'
        'summary 需要信息密度充足，建议 2-3 句中文，不要只写一句很短的话。'
        'why_it_matters 建议 1-2 句中文，说明影响对象、变化方向或行业意义。'
        'insights 建议 1-2 句中文，给出趋势判断或工程/研究启示，不得重复 summary。'
        '固定一级栏目只能使用：论文与科研进展、模型与技术进展、Agent 与 AI 工具、开源项目与开发者生态、产业与公司动态、政策安全与风险。'
        '论文、benchmark、arXiv、学术发现必须优先放入“论文与科研进展”，不要混入“模型与技术进展”。'
        '报告不应变成论文摘要列表。'
        '论文内容应提炼研究方向、技术趋势和工程启示，而非仅翻译 abstract。'
        '产业/产品内容应提炼公司战略、商业化趋势、开发者生态和基础设施变化。'
        '官方博客通常代表公司战略、产品更新和模型能力变化。'
        '科技媒体通常代表产业动态和商业化趋势。'
        'arXiv 代表科研前沿，GitHub Trending 代表开发者生态。'
        'HN 代表工程社区讨论，不应主导整份日报。'
        '中文来源代表国内 AI 生态与产业动态。'
        'insights 必须体现趋势判断或启示，不得重复 summary。'
        '论文与科研进展在正文中原则上不超过 45%，除非候选几乎全是论文。'
        'HN 来源在正文中原则上不超过一半。'
        '正文不应被单一来源主导，应在官方博客、产业媒体、开源生态、研究论文之间尽量平衡。'
        'appendix 必须是数组，每个 item 必须严格包含 title、link、source、brief_summary。'
        'appendix 不要使用 url、links、source_name、source_names、summary 字段名。'
        'appendix 不应重复 main_digest 同一 URL。'
        'appendix 是未进入正文但仍值得关注的候选，不是剩余候选全集。'
        'appendix 应过滤普通博客、泛泛评论、争议八卦、非核心 AI 工程内容和低质量社区讨论。'
        '如果候选质量不足，可少于 5 条，不要强行凑数。'
        'source_statistics.selected_items 必须等于 main_digest 所有 items 总数。'
    )


def build_digest_user_prompt(
    candidates: list[CandidateNews],
    topic: str,
    date: str,
    min_items: int,
    max_items: int,
    lookback_hours: int = 24,
) -> str:
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
                'summary_or_snippet': _clip_text(item.summary_or_snippet, max_chars=320),
            }
        )

    categories = _preferred_categories()
    shape = recommend_digest_shape(lookback_hours)
    main_min = int(shape['main_min'])
    main_max = int(shape['main_max'])
    appendix_min = int(shape['appendix_min'])
    appendix_max = int(shape['appendix_max'])
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
        f'lookback_hours: {lookback_hours}\n'
        f'report_window: {shape["window_label"]}\n'
        f'report_type: {shape["report_type"]}\n'
        f'candidate_count: {len(candidates)}\n'
        f'main_digest_item_range: {main_min}-{main_max}\n'
        f'appendix_item_range: {appendix_min}-{appendix_max}\n\n'
        '请基于候选新闻输出“AI 科研进展 + 产业风向”结构化日报。\n'
        '输出必须是 RFC 8259 标准 JSON：key 和字符串都必须是双引号；不要单引号；不要尾随逗号；不要注释。\n'
        'main_digest 必须是 category group 结构，不能是扁平数组。\n'
        '请结合来源类型平衡信息密度：官方博客/产业媒体/开源生态/研究论文尽量均衡。\n'
        '固定一级栏目只能使用：论文与科研进展、模型与技术进展、Agent 与 AI 工具、开源项目与开发者生态、产业与公司动态、政策安全与风险。\n'
        '论文、benchmark、arXiv、学术发现必须优先进入“论文与科研进展”，不要混在“模型与技术进展”。\n'
        'HN 来源在正文中原则上不超过一半；论文类正文原则上不超过约 45%。\n'
        '如果某类来源候选很少，可自然减少该类。\n'
        f'正文精选数量规则：本次是{shape["window_label"]}（{shape["report_type"]}），main_digest 目标 {main_min}-{main_max} 条；如果候选不足，可少于目标但不得超过候选数。\n'
        f'附录补充数量规则：appendix 目标 {appendix_min}-{appendix_max} 条高质量补充；如果候选不足或质量不够，可少于目标，不要把剩余候选全部塞入 appendix。\n'
        '标题语言规则：title 保留英文原题时，必须在同一字段追加中文副标题，格式为“英文原题｜中文副标题”。\n'
        '正文语言规则：summary、why_it_matters、insights、brief_summary 必须使用中文；不要输出英文摘要或英文 why it matters。\n'
        '摘要长度规则：summary 建议 2-3 句中文，约为普通一句话摘要的 1.5 倍；不要空泛。\n'
        'why_it_matters 和 insights 必须是中文，分别解释重要性和趋势启示，不能互相重复。\n'
        'appendix 应保留未进入正文但仍值得关注的候选，且链接不要重复 main_digest。\n'
        'appendix 不要收录普通博客、泛泛评论、争议新闻、非核心 AI 工程内容或低质量社区讨论。\n'
        '低置信度内容应使用谨慎表述，不要写成确定事实。\n'
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
