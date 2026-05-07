from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.config import AppConfig, load_app_config
from src.models import CandidateNews, DailyDigest
from src.processors.prompts import (
    build_digest_system_prompt,
    build_digest_user_prompt,
    extract_json_text,
)


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

    main_digest = payload.get("main_digest")
    if not isinstance(main_digest, list):
        return payload

    # Already grouped format: [{"category_name": "...", "items": [...]}, ...]
    if all(isinstance(group, dict) and "category_name" in group and "items" in group for group in main_digest):
        return payload

    # Flat list fallback: group by category_name/category, default to "其他".
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in main_digest:
        if not isinstance(item, dict):
            continue

        category = str(item.get("category_name") or item.get("category") or "其他").strip() or "其他"

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
        payload["main_digest"] = [{"category_name": category, "items": items} for category, items in grouped.items()]
    else:
        payload["main_digest"] = [{"category_name": "其他", "items": []}]

    return payload


def analyze_candidates_with_llm(candidates: list[CandidateNews], config: AppConfig | None = None) -> DailyDigest:
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
    )

    client = LLMClient(config=cfg)
    raw_response = client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)

    try:
        json_text = extract_json_text(raw_response)
        payload = json.loads(json_text)
        payload = normalize_digest_payload(payload)
        if hasattr(DailyDigest, "model_validate"):
            digest = DailyDigest.model_validate(payload)
        else:
            digest = DailyDigest(**payload)
        return digest
    except Exception as exc:
        debug_dir = Path("data/digested")
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"{digest_date}_llm_raw_response.txt"
        debug_path.write_text(raw_response, encoding="utf-8")
        raise RuntimeError(
            f"Failed to parse/validate LLM digest JSON. Raw response saved to: {debug_path}"
        ) from exc


def save_digest(digest: DailyDigest, output_dir: str = "data/digested") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{digest.date}_digest.json"
    out_path = out_dir / filename
    if hasattr(digest, "model_dump"):
        payload = digest.model_dump(mode="json")
    else:
        payload = digest.dict()
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
