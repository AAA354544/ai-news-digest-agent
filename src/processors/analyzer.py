from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from src.config import AppConfig, load_app_config
from src.models import CandidateNews, DailyDigest, SourceStatistics
from src.processors.prompts import (
    build_digest_system_prompt,
    build_digest_user_prompt,
    extract_json_text,
    recommend_digest_shape,
)

CANONICAL_CATEGORIES = [
    "论文与科研进展",
    "模型与技术进展",
    "Agent 与 AI 工具",
    "开源项目与开发者生态",
    "产业与公司动态",
    "政策安全与风险",
]

_CATEGORY_ALIASES = {
    "科研与论文前沿": "论文与科研进展",
    "论文与科研前沿": "论文与科研进展",
    "研究论文": "论文与科研进展",
    "科研进展": "论文与科研进展",
    "技术与模型进展": "模型与技术进展",
    "模型技术进展": "模型与技术进展",
    "算力、芯片与基础设施": "模型与技术进展",
    "开源生态与开发者趋势": "开源项目与开发者生态",
    "开源生态与开发者生态": "开源项目与开发者生态",
    "开发者生态": "开源项目与开发者生态",
    "产业与公司动态": "产业与公司动态",
    "安全、政策与监管": "政策安全与风险",
    "政策、安全与监管": "政策安全与风险",
    "安全政策与风险": "政策安全与风险",
    "其他": "产业与公司动态",
}


