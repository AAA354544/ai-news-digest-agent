from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def normalize_source_health_record(record: dict[str, Any]) -> dict[str, Any]:
    name = str(record.get("source_name") or record.get("name") or "").strip()
    source_type = str(record.get("source_type") or record.get("type") or "").strip()
    raw_count = int(record.get("raw_count") or record.get("count") or 0)
    cleaned_count = int(record.get("cleaned_count") or 0)
    normalized = {
        "source_name": name,
        "name": name,
        "source_type": source_type,
        "type": source_type,
        "region": str(record.get("region") or "").strip(),
        "language": str(record.get("language") or "").strip(),
        "status": str(record.get("status") or "empty").strip(),
        "raw_count": raw_count,
        "count": raw_count,
        "cleaned_count": cleaned_count,
        "error": str(record.get("error") or "").strip(),
        "duration_seconds": float(record.get("duration_seconds") or record.get("duration") or 0.0),
        "duration": float(record.get("duration_seconds") or record.get("duration") or 0.0),
        "endpoint": str(record.get("endpoint") or record.get("url_or_endpoint") or "").strip(),
    }
    return normalized


def save_source_health(records: list[dict[str, Any]], output_dir: str = "data/raw") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_source_health.json"
    normalized = [normalize_source_health_record(record) for record in records]
    out_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_latest_source_health(input_dir: str = "data/raw") -> list[dict[str, Any]]:
    base = Path(input_dir)
    files = sorted(base.glob("*_source_health.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return []
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [normalize_source_health_record(record) for record in data if isinstance(record, dict)]
        return []
    except Exception:
        return []


def update_latest_source_health_cleaned_counts(cleaned_counts: dict[str, int], input_dir: str = "data/raw") -> Path | None:
    base = Path(input_dir)
    files = sorted(base.glob("*_source_health.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    path = files[0]
    records = load_latest_source_health(input_dir=input_dir)
    for record in records:
        name = str(record.get("source_name") or record.get("name") or "").strip()
        record["cleaned_count"] = int(cleaned_counts.get(name, 0))
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
