from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlsplit
import difflib

from src.models import CandidateNews
from src.processors.cleaner import parse_candidate_datetime

ENTITY_HINTS = {
    'openai', 'anthropic', 'claude', 'gemini', 'deepseek', 'qwen', 'nvidia', 'microsoft',
    'google', 'meta', 'mistral', 'hugging face', 'langchain', 'llamaindex', 'arxiv', 'kimi',
}
GENERIC_ENTITY_TERMS = {
    'ai', 'llm', 'agent', 'model', 'openai', 'anthropic', 'claude', 'gemini',
}

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'to', 'of', 'in', 'for', 'with', 'on', 'at', 'by', 'from',
    'ai', 'news', 'update', 'announces', 'launches'
}


@dataclass
class EventCluster:
    event_id: str
    representative_title: str
    normalized_key: str
    category_hint: str
    importance_score: float
    region_hint: str
    topic_relevance_score: float
    sources: list[CandidateNews] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)
    earliest_published_at: datetime | None = None
    latest_published_at: datetime | None = None
    evidence_count: int = 0


def _tokenize(text: str) -> set[str]:
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]+', ' ', (text or '').lower())
    tokens = {t for t in cleaned.split() if t and len(t) >= 2 and t not in STOPWORDS}
    return tokens


def _normalize_key(title: str) -> str:
    tokens = sorted(_tokenize(title))
    return ' '.join(tokens[:8])


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return inter / union if union > 0 else 0.0


def _entity_overlap(title_a: str, title_b: str) -> float:
    ta = title_a.lower()
    tb = title_b.lower()
    matched = 0
    for ent in ENTITY_HINTS:
        if ent in ta and ent in tb:
            matched += 1
    return min(1.0, matched / 2.0)


def _shared_specific_tokens(title_a: str, title_b: str) -> int:
    ta = {t for t in _tokenize(title_a) if t not in GENERIC_ENTITY_TERMS and len(t) >= 3}
    tb = {t for t in _tokenize(title_b) if t not in GENERIC_ENTITY_TERMS and len(t) >= 3}
    return len(ta.intersection(tb))


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower().strip()


