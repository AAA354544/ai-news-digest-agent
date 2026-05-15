from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def append_run_index(entry: dict[str, Any], index_path: str = "data/index.json", keep: int = 100) -> Path:
    path = Path(index_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                existing = [item for item in payload if isinstance(item, dict)]
        except Exception:
            existing = []

    normalized = dict(entry)
    normalized.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    existing.insert(0, normalized)
    path.write_text(json.dumps(existing[:keep], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_run_index(index_path: str = "data/index.json") -> list[dict[str, Any]]:
    path = Path(index_path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
    except Exception:
        return []
