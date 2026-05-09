from __future__ import annotations

import json
from typing import Any

from src.config import load_digest_policy
from src.models import CandidateNews
from src.processors.event_clusterer import EventCluster


def _clip_text(value: str | None, max_chars: int = 220) -> str:
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


def _skeleton(categories: list[str]) -> dict[str, Any]:
    return {
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
            'raw_candidates': 0,
            'cluster_input_candidates': 0,
            'event_clusters': 0,
            'final_llm_events': 0,
            'appendix_items': 0,
        },
    }


def build_digest_system_prompt() -> str:
    return (
        '你是专业 AI 情报编辑、技术分析师、产业观察员。'
        '定位是“AI 科研最新进展 + AI 技术/产业风向日报”。'
        '只基于输入内容分析，不得编造外部事实。'
        '优先按“事件”组织信息：同一事件的多来源必须尽量合并为一条。'
        '输出必须是 RFC 8259 标准 JSON；所有 key 和字符串必须双引号。'
        '不要 Markdown，不要代码块，不要 JSON 外解释文字，不要尾随逗号。'
        'main_digest 必须是 category group 结构，不能是扁平列表。'
        '每个 digest item 必须包含 title, links, tags, summary, why_it_matters, insights, source_names。'
        'links 必须来自输入链接。'
        'appendix 每条必须是 {title, link, source, brief_summary}。'
        '不要使用 appendix 的 url/links/source_name/source_names/summary 字段名。'
        'appendix.brief_summary 只能描述事件本身，不能解释筛选或降级原因。'
        '不要出现“降级至附录/弱相关/与AI无关/避免重复/debug/dropped/filtered”等内部决策措辞。'
        '与 AI 主题无关的内容应直接丢弃，不要输出到 appendix。'
        'appendix 不能与 main_digest 重复链接。'
        '正文不应被单一来源主导；HN 不应主导；论文类原则上不超过约 40%。'
        '这是 AI Research & Industry Digest，不是工具新闻列表。'
        '如果输入包含 arXiv/Semantic Scholar/research 候选，正文至少保留 3 条研究内容。'
        '不要让 GitHub Trending、HN 或中文产业稿挤掉论文与科研进展。'
        '针对主题应强约束相关性：弱相关工具、融资、硬件小新闻优先放 appendix。'
        '中文输出中不要产生未转义英文双引号，概念引用优先使用「」。'
        '正文必须输出 10-15 条，目标约 12 条；候选充足时不要只输出 5 条。'
        '正文整体应尽量保持 international:chinese 约 70:30（允许小幅波动）。'
        '中文来源用于补充中国 AI 生态，不应支配整份日报。'
        '弱相关、营销稿、职业焦虑、泛生活内容应降级到 appendix 或剔除。'
        'source_statistics.selected_items 必须等于 main_digest 实际条目总数。'
    )


def build_digest_user_prompt(
    candidates: list[CandidateNews],
    topic: str,
    date: str,
    min_items: int,
    max_items: int,
    appendix_max_items: int,
    stats_context: dict[str, int] | None = None,
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
                'region': item.region,
                'language': item.language,
                'published_at': str(item.published_at) if item.published_at is not None else None,
                'summary_or_snippet': _clip_text(item.summary_or_snippet, max_chars=200),
            }
        )

    categories = _preferred_categories()
    skeleton = _skeleton(categories)

    return (
        f'date: {date}\n'
        f'topic: {topic}\n'
        f'candidate_count: {len(candidates)}\n'
        f'main_digest_item_range: {min_items}-{max_items}\n'
        f'appendix_max_items: {appendix_max_items}\n'
        f'stats_context: {json.dumps(stats_context or {}, ensure_ascii=False)}\n\n'
        '当前输入是候选新闻列表。请尽量识别同一事件并合并，不要重复写同一事件。\n'
        '正文精选规则：\n'
        '- 必须输出 10-15 条，目标 12 条；\n'
        '- 若候选不足，不要用低价值内容凑数。\n'
        '正文目标来源比例：international 约 70%，chinese 约 30%。\n'
        'appendix 保留未进正文但有价值的候选，最多 appendix_max_items 条。\n'
        '普通融资、普通硬件小新闻、营销稿、职业焦虑、泛生活内容优先放 appendix。\n'
        '正文结构建议：2-3 条 research/paper/benchmark/method，3-5 条 agent/tool use/memory/workflow，2-3 条产业/基础设施，其余高价值补充。\n'
        '如果存在研究候选，正文中“论文与科研进展/技术与模型进展”应至少包含 3 条研究内容。\n'
        '对于当前 topic，优先 reasoning/long context/memory/RAG/tool use/planning/context compression 相关事件。\n'
        'appendix 的 brief_summary 只写事件内容，不要写“为什么被降级”。\n'
        '返回严格 JSON，不要任何额外文本。\n'
        f'分类建议：{categories}\n'
        f'JSON 骨架：\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n'
        f'candidates:\n{json.dumps(packed, ensure_ascii=False)}'
    )


