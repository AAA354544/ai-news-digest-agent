from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import CandidateNews, DailyDigest
from src.processors.prompts import recommend_digest_shape

_HN_MARKERS = ("hacker news", "news.ycombinator.com")
_AI_RELEVANCE_TERMS = (
    "ai",
    "llm",
    "agent",
    "rag",
    "model",
    "openai",
    "claude",
    "gemini",
    "deepmind",
    "arxiv",
    "benchmark",
    "智能体",
    "模型",
    "论文",
    "开源",
    "人工智能",
    "大模型",
)


def _norm_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/").lower()


def _is_mostly_chinese(text: str, threshold: float = 0.35) -> bool:
    chars = [ch for ch in (text or "") if not ch.isspace()]
    if not chars:
        return False
    chinese = sum(1 for ch in chars if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in chars if ch.isalpha())
    return chinese / max(1, chinese + letters) >= threshold


def _has_long_english_residue(text: str) -> bool:
    return bool(re.search(r"\b[a-zA-Z][a-zA-Z0-9,;:\- ]{80,}\b", text or ""))


def _item_source_text(item: Any) -> str:
    return " ".join(str(x) for x in (getattr(item, "source_names", []) or []))


def _is_hn_item(item: Any) -> bool:
    text = f"{_item_source_text(item)} {' '.join(getattr(item, 'links', []) or [])}".lower()
    return any(marker in text for marker in _HN_MARKERS)


def _source_distribution(digest: DailyDigest) -> Counter[str]:
    counts: Counter[str] = Counter()
    for group in digest.main_digest:
        for item in group.items:
            for source in item.source_names or ["unknown"]:
                counts[str(source)] += 1
    return counts


def _issue(
    issues: list[dict[str, Any]],
    code: str,
    message: str,
    severity: str = "warning",
    location: str | None = None,
) -> None:
    issues.append({"code": code, "message": message, "severity": severity, "location": location})


def validate_digest(
    digest: DailyDigest,
    *,
    lookback_hours: int,
    candidates: list[CandidateNews] | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    shape = recommend_digest_shape(lookback_hours)
    main_count = sum(len(group.items) for group in digest.main_digest)
    appendix_count = len(digest.appendix or [])

    if main_count > int(shape["main_max"]):
        _issue(issues, "main_digest_too_large", f"main_digest has {main_count}, max is {shape['main_max']}", "error")
    if appendix_count > int(shape["appendix_max"]):
        _issue(issues, "appendix_too_large", f"appendix has {appendix_count}, max is {shape['appendix_max']}")
    if digest.source_statistics.selected_items != main_count:
        _issue(issues, "selected_items_mismatch", "selected_items does not match main_digest item count", "error")

    candidate_urls = {_norm_url(c.url) for c in candidates or [] if _norm_url(c.url)}
    main_links: list[str] = []
    appendix_links: list[str] = []
    hn_main = 0
    weak_ai = 0
    for group in digest.main_digest:
        for idx, item in enumerate(group.items, start=1):
            loc = f"{group.category_name}#{idx}"
            links = [_norm_url(link) for link in item.links if _norm_url(link)]
            main_links.extend(links)
            if _is_hn_item(item):
                hn_main += 1

            summary = item.summary or ""
            mechanism = item.mechanism or ""
            if len(summary) < 80:
                _issue(issues, "summary_too_short", "summary is shorter than 80 chars", location=loc)
            if len(mechanism) < 25:
                _issue(issues, "mechanism_missing_or_short", "mechanism is missing or short", location=loc)
            for field_name in ("summary", "mechanism", "why_it_matters", "insights"):
                value = getattr(item, field_name, "") or ""
                if value and not _is_mostly_chinese(value):
                    _issue(issues, "not_mostly_chinese", f"{field_name} is not mostly Chinese", location=loc)
                if _has_long_english_residue(value):
                    _issue(issues, "long_english_residue", f"{field_name} contains long English residue", location=loc)
            relevance_text = " ".join([item.title, " ".join(item.tags), summary, mechanism, _item_source_text(item)]).lower()
            if not any(term in relevance_text for term in _AI_RELEVANCE_TERMS):
                weak_ai += 1
                _issue(issues, "weak_ai_relevance", "item has weak visible AI relevance", location=loc)
            if candidate_urls:
                for link in links:
                    if link not in candidate_urls:
                        _issue(issues, "link_not_in_candidate_pool", link, location=loc)

    for item in digest.appendix or []:
        link = _norm_url(item.link)
        if link:
            appendix_links.append(link)

    duplicate_main = [url for url, count in Counter(main_links).items() if count > 1]
    if duplicate_main:
        _issue(issues, "duplicate_main_links", f"duplicate main links: {duplicate_main[:5]}", "error")
    overlap = sorted(set(main_links) & set(appendix_links))
    if overlap:
        _issue(issues, "main_appendix_link_overlap", f"main/appendix overlap: {overlap[:5]}", "error")

    hn_cap = 4 if int(lookback_hours or 24) <= 48 else 5
    if hn_main > hn_cap:
        _issue(issues, "hn_over_cap", f"HN main items {hn_main} exceed cap {hn_cap}")

    source_counts = _source_distribution(digest)
    if main_count and source_counts:
        source, count = source_counts.most_common(1)[0]
        if count / main_count > 0.45:
            _issue(issues, "single_source_concentration", f"{source} accounts for {count}/{main_count}")

    stats = digest.source_statistics
    if (stats.chinese_count or 0) == 0 and not stats.chinese_shortage_reason:
        _issue(issues, "missing_chinese_shortage_reason", "chinese_count is 0 without explanation")
    if main_count and stats.no_published_at_selected_count / max(1, main_count) > 0.30:
        _issue(issues, "no_date_selected_high", "no-date selected candidate ratio is high")

    error_count = sum(1 for item in issues if item["severity"] == "error")
    warning_count = len(issues) - error_count
    status = "fail" if strict and issues else ("error" if error_count else ("warning" if warning_count else "pass"))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "strict": strict,
        "lookback_hours": lookback_hours,
        "summary": {
            "main_count": main_count,
            "appendix_count": appendix_count,
            "hn_main_count": hn_main,
            "weak_ai_relevance_count": weak_ai,
            "error_count": error_count,
            "warning_count": warning_count,
        },
        "issues": issues,
        "errors": [issue for issue in issues if issue["severity"] == "error"],
        "warnings": [issue for issue in issues if issue["severity"] != "error"],
    }


def save_quality_report(report: dict[str, Any], output_dir: str = "outputs/quality", run_id: str | None = None) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{run_id}_quality_report.json" if run_id else "quality_report.json"
    out_path = out_dir / name
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