def _extract_json_core(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw
    start_obj = raw.find("{")
    start_arr = raw.find("[")
    starts = [x for x in [start_obj, start_arr] if x != -1]
    if not starts:
        return raw
    start = min(starts)
    end_obj = raw.rfind("}")
    end_arr = raw.rfind("]")
    end = max(end_obj, end_arr)
    if end == -1 or end <= start:
        return raw[start:]
    return raw[start : end + 1]


def _remove_trailing_commas(text: str) -> str:
    # lightweight cleanup for common LLM JSON drift
    return re.sub(r",\s*([}\]])", r"\1", text)


def parse_llm_json_safely(json_text: str) -> dict:
    digest_date = date.today().isoformat()
    debug_dir = Path("data/digested")
    debug_dir.mkdir(parents=True, exist_ok=True)

    cleaned = _extract_json_core((json_text or "").strip())
    cleaned = _remove_trailing_commas(cleaned)

    try:
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError("Parsed JSON is not an object.")
        return payload
    except Exception as exc:
        failed_path = debug_dir / f"{digest_date}_llm_json_parse_failed.txt"
        failed_path.write_text(json_text or "", encoding="utf-8")
        print(f"[analyzer] json parse failed, raw json text saved: {failed_path}")
        print(f"[analyzer] parse error: {exc}")

        # second pass: stricter local cleanup (works even without extra deps)
        try:
            cleaned2 = _remove_trailing_commas(_extract_json_core(json_text or ""))
            payload = json.loads(cleaned2)
            if not isinstance(payload, dict):
                raise ValueError("Locally repaired JSON is not an object.")
            repaired_path = debug_dir / f"{digest_date}_llm_repaired_response.json"
            repaired_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[analyzer] local repaired json saved: {repaired_path}")
            return payload
        except Exception:
            pass

        # try optional robust repair
        try:
            from json_repair import repair_json

            repaired = repair_json(json_text or "")
            repaired_core = _remove_trailing_commas(_extract_json_core(repaired))
            payload = json.loads(repaired_core)
            if not isinstance(payload, dict):
                raise ValueError("Repaired JSON is not an object.")

            repaired_path = debug_dir / f"{digest_date}_llm_repaired_response.json"
            repaired_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[analyzer] repaired json saved: {repaired_path}")
            return payload
        except Exception as repair_exc:
            raise RuntimeError(
                f"Failed to parse LLM JSON even after repair. Please inspect debug file: {failed_path}"
            ) from repair_exc


def normalize_digest_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload

    if "source_statistics" not in payload or not isinstance(payload.get("source_statistics"), dict):
        payload["source_statistics"] = {
            "total_candidates": 0,
            "cleaned_candidates": 0,
            "selected_items": 0,
            "source_count": 0,
            "international_count": 0,
            "chinese_count": 0,
        }

    appendix = payload.get("appendix")
    if not isinstance(appendix, list):
        payload["appendix"] = []
    else:
        normalized_appendix: list[dict[str, str]] = []
        for item in appendix:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title") or "Untitled appendix item").strip() or "Untitled appendix item"

            link_value = item.get("link")
            if not link_value:
                link_value = item.get("url")
            if not link_value:
                links_value = item.get("links")
                if isinstance(links_value, list) and links_value:
                    link_value = links_value[0]
                elif isinstance(links_value, str):
                    link_value = links_value
            link = str(link_value or "").strip()

            source_value = item.get("source")
            if not source_value:
                source_value = item.get("source_name")
            if not source_value:
                source_names_value = item.get("source_names")
                if isinstance(source_names_value, list) and source_names_value:
                    source_value = ", ".join(str(x).strip() for x in source_names_value if str(x).strip())
                elif isinstance(source_names_value, str):
                    source_value = source_names_value
            source = str(source_value or "").strip()

            brief_value = (
                item.get("brief_summary")
                or item.get("summary")
                or item.get("description")
                or item.get("snippet")
                or ""
            )
            brief_summary = str(brief_value).strip()

            normalized_appendix.append(
                {
                    "title": title,
                    "link": link,
                    "source": source,
                    "brief_summary": brief_summary,
                }
            )
        payload["appendix"] = normalized_appendix

    main_digest = payload.get("main_digest")
    if not isinstance(main_digest, list):
        return payload

    # Already grouped format: [{"category_name": "...", "items": [...]}, ...]
    if all(isinstance(group, dict) and "category_name" in group and "items" in group for group in main_digest):
        grouped_items: dict[str, list[dict[str, Any]]] = {category: [] for category in CANONICAL_CATEGORIES}
        for group in main_digest:
            raw_category = str(group.get("category_name") or "").strip()
            category = _CATEGORY_ALIASES.get(raw_category, raw_category)
            if category not in grouped_items:
                category = "产业与公司动态"
            items = group.get("items")
            if isinstance(items, list):
                grouped_items[category].extend([item for item in items if isinstance(item, dict)])
        payload["main_digest"] = [
            {"category_name": category, "items": grouped_items[category]}
            for category in CANONICAL_CATEGORIES
        ]
        return payload

    # Flat list fallback: group by category_name/category, default to "其他".
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in main_digest:
        if not isinstance(item, dict):
            continue

        raw_category = str(item.get("category_name") or item.get("category") or "产业与公司动态").strip() or "产业与公司动态"
        category = _CATEGORY_ALIASES.get(raw_category, raw_category)
        if category not in CANONICAL_CATEGORIES:
            category = "产业与公司动态"

        links = item.get("links")
        if isinstance(links, str):
            links = [links]
        elif not isinstance(links, list):
            links = []

        tags = item.get("tags")
        if isinstance(tags, str):
            tags = [tags]
        elif not isinstance(tags, list):
            tags = []

        source_names = item.get("source_names")
        if isinstance(source_names, str):
            source_names = [source_names]
        elif not isinstance(source_names, list):
            source_names = []

        cleaned_item = {
            "title": str(item.get("title", "")).strip(),
            "links": [str(x).strip() for x in links if str(x).strip()],
            "tags": [str(x).strip() for x in tags if str(x).strip()],
            "summary": str(item.get("summary", "")).strip(),
            "why_it_matters": str(item.get("why_it_matters", "")).strip(),
            "insights": str(item.get("insights", "")).strip(),
            "source_names": [str(x).strip() for x in source_names if str(x).strip()],
        }

        if not cleaned_item["links"] and item.get("link"):
            cleaned_item["links"] = [str(item.get("link")).strip()]

        grouped.setdefault(category, []).append(cleaned_item)

    if grouped:
        payload["main_digest"] = [
            {"category_name": category, "items": grouped.get(category, [])}
            for category in CANONICAL_CATEGORIES
        ]
    else:
        payload["main_digest"] = [{"category_name": category, "items": []} for category in CANONICAL_CATEGORIES]

    return payload


def _normalize_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/").lower()


def _estimate_region_counts(candidates: list[CandidateNews]) -> tuple[int, int]:
    chinese_count = 0
    international_count = 0
    for c in candidates:
        region = (getattr(c, "region", "") or "").strip().lower()
        if region in {"chinese", "china", "zh", "cn"}:
            chinese_count += 1
        elif region:
            international_count += 1
    return international_count, chinese_count


def _dedupe_appendix_against_main(digest: DailyDigest) -> DailyDigest:
    main_links = {
        _normalize_url(link)
        for group in digest.main_digest
        for item in group.items
        for link in (item.links or [])
        if _normalize_url(link)
    }

    filtered = []
    seen_appendix_links: set[str] = set()
    for item in digest.appendix:
        link = _normalize_url(item.link)
        if link and (link in main_links or link in seen_appendix_links):
            continue
        if link:
            seen_appendix_links.add(link)
        filtered.append(item)
    digest.appendix = filtered
    return digest


def finalize_digest_statistics(
    digest: DailyDigest,
    stats_context: dict[str, int] | None = None,
    fallback_candidates: list[CandidateNews] | None = None,
) -> DailyDigest:
    """Program-side statistics normalization to reduce dependence on LLM output."""
    actual_selected_items = sum(len(group.items) for group in digest.main_digest)

    stats = digest.source_statistics if digest.source_statistics is not None else SourceStatistics()
    updates: dict[str, int] = {"selected_items": actual_selected_items}

    if stats_context:
        for key in ("total_candidates", "cleaned_candidates", "source_count", "international_count", "chinese_count"):
            if key in stats_context:
                updates[key] = int(stats_context[key])

    if fallback_candidates:
        if "cleaned_candidates" not in updates:
            updates["cleaned_candidates"] = len(fallback_candidates)
        if "total_candidates" not in updates:
            updates["total_candidates"] = len(fallback_candidates)
        if "source_count" not in updates:
            updates["source_count"] = len(
                {((c.source_name or "").strip().lower()) for c in fallback_candidates if (c.source_name or "").strip()}
            )
        if "international_count" not in updates or "chinese_count" not in updates:
            intl, zh = _estimate_region_counts(fallback_candidates)
            updates.setdefault("international_count", intl)
            updates.setdefault("chinese_count", zh)

    digest.source_statistics = stats.model_copy(update=updates)
    return digest


def analyze_candidates_with_llm(
    candidates: list[CandidateNews],
    config: AppConfig | None = None,
    stats_context: dict[str, int] | None = None,
) -> DailyDigest:
    from src.processors.llm_client import LLMClient

    cfg = config or load_app_config()
    digest_date = date.today().isoformat()
    system_prompt = build_digest_system_prompt()
    user_prompt = build_digest_user_prompt(
        candidates=candidates,
        topic=cfg.digest_topic,
        date=digest_date,
        min_items=cfg.main_digest_min_items,
        max_items=cfg.main_digest_max_items,
        lookback_hours=cfg.digest_lookback_hours,
    )

    client = LLMClient(config=cfg)
    raw_response = client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)

    try:
        json_text = extract_json_text(raw_response)
        payload = parse_llm_json_safely(json_text)
        payload = normalize_digest_payload(payload)
        if hasattr(DailyDigest, "model_validate"):
            digest = DailyDigest.model_validate(payload)
        else:
            digest = DailyDigest(**payload)
        digest = _dedupe_appendix_against_main(digest)
        return finalize_digest_statistics(digest, stats_context=stats_context, fallback_candidates=candidates)
    except Exception as exc:
        debug_dir = Path("data/digested")
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"{digest_date}_llm_raw_response.txt"
        debug_path.write_text(raw_response, encoding="utf-8")
        raise RuntimeError(
            f"Failed to parse/validate LLM digest JSON. Raw response saved to: {debug_path}"
        ) from exc


def save_digest(digest: DailyDigest, output_dir: str = "data/digested") -> Path:
    digest = _dedupe_appendix_against_main(digest)
    digest = finalize_digest_statistics(digest)
    cfg = load_app_config()
    shape = recommend_digest_shape(cfg.digest_lookback_hours)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{digest.date}_digest.json"
    out_path = out_dir / filename
    if hasattr(digest, "model_dump"):
        payload = digest.model_dump(mode="json")
    else:
        payload = digest.dict()
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    meta_path = out_dir / f"{digest.date}_digest_meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "lookback_hours": cfg.digest_lookback_hours,
                "report_window": shape["window_label"],
                "report_type": shape["report_type"],
                "recommended_main_range": f"{shape['main_min']}-{shape['main_max']}",
                "recommended_appendix_range": f"{shape['appendix_min']}-{shape['appendix_max']}",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_path
