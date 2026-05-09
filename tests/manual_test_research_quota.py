from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import AppConfig
from src.models import CandidateNews, CategoryGroup, DailyDigest, DigestNewsItem, SourceStatistics
from src.processors.digest_quality import enforce_digest_quality_policy


def _item(title: str, source: str, link: str, summary: str = 'AI update', tags: list[str] | None = None) -> DigestNewsItem:
    return DigestNewsItem(
        title=title,
        links=[link],
        tags=tags or ['AI'],
        summary=summary,
        why_it_matters='important',
        insights='trend',
        source_names=[source],
    )


def _candidate(idx: str, title: str, source: str, source_type: str, region: str = 'international') -> CandidateNews:
    return CandidateNews(
        id=idx,
        title=title,
        url=f'https://example.com/{idx}',
        source_name=source,
        source_type=source_type,
        region=region,
        language='en' if region == 'international' else 'zh',
        category_hint='academic_paper' if source_type in {'arxiv', 'semantic_scholar'} else 'ai_media',
        summary_or_snippet='summary',
    )


def main() -> None:
    cfg = AppConfig(
        main_digest_max_items=12,
        appendix_max_items=20,
        target_international_ratio=0.7,
        target_chinese_ratio=0.3,
        enable_research_quota=True,
        research_min_main_items=3,
        research_target_ratio=0.25,
        research_max_main_items=5,
    )

    research_items = [
        _item(f'arXiv paper {i}', 'arXiv AI/CL', f'https://arxiv.org/abs/2501.{1000+i}', summary='paper on agent memory', tags=['paper', 'arxiv'])
        for i in range(1, 6)
    ]
    research_items.append(
        _item(
            'HN post discussing arXiv long-context paper',
            'Hacker News AI Search',
            'https://arxiv.org/abs/2501.99999',
            summary='discussion of long context reasoning paper',
            tags=['paper', 'reasoning'],
        )
    )
    tool_items = [
        _item(f'Agent tool update {i}', 'GitHub Trending AI', f'https://github.com/example/repo{i}', summary='tooling update', tags=['agent', 'tool'])
        for i in range(1, 13)
    ]

    digest = DailyDigest(
        date='2026-05-09',
        topic='AI agents',
        main_digest=[CategoryGroup(category_name='其他', items=research_items + tool_items)],
        appendix=[],
        source_statistics=SourceStatistics(),
    )

    candidates = []
    for i in range(1, 6):
        candidates.append(_candidate(f'r{i}', f'arXiv paper {i}', 'arXiv AI/CL', 'arxiv'))
    candidates.append(
        _candidate('rh1', 'HN post discussing arXiv long-context paper', 'Hacker News AI Search', 'hn_algolia')
    )
    for i in range(1, 13):
        candidates.append(_candidate(f't{i}', f'Agent tool update {i}', 'GitHub Trending AI', 'github_trending'))

    digest, metrics = enforce_digest_quality_policy(digest, cfg, candidates)

    selected_count = sum(len(g.items) for g in digest.main_digest)
    selected_research_count = metrics.get('selected_research_count', 0)
    intl_count = metrics.get('selected_international_count', 0)
    cn_count = metrics.get('selected_chinese_count', 0)
    if selected_count == 0:
        for g in digest.main_digest:
            print(f'group={g.category_name}, items={len(g.items)}')

    assert 10 <= selected_count <= 15, f'selected count should stay bounded, got {selected_count}'
    assert selected_research_count >= 3, f'research quota should be met, got {selected_research_count}'
    assert intl_count >= cn_count, f'international should not be lower than chinese, intl={intl_count}, cn={cn_count}'

    # No research candidates case: should not force fake research
    digest2 = DailyDigest(
        date='2026-05-09',
        topic='AI agents',
        main_digest=[CategoryGroup(category_name='其他', items=tool_items)],
        appendix=[],
        source_statistics=SourceStatistics(),
    )
    candidates2 = [_candidate(f't{i}', f'Agent tool update {i}', 'GitHub Trending AI', 'github_trending') for i in range(1, 13)]
    digest2, metrics2 = enforce_digest_quality_policy(digest2, cfg, candidates2)
    assert metrics2.get('selected_research_count', 0) == 0, 'should not force unrelated research'

    # HN with arxiv URL should still count as research.
    hn_arxiv = _item(
        'HN shared arXiv paper on long-context memory',
        'Hacker News AI Search',
        'https://arxiv.org/abs/2501.12345',
        summary='discussion on reasoning and long context',
        tags=['arxiv', 'paper'],
    )
    digest3 = DailyDigest(
        date='2026-05-09',
        topic='AI agents',
        main_digest=[CategoryGroup(category_name='Agent 与 AI 工具', items=[hn_arxiv] + tool_items[:4])],
        appendix=[],
        source_statistics=SourceStatistics(),
    )
    candidates3 = [_candidate('h1', hn_arxiv.title, 'Hacker News AI Search', 'hn_algolia')]
    candidates3.extend(_candidate(f't{i}', f'Agent tool update {i}', 'GitHub Trending AI', 'github_trending') for i in range(1, 5))
    digest3, metrics3 = enforce_digest_quality_policy(digest3, cfg, candidates3)
    assert metrics3.get('selected_research_count', 0) >= 1, 'arxiv URL from HN should be recognized as research'

    selected_urls = {u for g in digest.main_digest for it in g.items for u in it.links}
    for ap in digest.appendix:
        assert ap.link not in selected_urls, 'appendix should not duplicate main digest'

    print(f'selected_count={selected_count}')
    print(f'selected_research_count={selected_research_count}')
    print(f"research_quota_met={metrics.get('research_quota_met')}")
    print('Module research quota test passed.')


if __name__ == '__main__':
    main()
