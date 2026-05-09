from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.config import get_enabled_sources, load_app_config
from src.fetchers.base import BaseFetcher
from src.models import CandidateNews, DailyDigest
from src.processors.event_clusterer import EventCluster, cluster_candidates_into_events, limit_clusters
from src.utils.http_utils import is_placeholder_url
from src.utils.source_health import save_source_health


def _find_latest_file(input_dir: str, pattern: str) -> Path:
    base = Path(input_dir)
    files = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No files found for pattern '{pattern}' in '{input_dir}'.")
    return files[0]


def _to_json_compatible(items: list[CandidateNews]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json"))
        else:
            result.append(item.dict())
    return result


def _load_candidates(path: Path) -> list[CandidateNews]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []

    items: list[CandidateNews] = []
    for idx, entry in enumerate(payload):
        try:
            if hasattr(CandidateNews, "model_validate"):
                items.append(CandidateNews.model_validate(entry))
            else:
                items.append(CandidateNews(**entry))
        except Exception as exc:
            print(f"skip invalid item at index {idx}: {exc}")
    return items


def _build_fetcher(source: dict[str, Any]) -> BaseFetcher | None:
    source_type = source.get("type", "").strip()
    if source_type in {"rss", "rss_or_web"}:
        from src.fetchers.rss_fetcher import RSSFetcher

        return RSSFetcher(source)
    if source_type == "hn_algolia":
        from src.fetchers.hn_fetcher import HackerNewsFetcher

        return HackerNewsFetcher(source)
    if source_type == "arxiv":
        from src.fetchers.arxiv_fetcher import ArxivFetcher

        return ArxivFetcher(source)
    if source_type == "github_trending":
        from src.fetchers.github_trending_fetcher import GitHubTrendingFetcher

        return GitHubTrendingFetcher(source)
    return None


def run_fetch_step(topic_override: str | None = None) -> Path:
    cfg = load_app_config()
    topic = (topic_override or cfg.digest_topic or "AI").strip() or "AI"

    enabled_sources = get_enabled_sources()
    all_candidates: list[CandidateNews] = []
    health_records: list[dict[str, Any]] = []

    for source in enabled_sources:
        source_name = source.get("name", "UNKNOWN")
        source_type = source.get("type", "")
        endpoint = str(source.get("url_or_endpoint", ""))

        fetcher = _build_fetcher(source)
        if fetcher is None:
            health_records.append(
                {
                    "name": source_name,
                    "type": source_type,
                    "enabled": True,
                    "status": "failed_but_continued",
                    "count": 0,
                    "note": "unsupported source type",
                }
            )
            continue

        if is_placeholder_url(endpoint):
            health_records.append(
                {
                    "name": source_name,
                    "type": source_type,
                    "enabled": True,
                    "status": "skipped_placeholder",
                    "count": 0,
                    "note": "placeholder endpoint",
                }
            )
            continue

        try:
            items = fetcher.fetch(topic=topic)
            health = fetcher.get_health()
            status = health.get("status", "ok")
            note = health.get("note", "")
            if len(items) > 0:
                status = "ok"
            all_candidates.extend(items)
            health_records.append(
                {
                    "name": source_name,
                    "type": source_type,
                    "enabled": True,
                    "status": status,
                    "count": len(items),
                    "note": note,
                }
            )
            print(f"[fetch] {source_name}: {len(items)} ({status})")
        except Exception as exc:
            health_records.append(
                {
                    "name": source_name,
                    "type": source_type,
                    "enabled": True,
                    "status": "failed_but_continued",
                    "count": 0,
                    "note": str(exc),
                }
            )
            print(f"[fetch] failed {source_name}: {exc}")

    max_raw = max(1, cfg.max_raw_candidates)
    if len(all_candidates) > max_raw:
        all_candidates = all_candidates[:max_raw]

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_raw_candidates.json"
    out_path.write_text(json.dumps(_to_json_compatible(all_candidates), ensure_ascii=False, indent=2), encoding="utf-8")

    health_path = save_source_health(health_records, output_dir=str(out_dir))
    print(f"[fetch] source health saved: {health_path}")
    return out_path


def run_clean_step(topic_override: str | None = None) -> Path:
    from src.processors.cleaner import clean_candidates
    from src.processors.deduplicator import deduplicate_by_url, prepare_llm_candidates

    cfg = load_app_config()
    topic = (topic_override or cfg.digest_topic or "AI").strip() or "AI"

    raw_path = _find_latest_file("data/raw", "*_raw_candidates.json")
    raw_candidates = _load_candidates(raw_path)

    cleaned_only = clean_candidates(raw_candidates, lookback_hours=cfg.digest_lookback_hours)
    deduped_only = deduplicate_by_url(cleaned_only)
    cluster_input = deduped_only[: max(1, cfg.max_cluster_input_candidates)]

    final_candidates = prepare_llm_candidates(
        cluster_input,
        lookback_hours=cfg.digest_lookback_hours,
        max_candidates=max(1, cfg.max_llm_events),
        topic=topic,
        allow_overflow=True,
    )

    print(
        f"[clean] raw={len(raw_candidates)}, cleaned={len(cleaned_only)}, "
        f"dedup={len(deduped_only)}, cluster_input={len(cluster_input)}, final_llm_candidates={len(final_candidates)}"
    )

    out_dir = Path("data/cleaned")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_cleaned_candidates.json"
    out_path.write_text(json.dumps(_to_json_compatible(final_candidates), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _save_clusters(clusters: list[EventCluster], output_dir: str = "data/clustered") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_event_clusters.json"
    payload = []
    for c in clusters:
        payload.append(
            {
                "event_id": c.event_id,
                "representative_title": c.representative_title,
                "normalized_key": c.normalized_key,
                "category_hint": c.category_hint,
                "importance_score": c.importance_score,
                "region_hint": c.region_hint,
                "topic_relevance_score": c.topic_relevance_score,
                "source_names": c.source_names,
                "links": c.links,
                "source_types": c.source_types,
                "evidence_count": c.evidence_count,
            }
        )
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def run_analyze_step(limit_for_test: int | None = None, topic_override: str | None = None) -> Path:
    from src.processors.analyzer import analyze_candidates_with_llm, finalize_digest_statistics, save_digest

    cfg = load_app_config()
    topic = (topic_override or cfg.digest_topic or "AI").strip() or "AI"

    cleaned_path = _find_latest_file("data/cleaned", "*_cleaned_candidates.json")
    candidates = _load_candidates(cleaned_path)

    cluster_input_candidates = candidates[: max(1, cfg.max_cluster_input_candidates)]
    clusters = cluster_candidates_into_events(cluster_input_candidates, topic=topic)

    max_events = limit_for_test if limit_for_test is not None else cfg.max_llm_events
    max_events = max(1, max_events)
    final_clusters = limit_clusters(clusters, max_events=max_events)
    _save_clusters(final_clusters)

    raw_count = 0
    try:
        raw_path = _find_latest_file("data/raw", "*_raw_candidates.json")
        raw_count = len(_load_candidates(raw_path))
    except Exception:
        raw_count = len(candidates)

    stats_context = {
        "raw_candidates": raw_count,
        "cleaned_candidates": len(candidates),
        "cluster_input_candidates": len(cluster_input_candidates),
        "event_clusters": len(clusters),
        "final_llm_events": len(final_clusters),
        "source_count": len({c.source_name for c in candidates}),
        "international_count": sum(1 for c in candidates if c.region.lower() == "international"),
        "chinese_count": sum(1 for c in candidates if c.region.lower() in {"chinese", "china", "zh"}),
    }

    try:
        digest: DailyDigest = analyze_candidates_with_llm(
            candidates=cluster_input_candidates,
            config=cfg,
            topic_override=topic,
            event_clusters=final_clusters if cfg.llm_pipeline_mode == "layered" else None,
            stats_context=stats_context,
        )
    except Exception as exc:
        print(f"[analyze] layered/event mode failed, fallback to candidate mode: {exc}")
        digest = analyze_candidates_with_llm(
            candidates=cluster_input_candidates,
            config=cfg,
            topic_override=topic,
            event_clusters=None,
            stats_context=stats_context,
        )

    digest = finalize_digest_statistics(
        digest,
        raw_candidates=stats_context["raw_candidates"],
        cleaned_candidates=stats_context["cleaned_candidates"],
        cluster_input_candidates=stats_context["cluster_input_candidates"],
        event_clusters=stats_context["event_clusters"],
        final_llm_events=stats_context["final_llm_events"],
    )
    digest.topic = topic
    digest.source_statistics.source_count = stats_context["source_count"]
    digest.source_statistics.international_count = stats_context["international_count"]
    digest.source_statistics.chinese_count = stats_context["chinese_count"]

    return save_digest(digest, output_dir="data/digested")


def run_report_step() -> tuple[Path, Path]:
    from src.generators.report_generator import load_latest_digest, render_html_report, render_markdown_report, save_report_files

    digest = load_latest_digest(input_dir="data/digested")
    markdown_text = render_markdown_report(digest, template_dir="templates")
    html_text = render_html_report(digest, template_dir="templates")
    return save_report_files(digest, markdown_text, html_text, output_base_dir="outputs")


def run_email_step(dry_run_override: bool | None = None) -> dict[str, object]:
    from src.notifiers.email_sender import EmailSender

    html_path = _find_latest_file("outputs/html", "*-ai-news-digest.html")
    md_path = _find_latest_file("outputs/markdown", "*-ai-news-digest.md")
    sender = EmailSender()
    if dry_run_override is not None:
        sender.config.dry_run = dry_run_override
    return sender.send_digest_email(html_path=html_path, markdown_path=md_path)


def run_full_pipeline(
    send_email: bool = False,
    llm_candidate_limit: int | None = None,
    topic_override: str | None = None,
    dry_run: bool | None = None,
) -> dict[str, object]:
    cfg = load_app_config()
    raw_path = run_fetch_step(topic_override=topic_override)
    cleaned_path = run_clean_step(topic_override=topic_override)
    digest_path = run_analyze_step(limit_for_test=llm_candidate_limit, topic_override=topic_override)
    md_path, html_path = run_report_step()
    source_health_path = _find_latest_file("data/raw", "*_source_health.json")

    email_result: dict[str, object] | None = None
    should_send = send_email or cfg.send_email
    if should_send:
        email_result = run_email_step(dry_run_override=dry_run)

    pipeline_summary: dict[str, object] = {}
    try:
        payload = json.loads(Path(digest_path).read_text(encoding="utf-8"))
        stats = payload.get("source_statistics", {}) if isinstance(payload, dict) else {}
        pipeline_summary = {
            "raw_candidates": stats.get("raw_candidates"),
            "cleaned_candidates": stats.get("cleaned_candidates"),
            "cluster_input_candidates": stats.get("cluster_input_candidates"),
            "event_clusters": stats.get("event_clusters"),
            "final_llm_events": stats.get("final_llm_events"),
            "selected_items": stats.get("selected_items"),
            "appendix_items": stats.get("appendix_items"),
            "source_count": stats.get("source_count"),
            "chinese_count": stats.get("chinese_count"),
            "international_count": stats.get("international_count"),
            "topic": payload.get("topic"),
        }
    except Exception:
        pipeline_summary = {}

    return {
        "raw_path": raw_path,
        "cleaned_path": cleaned_path,
        "digest_path": digest_path,
        "markdown_path": md_path,
        "html_path": html_path,
        "source_health_path": source_health_path,
        "pipeline_summary": pipeline_summary,
        "email_result": email_result,
    }
