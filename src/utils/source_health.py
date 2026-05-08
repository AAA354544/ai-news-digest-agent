from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def save_source_health(records: list[dict[str, Any]], output_dir: str = "data/raw") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_source_health.json"
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_latest_source_health(input_dir: str = "data/raw") -> list[dict[str, Any]]:
    base = Path(input_dir)
    files = sorted(base.glob("*_source_health.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return []
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []
