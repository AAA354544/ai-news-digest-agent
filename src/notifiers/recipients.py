from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_RECIPIENTS_PATH = Path("data/recipients.local.json")


def normalize_email(email: str) -> str:
    """Normalize email text for consistent storage and comparison."""
    return (email or "").strip().lower()


def validate_email(email: str) -> bool:
    """Perform basic email format validation."""
    value = normalize_email(email)
    if "@" not in value:
        return False
    if value.count("@") != 1:
        return False
    local, domain = value.split("@", 1)
    if not local or not domain or "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith("."):
        return False
    return True


def parse_email_list(text: str) -> list[str]:
    """Parse and deduplicate emails from comma/semicolon/newline separated text."""
    if not text:
        return []
    tokens = re.split(r"[,;\n\r]+", text)
    emails: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        email = normalize_email(token)
        if not email or email in seen:
            continue
        seen.add(email)
        emails.append(email)
    return emails


def load_recipients(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load local recipients list; return empty list when file is missing."""
    target = Path(path) if path else DEFAULT_RECIPIENTS_PATH
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Recipients file format error in '{target}'. Please fix JSON syntax. Detail: {exc}"
        ) from exc
    if not isinstance(payload, list):
        raise ValueError(f"Recipients file '{target}' must contain a JSON list.")
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        email = normalize_email(str(item.get("email", "")))
        groups_raw = item.get("groups", [])
        groups = groups_raw if isinstance(groups_raw, list) else []
        normalized.append(
            {
                "name": str(item.get("name", "")).strip(),
                "email": email,
                "groups": [str(g).strip() for g in groups if str(g).strip()],
                "enabled": bool(item.get("enabled", True)),
                "note": str(item.get("note", "")).strip(),
            }
        )
    return normalized


def save_recipients(recipients: list[dict[str, Any]], path: str | Path | None = None) -> Path:
    """Save recipients list to local JSON file."""
    target = Path(path) if path else DEFAULT_RECIPIENTS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(recipients, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def get_enabled_recipients(recipients: list[dict[str, Any]], group: str | None = None) -> list[str]:
    """Return enabled recipient emails, optionally filtered by group."""
    out: list[str] = []
    seen: set[str] = set()
    target_group = (group or "").strip().lower()
    for r in recipients:
        email = normalize_email(str(r.get("email", "")))
        if not email or email in seen or not bool(r.get("enabled", True)):
            continue
        groups = [str(g).strip().lower() for g in (r.get("groups") or [])]
        if target_group and target_group not in groups:
            continue
        seen.add(email)
        out.append(email)
    return out


def add_or_update_recipient(
    recipients: list[dict[str, Any]],
    *,
    email: str,
    name: str = "",
    groups: list[str] | None = None,
    enabled: bool = True,
    note: str = "",
) -> list[dict[str, Any]]:
    """Add a recipient or update existing one by email."""
    normalized_email = normalize_email(email)
    if not validate_email(normalized_email):
        raise ValueError(f"Invalid email format: '{email}'.")
    cleaned_groups = [str(g).strip() for g in (groups or []) if str(g).strip()]
    for item in recipients:
        if normalize_email(str(item.get("email", ""))) == normalized_email:
            item["name"] = (name or "").strip()
            item["groups"] = cleaned_groups
            item["enabled"] = bool(enabled)
            item["note"] = (note or "").strip()
            item["email"] = normalized_email
            return recipients
    recipients.append(
        {
            "name": (name or "").strip(),
            "email": normalized_email,
            "groups": cleaned_groups,
            "enabled": bool(enabled),
            "note": (note or "").strip(),
        }
    )
    return recipients


def remove_recipient(recipients: list[dict[str, Any]], email: str) -> list[dict[str, Any]]:
    """Remove recipient by email."""
    normalized_email = normalize_email(email)
    return [r for r in recipients if normalize_email(str(r.get("email", ""))) != normalized_email]
