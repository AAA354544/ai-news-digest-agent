from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import CandidateNews
from src.processors.event_clusterer import cluster_candidates_into_events


def _candidate(
    cid: str,
    title: str,
    url: str,
    source_name: str,
    source_type: str = 'rss',
    summary: str = '',
    published_at: str | None = None,
) -> CandidateNews:
    return CandidateNews(
        id=cid,
        title=title,
        url=url,
        source_name=source_name,
        source_type=source_type,
        region='international',
        language='en',
        category_hint='official_blog',
        summary_or_snippet=summary,
        published_at=published_at,
    )


def _cluster_index_for_title(clusters, keyword: str) -> int | None:
    for idx, c in enumerate(clusters):
        if keyword.lower() in c.representative_title.lower() or any(keyword.lower() in s.title.lower() for s in c.sources):
            return idx
    return None


def main() -> None:
    samples = [
        _candidate(
            'a1',
            'OpenAI launches new Agent SDK runtime',
            'https://openai.com/blog/agent-sdk-runtime',
            'OpenAI',
            'rss',
            'official announcement',
            '2026-05-09T10:30:00+08:00',
        ),
        _candidate(
            'a2',
            'Media analysis: OpenAI Agent SDK runtime improves orchestration',
            'https://tech.example.com/openai-agent-sdk-runtime-analysis',
            'Tech Media',
            'rss',
            'media interpretation of same event',
            '2026-05-09T02:35:00',
        ),
        _candidate(
            'a3',
            'Developer notes on OpenAI Agent SDK runtime release',
            'https://dev.example.com/openai-agent-sdk-runtime-notes',
            'Dev Blog',
            'rss',
            'dev perspective of same event',
            '2026-05-09T03:35:00+00:00',
        ),
        _candidate(
            'b1',
            'Terax 7MB AI terminal now available for local use',
            'https://news.ycombinator.com/item?id=111111',
            'Hacker News AI Search',
            'hn_algolia',
            'tiny local terminal project',
        ),
        _candidate(
            'b2',
            'Top LLMs Have a Podcast Together',
            'https://www.youtube.com/watch?v=abc123',
            'Hacker News AI Search',
            'hn_algolia',
            'podcast discussion',
        ),
        _candidate(
            'c1',
            'What if new proofs make LLM training cheaper?',
            'https://example.com/new-proofs-llm-training',
            'AI Research Blog',
            'rss',
            'training theory discussion',
        ),
        _candidate(
            'c2',
            'Claude signup workflow is terrible',
            'https://news.ycombinator.com/item?id=222222',
            'Hacker News AI Search',
            'hn_algolia',
            'product UX complaint',
        ),
        _candidate(
            'd1',
            'Same URL duplicate test',
            'https://example.org/path/post',
            'Source A',
            'rss',
            'first record',
        ),
        _candidate(
            'd2',
            'Same URL duplicate test mirror title',
            'https://example.org/path/post/',
            'Source B',
            'rss',
            'second record',
        ),
    ]

    clusters = cluster_candidates_into_events(samples, topic='AI agent runtime')

    print(f'cluster count: {len(clusters)}')
    for c in clusters:
        print(f"- {c.event_id} | evidence={c.evidence_count} | title={c.representative_title}")

    openai_idx = _cluster_index_for_title(clusters, 'Agent SDK runtime')
    terax_idx = _cluster_index_for_title(clusters, 'Terax')
    podcast_idx = _cluster_index_for_title(clusters, 'Podcast')
    proofs_idx = _cluster_index_for_title(clusters, 'new proofs')
    claude_idx = _cluster_index_for_title(clusters, 'signup workflow')
    same_url_idx = _cluster_index_for_title(clusters, 'Same URL duplicate test')

    if openai_idx is None or clusters[openai_idx].evidence_count < 2:
        raise RuntimeError('Expected OpenAI official+media+dev items to merge into one cluster.')

    if terax_idx is None or podcast_idx is None or terax_idx == podcast_idx:
        raise RuntimeError('Terax terminal and podcast should not be merged.')

    if proofs_idx is None or claude_idx is None or proofs_idx == claude_idx:
        raise RuntimeError('New proofs event and Claude signup workflow should not be merged.')

    if same_url_idx is None or clusters[same_url_idx].evidence_count < 2:
        raise RuntimeError('Same/near URL items should merge.')

    print('Module event clusterer test completed.')


if __name__ == '__main__':
    main()
