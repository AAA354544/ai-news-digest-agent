from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_enabled_sources, load_app_config, load_sources_config
from src.models import (
    AppendixItem,
    CandidateNews,
    CategoryGroup,
    DailyDigest,
    DigestNewsItem,
    SourceStatistics,
)


def main() -> None:
    app_cfg = load_app_config()
    print('digest_topic:', app_cfg.digest_topic)
    print('lookback hours:', app_cfg.digest_lookback_hours)
    print('llm_provider:', app_cfg.llm_provider)
    print('timezone:', app_cfg.timezone)

    sources_cfg = load_sources_config()
    if isinstance(sources_cfg, dict):
        sources = sources_cfg.get('sources', [])
    else:
        sources = sources_cfg
    print('sources total:', len(sources))

    enabled_sources = get_enabled_sources()
    print('enabled sources count:', len(enabled_sources))
    print('enabled sources names:', [s.get('name', 'UNKNOWN') for s in enabled_sources])

    candidate = CandidateNews(
        id='cand-001',
        title='Example AI model release',
        url='https://example.com/news/ai-model-release',
        source_name='OpenAI Blog',
        source_type='rss',
        region='global',
        language='en',
        category_hint='model_release',
        summary_or_snippet='A short placeholder summary for module 1 test.',
        tags_hint=['model', 'release', 'llm'],
    )
    print('candidate news:', candidate.model_dump())

    digest_item = DigestNewsItem(
        title='示例：新模型发布',
        links=[candidate.url],
        tags=['模型', '发布'],
        summary='这是一个模块 1 的占位摘要。',
        why_it_matters='用于验证数据模型结构。',
        insights='后续模块将由 LLM 生成更完整内容。',
        source_names=[candidate.source_name],
    )

    digest = DailyDigest(
        date='2026-05-07',
        topic=app_cfg.digest_topic,
        main_digest=[CategoryGroup(category_name='模型与产品', items=[digest_item])],
        appendix=[
            AppendixItem(
                title='补充阅读示例',
                link='https://example.com/appendix',
                source='Example Source',
                brief_summary='补充材料占位文本。',
            )
        ],
        source_statistics=SourceStatistics(
            total_candidates=1,
            cleaned_candidates=1,
            selected_items=1,
            source_count=1,
            international_count=1,
            chinese_count=0,
        ),
    )
    print('daily digest:', digest.model_dump())

    print('Module 1 config and models test passed.')


if __name__ == '__main__':
    main()
