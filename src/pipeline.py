from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.config import get_enabled_sources, load_app_config, load_sources_config
from src.models import CandidateNews
from src.processors.prompts import recommend_llm_candidate_limit


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


def _run_fetcher(source: dict[str, Any]) -> list[CandidateNews]:
    source_type = source.get("type", "").strip()
    if source_type == "rss":
        from src.fetchers.rss_fetcher import RSSFetcher

        return RSSFetcher(source).fetch()
    if source_type == "hn_algolia":
        from src.fetchers.hn_fetcher import HackerNewsFetcher

        return HackerNewsFetcher(source).fetch()
    if source_type == "arxiv":
        from src.fetchers.arxiv_fetcher import ArxivFetcher

        return ArxivFetcher(source).fetch()
    if source_type == "github_trending":
        from src.fetchers.github_trending_fetcher import GitHubTrendingFetcher

        return GitHubTrendingFetcher(source).fetch()
    if source_type == "rss_or_web":
        from src.fetchers.rss_fetcher import RSSFetcher

        return RSSFetcher(source).fetch()
    return []


def _max_items_for_source(source: dict[str, Any], lookback_hours: int) -> int:
    source_type = str(source.get("type") or "").strip()
    configured = source.get("max_items")
    try:
        configured_max = int(configured) if configured is not None else 20
    except (TypeError, ValueError):
        configured_max = 20

    hours = max(1, int(lookback_hours or 24))
    if hours <= 24:
        caps = {"hn_algolia": 18, "github_trending": 5, "arxiv": 12}
        default_cap = 12
    elif hours <= 48:
        caps = {"hn_algolia": 24, "github_trending": 6, "arxiv": 16}
        default_cap = 18
    elif hours <= 72:
        caps = {"hn_algolia": 30, "github_trending": 8, "arxiv": 22}
        default_cap = 24
    else:
        caps = {"hn_algolia": 36, "github_trending": 10, "arxiv": 28}
        default_cap = 30

    return max(1, min(max(configured_max, default_cap), caps.get(source_type, default_cap)))


def _source_for_fetch_window(source: dict[str, Any], lookback_hours: int) -> dict[str, Any]:
    adjusted = dict(source)
    adjusted["max_items"] = _max_items_for_source(source, lookback_hours)
    return adjusted


def _region_count(candidates: list[CandidateNews], region_name: str) -> int:
    aliases = {"chinese": {"chinese", "china", "zh", "cn"}, "international": {"international", "global", "en"}}
    wanted = aliases.get(region_name, {region_name})
    return sum(1 for item in candidates if (item.region or "").strip().lower() in wanted)


def _chinese_shortage_reason(raw_candidates: list[CandidateNews], final_candidates: list[CandidateNews]) -> str | None:
    if _region_count(final_candidates, "chinese") > 0:
        return None

    sources_data = load_sources_config()
    source_rows = sources_data.get("sources", []) if isinstance(sources_data, dict) else sources_data
    chinese_sources = [
        source
        for source in source_rows
        if isinstance(source, dict) and str(source.get("region", "")).strip().lower() in {"chinese", "china", "zh", "cn"}
    ]
    enabled_chinese_sources = [source for source in chinese_sources if bool(source.get("enabled", True))]
    if not enabled_chinese_sources:
        return "no_chinese_sources_enabled"
    if _region_count(raw_candidates, "chinese") == 0:
        return "enabled_chinese_sources_returned_zero_raw_candidates"
    return "chinese_candidates_dropped_before_final_llm_pool"


