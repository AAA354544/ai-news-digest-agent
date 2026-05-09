from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import AppConfig
from src.models import AppendixItem, CandidateNews, CategoryGroup, DailyDigest, DigestNewsItem, SourceStatistics
from src.processors.digest_quality import enforce_digest_quality_policy

BAD_PHRASES = [
    '降级至附录', '与ai无关', '弱相关', '职业焦虑类', '泛生活', '泛商业', '避免重复', 'debug', 'dropped', 'filtered'
]
HARD_REJECT_EXPECTED = ['ufo', 'discord tui', 'terminal music', 'jane street', 'saas', 'ipv6 proxy']
EXTRA_REJECT_EXPECTED = ['9点1氪', 'dirtyfrag', 'solar radiation']


def main() -> None:
    cfg = AppConfig(
        digest_topic='AI',
        main_digest_min_items=10,
        main_digest_max_items=12,
        appendix_min_items=5,
        appendix_target_items=8,
        appendix_max_items=10,
        target_international_ratio=0.7,
        target_chinese_ratio=0.3,
    )

    candidates: list[CandidateNews] = []
    items: list[DigestNewsItem] = []

    for i in range(1, 6):
        title = f'International AI model release {i}'
        url = f'https://intl.example.com/ai/{i}'
        items.append(
            DigestNewsItem(
                title=title,
                links=[url],
                tags=['AI', 'model'],
                summary='A meaningful AI model capability update.',
                why_it_matters='Impacts developer workflows and model deployment choices.',
                insights='Signals ongoing competition in efficient reasoning models.',
                source_names=['Intl Source'],
            )
        )
        candidates.append(
            CandidateNews(
                id=f'i{i}',
                title=title,
                url=url,
                source_name='Intl Source',
                source_type='rss',
                region='international',
                language='en',
            )
        )

    for i in range(1, 4):
        title = f'中文 AI 产业动态 {i}'
        url = f'https://cn.example.cn/ai/{i}'
        items.append(
            DigestNewsItem(
                title=title,
                links=[url],
                tags=['AI'],
                summary='围绕 AI 产品和产业协作的进展。',
                why_it_matters='有助于理解中文 AI 生态。',
                insights='反映区域产业化节奏。',
                source_names=['中文来源'],
            )
        )
        candidates.append(
            CandidateNews(
                id=f'c{i}',
                title=title,
                url=url,
                source_name='中文来源',
                source_type='rss',
                region='chinese',
                language='zh',
            )
        )

    # additional relevant supplemental items to validate appendix target range
    for i in range(1, 3):
        title = f'Agent memory workflow note {i}'
        url = f'https://supplement.example.com/agent-memory/{i}'
        items.append(
            DigestNewsItem(
                title=title,
                links=[url],
                tags=['agent', 'memory', 'workflow'],
                summary='Agent memory and workflow engineering notes.',
                why_it_matters='Useful supplemental reference for implementation details.',
                insights='Provides medium-priority but topic-related context.',
                source_names=['Supplement Source'],
            )
        )
        candidates.append(
            CandidateNews(
                id=f's{i}',
                title=title,
                url=url,
                source_name='Supplement Source',
                source_type='rss',
                region='international',
                language='en',
            )
        )

    # candidate-only appendix supply (not in LLM main rows) for backfill testing
    for i in range(1, 9):
        candidates.append(
            CandidateNews(
                id=f'a{i}',
                title=f'AI supplemental reference {i}',
                url=f'https://appendix.example.com/ai/{i}',
                source_name='Appendix Feed',
                source_type='rss',
                region='international',
                language='en',
                summary_or_snippet='AI supplemental context for readers.',
            )
        )

    # Duplicate/conflicting main items should be deduplicated and categorized away from research.
    agentmemory_url = 'https://github.com/rohitg00/agentmemory'
    items.append(
        DigestNewsItem(
            title='rohitg00/agentmemory',
            links=[agentmemory_url],
            tags=['agent', 'memory', 'github'],
            summary='Open-source agent memory toolkit.',
            why_it_matters='Useful for workflow prototyping.',
            insights='Engineering-oriented, not a research paper.',
            source_names=['GitHub Trending AI'],
        )
    )
    items.append(
        DigestNewsItem(
            title='rohitg00/agentmemory',
            links=[agentmemory_url],
            tags=['paper', 'benchmark', 'memory'],
            summary='Duplicate same repo accidentally placed in research category.',
            why_it_matters='Should not appear twice.',
            insights='Should be deduplicated.',
            source_names=['GitHub Trending AI'],
        )
    )
    candidates.append(
        CandidateNews(
            id='gh-agentmemory',
            title='rohitg00/agentmemory',
            url=agentmemory_url,
            source_name='GitHub Trending AI',
            source_type='github_trending',
            region='international',
            language='en',
        )
    )

    # low-value / irrelevant samples should be filtered or kept out of appendix
    items.append(
        DigestNewsItem(
            title='AI 让年轻人缓解焦虑的生活方式讨论',
            links=['https://cn.example.cn/noise/1'],
            tags=['AI'],
            summary='属于职业焦虑类内容，降级至附录。',
            why_it_matters='弱相关',
            insights='debug marker',
            source_names=['中文来源'],
        )
    )
    items.append(
        DigestNewsItem(
            title='Frontier plane runway accident update',
            links=['https://world.example.com/non-ai/runway'],
            tags=['world'],
            summary='non-ai event',
            why_it_matters='none',
            insights='none',
            source_names=['World News'],
        )
    )
    items.append(
        DigestNewsItem(
            title='AWS DirtyFrag mitigation note',
            links=['https://security.example.com/dirtyfrag'],
            tags=['security'],
            summary='<div>query=RAG author=test points=99 DirtyFrag mitigation details</div>',
            why_it_matters='infra',
            insights='debug',
            source_names=['Security Feed'],
        )
    )
    items.append(
        DigestNewsItem(
            title='Free Solar Radiation and Heat Flux Data Stream',
            links=['https://weather.example.com/solar-radiation'],
            tags=['data'],
            summary='Solar Radiation dashboard',
            why_it_matters='none',
            insights='none',
            source_names=['Weather Feed'],
        )
    )

    digest = DailyDigest(
        date='2026-05-09',
        topic='AI',
        main_digest=[CategoryGroup(category_name='其他', items=items)],
        appendix=[
            AppendixItem(
                title='Lime files for IPO',
                link='https://business.example.com/lime-ipo',
                source='Business',
                brief_summary='与AI无关，降级至附录。',
            )
        ],
        source_statistics=SourceStatistics(),
    )

    digest, metrics = enforce_digest_quality_policy(digest=digest, cfg=cfg, candidates=candidates)

    selected_count = sum(len(g.items) for g in digest.main_digest)
    appendix_count = len(digest.appendix)

    selected_urls = {u for g in digest.main_digest for it in g.items for u in it.links if u}

    assert 10 <= selected_count <= 15, f'selected_count out of range: {selected_count}'
    assert appendix_count <= 10, f'appendix_count should be capped at 10, got {appendix_count}'

    assert metrics['selected_international_count'] >= metrics['selected_chinese_count'], 'international should dominate by default ratio target'

    joined_appendix = ' '.join(f"{a.title} {a.brief_summary}" for a in digest.appendix).lower()
    for phrase in BAD_PHRASES:
        assert phrase.lower() not in joined_appendix, f'bad phrase leaked to appendix: {phrase}'

    assert 'runway accident' not in joined_appendix, 'irrelevant non-AI runway item should be filtered from appendix'
    assert 'lime files for ipo' not in joined_appendix, 'irrelevant IPO item should be filtered from appendix'
    for bad in HARD_REJECT_EXPECTED:
        assert bad not in joined_appendix, f'hard reject noise should not be in appendix: {bad}'
    for bad in EXTRA_REJECT_EXPECTED:
        assert bad.lower() not in joined_appendix, f'additional hard reject should not be in appendix: {bad}'

    for ap in digest.appendix:
        if ap.link:
            assert ap.link not in selected_urls, 'appendix should not duplicate main digest URL'
        joined = f"{ap.title} {ap.brief_summary}".lower()
        for phrase in BAD_PHRASES:
            assert phrase.lower() not in joined, f'appendix should not leak internal phrase: {phrase}'
        assert '<' not in ap.brief_summary and '>' not in ap.brief_summary, 'appendix summary should not contain HTML tags'
        assert 'query=' not in joined and 'author=' not in joined and 'points=' not in joined, 'appendix summary should not contain debug fields'
        assert len(ap.brief_summary) <= 300, 'appendix brief_summary should be capped'
        ascii_chars = sum(1 for ch in ap.brief_summary if ord(ch) < 128)
        assert ascii_chars / max(1, len(ap.brief_summary)) < 0.95, 'appendix summary should not be raw English one-liner'

    assert 5 <= appendix_count <= 10, f'appendix should be in 5-10 range when relevant supply is enough, got {appendix_count}'
    assert metrics.get('main_backfill_used') is True or selected_count >= 10, 'main backfill should fill when initial rows are sparse'

    # Main digest should not include duplicate same repo url across categories.
    main_links = [u for g in digest.main_digest for it in g.items for u in it.links if u]
    assert main_links.count(agentmemory_url) <= 1, 'same github repo should not be duplicated in main digest'

    print(f'selected_count={selected_count}')
    print(f'appendix_count={appendix_count}')
    print(f"selected_international_count={metrics['selected_international_count']}")
    print(f"selected_chinese_count={metrics['selected_chinese_count']}")
    print(f"dropped_low_value_count={metrics['dropped_low_value_count']}")
    print('Module digest quality policy test passed.')


if __name__ == '__main__':
    main()