def _same_or_near_url(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    pa = urlsplit(a)
    pb = urlsplit(b)
    if pa.netloc.lower() == pb.netloc.lower() and pa.path.rstrip('/') == pb.path.rstrip('/'):
        qa = (pa.query or '').strip().lower()
        qb = (pb.query or '').strip().lower()
        # Keep HN and similar id-based URLs strict: same path but different query should not merge.
        if qa or qb:
            return qa == qb
        return True
    return False


def _time_close(a: datetime | None, b: datetime | None, hours: int = 72) -> bool:
    if a is None or b is None:
        return True
    na = _normalize_datetime_utc(a)
    nb = _normalize_datetime_utc(b)
    if na is None or nb is None:
        return True
    return abs(na - nb) <= timedelta(hours=hours)


def _normalize_datetime_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _topic_score(candidate: CandidateNews, topic: str | None) -> float:
    if not topic:
        return 0.0
    txt = f"{candidate.title} {candidate.summary_or_snippet or ''}".lower()
    topic_tokens = _tokenize(topic)
    if not topic_tokens:
        return 0.0
    hit = sum(1 for t in topic_tokens if t in txt)
    return hit / max(1, len(topic_tokens))


def _source_quality(source_type: str, category_hint: str | None) -> float:
    if source_type == 'arxiv':
        return 0.9
    if source_type == 'rss' and category_hint in {'official_blog', 'ai_company', 'company_blog'}:
        return 0.85
    if source_type == 'rss':
        return 0.75
    if source_type == 'hn_algolia':
        return 0.65
    if source_type == 'github_trending':
        return 0.7
    return 0.6


def _should_merge(candidate: CandidateNews, cluster: EventCluster) -> bool:
    if not cluster.sources:
        return True

    rep = cluster.sources[0]
    if _same_or_near_url(candidate.url, rep.url):
        return True

    candidate_domain = _domain(candidate.url)
    rep_domain = _domain(rep.url)

    t1 = _tokenize(candidate.title)
    t2 = _tokenize(cluster.representative_title)
    jac = _jaccard(t1, t2)
    seq = difflib.SequenceMatcher(None, candidate.title.lower(), cluster.representative_title.lower()).ratio()
    ent = _entity_overlap(candidate.title, cluster.representative_title)
    specific_overlap = _shared_specific_tokens(candidate.title, cluster.representative_title)

    c_dt = parse_candidate_datetime(candidate.published_at)
    r_dt = parse_candidate_datetime(rep.published_at)
    time_ok = _time_close(c_dt, r_dt, hours=72)

    # Keep HN clusters strict: only merge if titles are highly similar or they resolve to same target URL.
    if candidate.source_type == 'hn_algolia' and rep.source_type == 'hn_algolia':
        return time_ok and (jac >= 0.6 and seq >= 0.82 or seq >= 0.9)

    # Keep YouTube clusters strict to avoid accidental merges across unrelated videos.
    if 'youtube.com' in candidate_domain or 'youtu.be' in candidate_domain or 'youtube.com' in rep_domain or 'youtu.be' in rep_domain:
        return time_ok and (seq >= 0.88 and (jac >= 0.55 or specific_overlap >= 1))

    if not time_ok:
        return False

    # Strong lexical agreement.
    if jac >= 0.52 and seq >= 0.78:
        return True
    # Title near-duplicate.
    if seq >= 0.9:
        return True
    # Require concrete overlap (not only generic AI terms) for looser merges.
    if specific_overlap >= 2 and (jac >= 0.35 or seq >= 0.68):
        return True
    if specific_overlap >= 1 and ent >= 0.5 and jac >= 0.3 and seq >= 0.6:
        return True

    return False


def _update_cluster(cluster: EventCluster, candidate: CandidateNews, topic: str | None) -> None:
    cluster.sources.append(candidate)
    if candidate.source_name not in cluster.source_names:
        cluster.source_names.append(candidate.source_name)
    if candidate.url not in cluster.links:
        cluster.links.append(candidate.url)
    if candidate.source_type not in cluster.source_types:
        cluster.source_types.append(candidate.source_type)

    c_dt = _normalize_datetime_utc(parse_candidate_datetime(candidate.published_at))
    if c_dt is not None:
        if cluster.earliest_published_at is None or c_dt < cluster.earliest_published_at:
            cluster.earliest_published_at = c_dt
        if cluster.latest_published_at is None or c_dt > cluster.latest_published_at:
            cluster.latest_published_at = c_dt

    cluster.evidence_count = len(cluster.sources)
    cluster.topic_relevance_score = max(cluster.topic_relevance_score, _topic_score(candidate, topic))

    quality = _source_quality(candidate.source_type, candidate.category_hint)
    diversity = len(cluster.source_types) * 0.12
    evidence = min(1.0, cluster.evidence_count / 5.0)
    cluster.importance_score = round(0.5 * quality + 0.25 * evidence + 0.15 * diversity + 0.1 * cluster.topic_relevance_score, 4)


def cluster_candidates_into_events(candidates: list[CandidateNews], topic: str | None = None) -> list[EventCluster]:
    clusters: list[EventCluster] = []

    for idx, candidate in enumerate(candidates):
        merged = False
        for cluster in clusters:
            if _should_merge(candidate, cluster):
                _update_cluster(cluster, candidate, topic=topic)
                merged = True
                break

        if merged:
            continue

        key = _normalize_key(candidate.title)
        cluster = EventCluster(
            event_id=f'evt_{idx+1:04d}',
            representative_title=candidate.title,
            normalized_key=key,
            category_hint=candidate.category_hint or 'other',
            importance_score=0.0,
            region_hint=candidate.region,
            topic_relevance_score=_topic_score(candidate, topic),
        )
        _update_cluster(cluster, candidate, topic=topic)
        clusters.append(cluster)

    return rank_event_clusters(clusters)


def rank_event_clusters(clusters: Iterable[EventCluster]) -> list[EventCluster]:
    def _score(c: EventCluster) -> tuple[float, int, int, float]:
        official_bonus = 1 if any(x in {'official_blog', 'rss'} for x in c.source_types) else 0
        recency = c.latest_published_at.timestamp() if c.latest_published_at else 0.0
        return (c.importance_score, c.evidence_count, official_bonus, recency)

    return sorted(list(clusters), key=_score, reverse=True)


def limit_clusters(clusters: list[EventCluster], max_events: int) -> list[EventCluster]:
    if max_events <= 0:
        return []
    return clusters[:max_events]