def run_fetch_step() -> Path:
    cfg = load_app_config()
    enabled_sources = get_enabled_sources()
    all_candidates: list[CandidateNews] = []
    for source in enabled_sources:
        source_name = source.get("name", "UNKNOWN")
        try:
            fetch_source = _source_for_fetch_window(source, cfg.digest_lookback_hours)
            items = _run_fetcher(fetch_source)
            print(f"[fetch] {source_name}: {len(items)} (max_items={fetch_source.get('max_items')})")
            all_candidates.extend(items)
        except Exception as exc:
            print(f"[fetch] failed {source_name}: {exc}")

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_raw_candidates.json"
    out_path.write_text(json.dumps(_to_json_compatible(all_candidates), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def run_clean_step() -> Path:
    from src.processors.cleaner import clean_candidates
    from src.processors.deduplicator import deduplicate_by_url, get_last_selection_report, prepare_llm_candidates

    cfg = load_app_config()
    raw_path = _find_latest_file("data/raw", "*_raw_candidates.json")
    raw_candidates = _load_candidates(raw_path)

    cleaned_only = clean_candidates(raw_candidates, lookback_hours=cfg.digest_lookback_hours)
    deduped_only = deduplicate_by_url(cleaned_only)
    final_candidates = prepare_llm_candidates(
        raw_candidates,
        lookback_hours=cfg.digest_lookback_hours,
        max_candidates=recommend_llm_candidate_limit(cfg.digest_lookback_hours, cfg.max_llm_candidates),
    )

    out_dir = Path("data/cleaned")
    out_dir.mkdir(parents=True, exist_ok=True)

    selection_report = get_last_selection_report()
    title_dedup_count = selection_report.get("title_dedup_count", len(deduped_only))
    source_distribution_after = selection_report.get("source_distribution_after", {})
    if isinstance(source_distribution_after, dict) and source_distribution_after:
        distribution_text = ", ".join(f"{key}={value}" for key, value in source_distribution_after.items())
    else:
        distribution_text = "none"

    effective_candidate_limit = recommend_llm_candidate_limit(cfg.digest_lookback_hours, cfg.max_llm_candidates)
    print(
        "[clean] "
        f"raw={len(raw_candidates)}, "
        f"cleaned={len(cleaned_only)}, "
        f"url_dedup={len(deduped_only)}, "
        f"title_dedup={title_dedup_count}, "
        f"final={len(final_candidates)}, "
        f"candidate_limit={effective_candidate_limit}"
    )
    print(f"[clean] final source distribution: {distribution_text}")

    if selection_report:
        report_path = out_dir / f"{date.today().isoformat()}_candidate_selection_report.json"
        report_path.write_text(json.dumps(selection_report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[clean] selection report: {report_path}")

    out_path = out_dir / f"{date.today().isoformat()}_cleaned_candidates.json"
    out_path.write_text(json.dumps(_to_json_compatible(final_candidates), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def run_analyze_step(limit_for_test: int | None = None) -> Path:
    from src.processors.analyzer import analyze_candidates_with_llm, save_digest

    cfg = load_app_config()
    cleaned_path = _find_latest_file("data/cleaned", "*_cleaned_candidates.json")
    candidates = _load_candidates(cleaned_path)

    limit = limit_for_test if limit_for_test is not None else recommend_llm_candidate_limit(
        cfg.digest_lookback_hours,
        cfg.max_llm_candidates,
    )
    limit = max(1, limit)
    limited = candidates[: min(len(candidates), limit)]

    total_candidates = len(candidates)
    try:
        raw_path = _find_latest_file("data/raw", "*_raw_candidates.json")
        raw_candidates = _load_candidates(raw_path)
        total_candidates = len(raw_candidates)
    except Exception:
        raw_candidates = []
        pass

    source_count = len({(c.source_name or "").strip().lower() for c in candidates if (c.source_name or "").strip()})
    chinese_count = 0
    international_count = 0
    for c in candidates:
        region = (c.region or "").strip().lower()
        if region in {"chinese", "china", "zh", "cn"}:
            chinese_count += 1
        elif region:
            international_count += 1

    stats_context = {
        "total_candidates": total_candidates,
        "cleaned_candidates": len(candidates),
        "final_llm_candidates": len(limited),
        "source_count": source_count,
        "international_count": international_count,
        "chinese_count": chinese_count,
        "chinese_shortage_reason": _chinese_shortage_reason(raw_candidates, candidates),
    }

    try:
        selection_report_path = _find_latest_file("data/cleaned", "*_candidate_selection_report.json")
        selection_report = json.loads(selection_report_path.read_text(encoding="utf-8"))
        if isinstance(selection_report, dict):
            for key in (
                "candidate_limit",
                "final_count",
                "no_published_at_count",
                "no_published_at_selected_count",
                "source_distribution_after",
            ):
                if key in selection_report:
                    stats_context[key] = selection_report[key]
    except Exception:
        pass

    digest = analyze_candidates_with_llm(limited, config=cfg, stats_context=stats_context)
    return save_digest(digest, output_dir="data/digested")


def run_report_step() -> tuple[Path, Path]:
    from src.generators.report_generator import load_latest_digest, render_html_report, render_markdown_report, save_report_files

    digest = load_latest_digest(input_dir="data/digested")
    markdown_text = render_markdown_report(digest, template_dir="templates")
    html_text = render_html_report(digest, template_dir="templates")
    return save_report_files(digest, markdown_text, html_text, output_base_dir="outputs")


def run_email_step(recipients: list[str] | None = None) -> dict[str, object]:
    from src.notifiers.email_sender import EmailSender

    html_path = _find_latest_file("outputs/html", "*-ai-news-digest.html")
    md_path = _find_latest_file("outputs/markdown", "*-ai-news-digest.md")
    return EmailSender().send_digest_email(html_path=html_path, markdown_path=md_path, recipients=recipients)


def run_full_pipeline(
    send_email: bool = False,
    llm_candidate_limit: int | None = None,
    recipients: list[str] | None = None,
) -> dict[str, Path | dict[str, object] | None]:
    raw_path = run_fetch_step()
    cleaned_path = run_clean_step()
    digest_path = run_analyze_step(limit_for_test=llm_candidate_limit)
    md_path, html_path = run_report_step()

    email_result: dict[str, object] | None = None
    if send_email:
        email_result = run_email_step(recipients=recipients)

    return {
        "raw_path": raw_path,
        "cleaned_path": cleaned_path,
        "digest_path": digest_path,
        "markdown_path": md_path,
        "html_path": html_path,
        "email_result": email_result,
    }
