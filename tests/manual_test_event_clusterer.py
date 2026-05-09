from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import CandidateNews
from src.processors.event_clusterer import cluster_candidates_into_events


def main() -> None:
    samples = [
        CandidateNews(
            id='1',
            title='OpenAI announces new Agent SDK update',
            url='https://openai.com/news/agent-sdk-update',
            source_name='OpenAI News',
            source_type='rss',
            region='international',
            language='en',
            category_hint='official_blog',
            summary_or_snippet='Official announcement of Agent SDK updates.',
        ),
        CandidateNews(
            id='2',
            title='Media report: OpenAI Agent SDK brings multi-step tooling',
            url='https://tech.example.com/openai-agent-sdk',
            source_name='Tech Media',
            source_type='rss',
            region='international',
            language='en',
            category_hint='ai_media',
            published_at='2026-05-09T10:30:00+08:00',
            summary_or_snippet='Media interpretation of the same OpenAI Agent SDK update.',
        ),
        CandidateNews(
            id='2b',
            title='OpenAI Agent SDK update improves multi-step tool orchestration',
            url='https://blog.example.com/openai-agent-sdk-analysis',
            source_name='Dev Blog',
            source_type='rss',
            region='international',
            language='en',
            category_hint='developer_tools',
            published_at='2026-05-09T02:35:00',
            summary_or_snippet='Naive datetime sample for the same event to validate timezone normalization.',
        ),
        CandidateNews(
            id='3',
            title='GitHub repo gains stars for OpenAI Agent SDK examples',
            url='https://github.com/example/openai-agent-sdk-examples',
            source_name='GitHub Trending AI',
            source_type='github_trending',
            region='international',
            language='en',
            category_hint='open_source_project',
            summary_or_snippet='Community examples around the same Agent SDK event.',
        ),
        CandidateNews(
            id='4',
            title='Anthropic releases new Claude capabilities for coding agents',
            url='https://anthropic.com/news/claude-coding-agent',
            source_name='Anthropic News',
            source_type='rss',
            region='international',
            language='en',
            category_hint='official_blog',
            summary_or_snippet='Different event: Claude coding agent capability release.',
        ),
    ]

    clusters = cluster_candidates_into_events(samples, topic='AI Agent memory')

    print(f'cluster count: {len(clusters)}')
    for c in clusters:
        print(f"- {c.event_id} | evidence={c.evidence_count} | title={c.representative_title}")
        print(f"  sources={c.source_names}")

    if len(clusters) > len(samples):
        raise RuntimeError('Unexpected cluster explosion.')

    merged_ok = any(c.evidence_count >= 2 for c in clusters)
    if not merged_ok:
        raise RuntimeError('Expected at least one merged event cluster with evidence_count >= 2.')

    print('Module event clusterer test completed.')


if __name__ == '__main__':
    main()