def build_digest_user_prompt_from_clusters(
    clusters: list[EventCluster],
    topic: str,
    date: str,
    min_items: int,
    max_items: int,
    appendix_max_items: int,
    stats_context: dict[str, int] | None = None,
) -> str:
    packed: list[dict[str, Any]] = []
    for cluster in clusters:
        evidence_snippets: list[str] = []
        for source in cluster.sources[:4]:
            evidence_snippets.append(_clip_text(source.summary_or_snippet, max_chars=180))

        packed.append(
            {
                'event_id': cluster.event_id,
                'representative_title': cluster.representative_title,
                'category_hint': cluster.category_hint,
                'importance_score': cluster.importance_score,
                'topic_relevance_score': cluster.topic_relevance_score,
                'region_hint': cluster.region_hint,
                'evidence_count': cluster.evidence_count,
                'source_names': cluster.source_names,
                'source_types': cluster.source_types,
                'links': cluster.links,
                'evidence_snippets': evidence_snippets,
            }
        )

    categories = _preferred_categories()
    skeleton = _skeleton(categories)

    return (
        f'date: {date}\n'
        f'topic: {topic}\n'
        f'event_cluster_count: {len(clusters)}\n'
        f'main_digest_item_range: {min_items}-{max_items}\n'
        f'appendix_max_items: {appendix_max_items}\n'
        f'stats_context: {json.dumps(stats_context or {}, ensure_ascii=False)}\n\n'
        '当前输入已经是事件聚类（同一事件多来源已初步聚合）。\n'
        '请按事件写日报，不要把同一事件拆成多条。\n'
        '每条正文可包含多个 links 和多个 source_names。\n'
        'summary 写事件事实；why_it_matters 写重要性；insights 写趋势判断和启示。\n'
        '正文应保持 10-15 条（目标约 12 条）并保持 international:chinese 约 70:30。\n'
        '若输入含 research clusters（如 arXiv/Semantic Scholar），正文至少保留 3 条研究类事件。\n'
        '弱相关、营销稿、职业焦虑、泛生活内容不要进入正文。\n'
        '附录保留未入正文但值得关注的事件，不要重复正文链接。\n'
        'appendix brief_summary 只描述事件本身，不得包含内部筛选理由。\n'
        '返回严格 JSON，不要任何额外文本。\n'
        f'分类建议：{categories}\n'
        f'JSON 骨架：\n{json.dumps(skeleton, ensure_ascii=False, indent=2)}\n\n'
        f'event_clusters:\n{json.dumps(packed, ensure_ascii=False)}'
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


def build_json_repair_prompts(broken_json_text: str) -> tuple[str, str]:
    system_prompt = (
        '你是 JSON 修复助手。'
        '任务是把输入修复为 RFC 8259 合法 JSON。'
        '只输出 JSON，不要 Markdown，不要代码块，不要解释。'
        '不要改变业务语义；仅修复语法问题。'
        '可修复字段名引号、中文引号、单引号、尾逗号、缺失引号等格式错误。'
        '除非为满足结构最低合法性，不要新增内容。'
    )
    user_prompt = (
        '请修复下面文本为严格合法 JSON。'
        '必须使用双引号作为 key 和字符串引号。'
        '不要输出任何 JSON 之外的内容。\n\n'
        f'{broken_json_text or ""}'
    )
    return system_prompt, user_prompt
