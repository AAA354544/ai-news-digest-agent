from __future__ import annotations

import os
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from src.config import get_enabled_sources, is_placeholder_value, load_app_config, load_sources_config
from src.generators.report_generator import link_label, load_latest_digest, split_title
from src.notifiers.recipients import (
    add_or_update_recipient,
    get_enabled_recipients,
    load_recipients,
    parse_email_list,
    remove_recipient,
    save_recipients,
    validate_email,
)
from src.pipeline import run_analyze_step, run_clean_step, run_email_step, run_fetch_step, run_report_step
from src.processors.prompts import recommend_llm_candidate_limit
from src.utils.source_health import load_latest_source_health

PROJECT_ROOT = Path(__file__).resolve().parent
MARKDOWN_DIR = PROJECT_ROOT / "outputs" / "markdown"
HTML_DIR = PROJECT_ROOT / "outputs" / "html"
DIGEST_DIR = PROJECT_ROOT / "data" / "digested"
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def _find_latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read_text(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _latest_report_paths() -> tuple[Path | None, Path | None]:
    md_path = _find_latest(MARKDOWN_DIR, "*-ai-news-digest.md")
    html_path = _find_latest(HTML_DIR, "*-ai-news-digest.html")
    return md_path, html_path


def _load_latest_digest_safe():
    try:
        return load_latest_digest(input_dir=str(DIGEST_DIR))
    except Exception:
        return None


def _selected_item_count(digest: Any | None) -> int | None:
    if digest is None:
        return None
    return sum(len(getattr(group, "items", []) or []) for group in getattr(digest, "main_digest", []) or [])


def _appendix_count(digest: Any | None) -> int | None:
    if digest is None:
        return None
    return len(getattr(digest, "appendix", []) or [])


def _source_count(digest: Any | None) -> int | None:
    if digest is None:
        return None
    stats = getattr(digest, "source_statistics", None)
    if stats is None:
        return None
    return getattr(stats, "source_count", None)


def _extract_counts_from_markdown(md_text: str | None) -> tuple[int | None, int | None]:
    if not md_text:
        return None, None
    selected = None
    appendix = None
    patterns = {
        "selected": [r"正文精选[:：]\s*(\d+)", r"Selected News Count[:：]\s*(\d+)", r"selected_items[:：]\s*(\d+)"],
        "appendix": [r"附录补充[:：]\s*(\d+)", r"Appendix Count[:：]\s*(\d+)"],
    }
    for pattern in patterns["selected"]:
        match = re.search(pattern, md_text)
        if match:
            selected = int(match.group(1))
            break
    for pattern in patterns["appendix"]:
        match = re.search(pattern, md_text)
        if match:
            appendix = int(match.group(1))
            break
    return selected, appendix


def _date_from_path(path: Path | None) -> str:
    if path is None:
        return "-"
    match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    if match:
        return match.group(1)
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def _flatten_digest_items(digest: Any | None) -> list[dict[str, Any]]:
    if digest is None:
        return []
    rows: list[dict[str, Any]] = []
    for group in getattr(digest, "main_digest", []) or []:
        category = getattr(group, "category_name", "") or "Other"
        for item in getattr(group, "items", []) or []:
            rows.append(
                {
                    "category": category,
                    "title": getattr(item, "title", ""),
                    "summary": getattr(item, "summary", ""),
                    "why_it_matters": getattr(item, "why_it_matters", ""),
                    "insights": getattr(item, "insights", ""),
                    "tags": getattr(item, "tags", []) or [],
                    "links": getattr(item, "links", []) or [],
                    "source_names": getattr(item, "source_names", []) or [],
                }
            )
    return rows


def _structured_digest_groups(digest: Any | None) -> list[dict[str, Any]]:
    if digest is None:
        return []
    groups: list[dict[str, Any]] = []
    for group in getattr(digest, "main_digest", []) or []:
        category = getattr(group, "category_name", "") or "Other"
        items: list[dict[str, Any]] = []
        for idx, item in enumerate(getattr(group, "items", []) or [], start=1):
            title = getattr(item, "title", "") or "Untitled"
            title_parts = split_title(title)
            source_names = getattr(item, "source_names", []) or []
            links = [
                {
                    "label": link_label(str(link), source_names) if str(link).strip() else f"Link {link_idx}",
                    "url": str(link).strip(),
                }
                for link_idx, link in enumerate(getattr(item, "links", []) or [], start=1)
                if str(link).strip()
            ]
            items.append(
                {
                    "index": idx,
                    "category": category,
                    "title": title,
                    "title_primary": title_parts["primary"],
                    "title_secondary": title_parts["secondary"],
                    "tags": getattr(item, "tags", []) or [],
                    "summary": getattr(item, "summary", "") or "",
                    "why_it_matters": getattr(item, "why_it_matters", "") or "",
                    "insights": getattr(item, "insights", "") or "",
                    "source_names": source_names,
                    "links": links,
                }
            )
        groups.append({"category": category, "items": items})
    return groups


def _markdown_preview(md_text: str | None, max_chars: int = 4500) -> str | None:
    if not md_text:
        return None
    return md_text[:max_chars] + ("\n\n..." if len(md_text) > max_chars else "")


def _markdown_signal_preview(md_text: str | None) -> str:
    if not md_text:
        return ""
    blocks: list[str] = []
    current: list[str] = []
    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        if line.startswith("#") or line.startswith("Generated by"):
            continue
        current.append(raw_line)
    if current:
        blocks.append("\n".join(current))
    return "\n\n".join(blocks[:3])


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return email
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = f"{local[:2]}***{local[-1:]}"
    return f"{masked_local}@{domain}"


def _email_ready(cfg: Any) -> bool:
    return not is_placeholder_value(cfg.sender_email) and not is_placeholder_value(cfg.smtp_auth_code)


def _source_health_rows() -> list[dict[str, Any]]:
    return load_latest_source_health(input_dir=str(RAW_DIR))


def _health_summary(health: list[dict[str, Any]]) -> dict[str, int]:
    ok = sum(1 for row in health if str(row.get("status", "")).lower() in {"ok", "success"})
    failed = sum(1 for row in health if str(row.get("status", "")).lower() not in {"ok", "success"})
    candidates = sum(int(row.get("count") or row.get("candidate_count") or 0) for row in health)
    return {"ok": ok, "failed": failed, "candidates": candidates}


def _load_all_sources() -> list[dict[str, Any]]:
    data = load_sources_config(str(PROJECT_ROOT / "config" / "sources.yaml"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [item for item in data.get("sources", []) if isinstance(item, dict)]
    return []


def _source_table_rows(enabled_only: bool = True) -> list[dict[str, Any]]:
    sources = _load_all_sources()
    health_by_name = {str(row.get("name", "")).strip().lower(): row for row in _source_health_rows()}
    rows: list[dict[str, Any]] = []
    for source in sources:
        if enabled_only and not bool(source.get("enabled", True)):
            continue
        name = str(source.get("name", ""))
        health = health_by_name.get(name.strip().lower(), {})
        status = health.get("status", "not checked")
        note = str(health.get("note") or health.get("last_error") or "")
        rows.append(
            {
                "source name": name,
                "type": source.get("type", ""),
                "category": source.get("category", ""),
                "region": source.get("region", ""),
                "enabled": bool(source.get("enabled", True)),
                "status": status,
                "candidate count": health.get("count", health.get("candidate_count", "")),
                "last error": "" if str(status).lower() in {"ok", "success"} else note,
            }
        )
    return rows


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #F6F7FB;
            --app-surface: #FFFFFF;
            --app-surface-2: #F9FAFB;
            --app-text: #111827;
            --app-muted: #64748B;
            --app-border: #E5E7EB;
            --app-brand: #4F46E5;
            --app-brand-soft: #EEF2FF;
            --app-success: #16A34A;
            --app-warning: #D97706;
            --app-danger: #DC2626;
            --app-shadow: 0 14px 34px rgba(15, 23, 42, 0.07);
            --app-sidebar-bg: #FFFFFF;
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --app-bg: #0B1020;
                --app-surface: #111827;
                --app-surface-2: #1F2937;
                --app-text: #F9FAFB;
                --app-muted: #CBD5E1;
                --app-border: #334155;
                --app-brand: #818CF8;
                --app-brand-soft: #312E81;
                --app-success: #4ADE80;
                --app-warning: #FBBF24;
                --app-danger: #F87171;
                --app-shadow: 0 18px 42px rgba(0, 0, 0, 0.28);
                --app-sidebar-bg: #0F172A;
            }
        }

        .stApp {
            background: var(--app-bg);
            color: var(--app-text);
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1180px;
        }
        .stApp, .stApp p, .stApp span, .stApp label, .stApp div {
            word-break: normal;
            overflow-wrap: break-word;
        }
        h1, h2, h3 {
            color: var(--app-text);
            letter-spacing: 0;
            word-break: normal;
            overflow-wrap: normal;
        }

        section[data-testid="stSidebar"] {
            background: var(--app-sidebar-bg);
            border-right: 1px solid var(--app-border);
        }
        section[data-testid="stSidebar"] * {
            color: var(--app-text);
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] label {
            color: var(--app-muted);
        }
        section[data-testid="stSidebar"] hr {
            border-color: var(--app-border);
        }

        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button {
            background: var(--app-surface);
            border: 1px solid var(--app-border);
            color: var(--app-text);
            min-height: 2.45rem;
            border-radius: 9px;
            font-weight: 650;
            word-break: normal;
            overflow-wrap: normal;
            white-space: normal;
            transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
        }
        div[data-testid="stButton"] button:hover,
        div[data-testid="stDownloadButton"] button:hover {
            background: var(--app-surface-2);
            border-color: var(--app-brand);
            color: var(--app-brand);
        }
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
            background: var(--app-brand);
            border: 1px solid var(--app-brand);
            color: #FFFFFF;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:hover {
            background: var(--app-brand);
            border-color: var(--app-brand);
            color: #FFFFFF;
            filter: brightness(1.06);
        }
        div[data-testid="stButton"] button[kind="secondary"],
        div[data-testid="stDownloadButton"] button,
        div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"],
        div[data-testid="stDownloadButton"] button[data-testid="stBaseButton-secondary"] {
            background: var(--app-surface);
            border: 1px solid var(--app-border);
            color: var(--app-text);
        }
        div[data-testid="stButton"] button[kind="secondary"]:hover,
        div[data-testid="stDownloadButton"] button:hover,
        div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"]:hover,
        div[data-testid="stDownloadButton"] button[data-testid="stBaseButton-secondary"]:hover {
            background: var(--app-surface-2);
            border-color: var(--app-brand);
            color: var(--app-brand);
        }
        div[data-testid="stButton"] button:disabled,
        div[data-testid="stDownloadButton"] button:disabled {
            background: var(--app-surface-2);
            border-color: var(--app-border);
            color: var(--app-muted);
            opacity: 0.65;
        }

        div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
            background: var(--app-surface);
            color: var(--app-text);
        }
        div[data-baseweb="radio"] label,
        div[data-baseweb="checkbox"] label {
            color: var(--app-text);
        }
        section[data-testid="stSidebar"] div[data-baseweb="radio"] label,
        section[data-testid="stSidebar"] div[data-baseweb="checkbox"] label,
        section[data-testid="stSidebar"] [role="radiogroup"] label,
        section[data-testid="stSidebar"] [role="radiogroup"] p {
            color: var(--app-text);
        }

        .hero-panel {
            background: linear-gradient(180deg, var(--app-surface), var(--app-surface-2));
            border: 1px solid var(--app-border);
            border-radius: 14px;
            padding: 28px 30px;
            box-shadow: var(--app-shadow);
            overflow: hidden;
        }
        .hero-kicker {
            color: var(--app-brand);
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .08em;
            margin-bottom: 8px;
        }
        .hero-title {
            color: var(--app-text);
            font-size: 36px;
            line-height: 1.12;
            font-weight: 760;
            margin: 0 0 10px 0;
        }
        .hero-copy {
            color: var(--app-muted);
            font-size: 15px;
            line-height: 1.7;
            max-width: 780px;
            margin: 0;
            word-break: normal;
            overflow-wrap: normal;
        }
        .metric-card, .soft-card {
            background: var(--app-surface);
            border: 1px solid var(--app-border);
            border-radius: 12px;
            padding: 16px 18px;
            min-height: 100px;
            box-shadow: var(--app-shadow);
            overflow: hidden;
        }
        .metric-label {
            color: var(--app-muted);
            font-size: 12px;
            font-weight: 650;
            text-transform: uppercase;
            letter-spacing: .04em;
            margin-bottom: 10px;
            white-space: nowrap;
            word-break: normal;
            overflow-wrap: normal;
        }
        .metric-value {
            color: var(--app-text);
            font-size: 26px;
            line-height: 1.1;
            font-weight: 760;
            margin-bottom: 8px;
            word-break: normal;
            overflow-wrap: break-word;
        }
        .metric-caption {
            color: var(--app-muted);
            font-size: 13px;
            line-height: 1.45;
            word-break: normal;
            overflow-wrap: break-word;
        }
        .section-label {
            color: var(--app-text);
            font-size: 17px;
            font-weight: 720;
            margin: 26px 0 10px 0;
        }
        .signal-card {
            background: var(--app-surface);
            border: 1px solid var(--app-border);
            border-radius: 12px;
            padding: 16px 18px;
            margin-bottom: 12px;
            box-shadow: var(--app-shadow);
        }
        .signal-meta { color: var(--app-brand); font-size: 12px; font-weight: 700; margin-bottom: 6px; }
        .signal-title {
            color: var(--app-text);
            font-size: 16px;
            font-weight: 720;
            margin-bottom: 8px;
            word-break: normal;
            overflow-wrap: break-word;
        }
        .signal-text { color: var(--app-muted); font-size: 14px; line-height: 1.65; }
        .path-text {
            color: var(--app-muted);
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 12px;
            word-break: break-all;
        }
        .empty-card {
            background: var(--app-surface);
            border: 1px dashed var(--app-border);
            border-radius: 12px;
            padding: 20px;
            color: var(--app-muted);
            line-height: 1.6;
            box-shadow: var(--app-shadow);
        }
        .empty-card strong { color: var(--app-text); }
        .status-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 4px 9px;
            background: var(--app-brand-soft);
            color: var(--app-brand);
            font-size: 12px;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] .status-pill {
            color: var(--app-brand);
            background: var(--app-brand-soft);
        }
        div[data-testid="stAlert"] {
            background: var(--app-surface-2);
            color: var(--app-text);
            border: 1px solid var(--app-border);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--app-border);
            border-radius: 12px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _set_nav(page: str) -> None:
    st.session_state["nav"] = page
    _mark_scroll_to_top_pending()


def _mark_scroll_to_top_pending() -> None:
    st.session_state["_scroll_to_top_pending"] = True
    st.session_state["_scroll_to_top_nonce"] = int(st.session_state.get("_scroll_to_top_nonce", 0)) + 1


def _page_top_anchor() -> None:
    st.markdown('<div id="app-page-top" style="height:0; overflow:hidden;"></div>', unsafe_allow_html=True)


def _scroll_to_top_once() -> None:
    if st.session_state.pop("_scroll_to_top_pending", False):
        nonce = int(st.session_state.get("_scroll_to_top_nonce", 0))
        components.html(
            """
            <script>
            (function () {
              const scrollNonce = __SCROLL_NONCE__;
              const topAnchor = "app-page-top";
              function tryHashScroll() {
                try {
                  const parentWindow = window.parent;
                  const base = parentWindow.location.pathname + parentWindow.location.search;
                  parentWindow.location.hash = "";
                  parentWindow.setTimeout(function () {
                    parentWindow.location.hash = topAnchor;
                    parentWindow.setTimeout(function () {
                      if (parentWindow.history && parentWindow.history.replaceState) {
                        parentWindow.history.replaceState(null, "", base);
                      }
                    }, 120);
                  }, 20);
                } catch (err) {}
              }

              function scrollTop() {
                let parentWindow = window.parent;
                let doc = null;
                try {
                  doc = parentWindow.document;
                } catch (err) {
                  tryHashScroll();
                  try { parentWindow.scrollTo(0, 0); } catch (innerErr) {}
                  return;
                }

                const directTargets = [
                  parentWindow,
                  doc.scrollingElement,
                  doc.documentElement,
                  doc.body,
                  doc.getElementById(topAnchor),
                  doc.querySelector('[data-testid="stAppViewContainer"]'),
                  doc.querySelector('[data-testid="stMain"]'),
                  doc.querySelector('[data-testid="stMainBlockContainer"]'),
                  doc.querySelector('section.main'),
                  doc.querySelector('.main'),
                  doc.querySelector('.stApp')
                ].filter(Boolean);

                for (const target of directTargets) {
                  try {
                    if (target.scrollTo) {
                      target.scrollTo({ top: 0, left: 0, behavior: "auto" });
                    }
                    if ("scrollTop" in target) {
                      target.scrollTop = 0;
                    }
                  } catch (err) {}
                }

                try {
                  const anchor = doc.getElementById(topAnchor);
                  if (anchor && anchor.scrollIntoView) {
                    anchor.scrollIntoView({ block: "start", inline: "nearest", behavior: "auto" });
                  }
                } catch (err) {}

                const scrollables = Array.from(doc.querySelectorAll("main, section, div"))
                  .filter((el) => {
                    const style = parentWindow.getComputedStyle(el);
                    const overflowY = style.overflowY || "";
                    return el.scrollHeight > el.clientHeight &&
                      ["auto", "scroll", "overlay"].includes(overflowY);
                  });
                for (const el of scrollables) {
                  try { el.scrollTop = 0; } catch (err) {}
                }
              }

              tryHashScroll();
              scrollTop();
              try { window.parent.requestAnimationFrame(scrollTop); } catch (err) {}
              [60, 180, 420, 900, 1400, 2200].forEach(function (delay) {
                try { window.parent.setTimeout(scrollTop, delay); } catch (err) {}
              });
              window.__aiDigestLastScrollNonce = scrollNonce;
            })();
            </script>
            """.replace("__SCROLL_NONCE__", str(nonce)),
            height=0,
        )


def _metric_card(label: str, value: str | int, caption: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value">{escape(str(value))}</div>
            <div class="metric-caption">{escape(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="empty-card">
            <strong>{escape(title)}</strong><br>
            {escape(body)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_downloads(md_path: Path | None, html_path: Path | None, key_prefix: str) -> None:
    md_text = _read_text(md_path)
    html_text = _read_text(html_path)
    col1, col2 = st.columns(2)
    with col1:
        if md_path and md_text is not None:
            st.download_button(
                "Download Markdown",
                data=md_text,
                file_name=md_path.name,
                mime="text/markdown",
                key=f"{key_prefix}_md",
                use_container_width=True,
            )
    with col2:
        if html_path and html_text is not None:
            st.download_button(
                "Download HTML",
                data=html_text,
                file_name=html_path.name,
                mime="text/html",
                key=f"{key_prefix}_html",
                use_container_width=True,
            )


def _send_to_recipients_ui(selected_emails: list[str]) -> tuple[bool, str]:
    if not selected_emails:
        return False, "No recipients selected."
    md_path, html_path = _latest_report_paths()
    if md_path is None or html_path is None:
        return False, "Latest reports not found in outputs/. Please generate a report first."
    try:
        result = run_email_step(recipients=selected_emails)
        return True, f"Email sent to {result.get('recipient_count', 0)} recipient(s)."
    except Exception as exc:
        return False, str(exc)


def _run_digest_with_status(*, send_email: bool, llm_limit: int, lookback_hours: int, topic: str) -> dict[str, Any]:
    os.environ["DIGEST_TOPIC"] = topic.strip() or "AI"
    os.environ["DIGEST_LOOKBACK_HOURS"] = str(lookback_hours)
    effective_llm_limit = recommend_llm_candidate_limit(lookback_hours, llm_limit)

    outputs: dict[str, Any] = {"effective_llm_limit": effective_llm_limit}
    status_box = st.empty()
    try:
        status_box.info("Fetching public sources...")
        outputs["raw_path"] = run_fetch_step()
        status_box.info("Cleaning and deduplicating candidates...")
        outputs["cleaned_path"] = run_clean_step()
        status_box.info(f"Analyzing up to {effective_llm_limit} candidate signals with the configured LLM...")
        outputs["digest_path"] = run_analyze_step(limit_for_test=effective_llm_limit)
        status_box.info("Rendering Markdown and HTML reports...")
        md_path, html_path = run_report_step()
        outputs["markdown_path"] = md_path
        outputs["html_path"] = html_path
        if send_email:
            status_box.info("Sending email newsletter...")
            outputs["email_result"] = run_email_step()
        status_box.success("Digest workflow completed.")
        return outputs
    except Exception:
        status_box.error("Digest workflow stopped before completion.")
        raise


def render_overview(cfg: Any) -> None:
    md_path, html_path = _latest_report_paths()
    md_text = _read_text(md_path)
    digest = _load_latest_digest_safe()
    enabled_source_count = len(get_enabled_sources())
    health = _source_health_rows()
    health_totals = _health_summary(health)

    selected = _selected_item_count(digest)
    appendix = _appendix_count(digest)
    if selected is None or appendix is None:
        md_selected, md_appendix = _extract_counts_from_markdown(md_text)
        selected = selected if selected is not None else md_selected
        appendix = appendix if appendix is not None else md_appendix

    st.markdown(
        """
        <div class="hero-panel">
            <div class="hero-kicker">Calm Intelligence Workspace</div>
            <div class="hero-title">AI News Digest Agent</div>
            <p class="hero-copy">
            A self-hosted AI intelligence workspace for tracking AI research, open-source projects, and industry signals.
            </p>
            <p class="hero-copy" style="margin-top: 8px;">
            生成结构化中文日报，支持 CLI、Streamlit、邮件和 GitHub Actions。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("Generate Digest", type="primary", use_container_width=True, on_click=_set_nav, args=("Run Digest",))
    with col2:
        st.button("View Latest Report", use_container_width=True, on_click=_set_nav, args=("Latest Report",))

    st.markdown('<div class="section-label">Workspace Summary</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _metric_card("Latest Report", _date_from_path(md_path), "Most recent report")
    with c2:
        _metric_card("Selected", selected if selected is not None else "-", "Main digest")
    with c3:
        _metric_card("Appendix", appendix if appendix is not None else "-", "Supplementary")
    with c4:
        _metric_card("Sources", enabled_source_count, "Enabled")
    with c5:
        _metric_card("Email", "Ready" if _email_ready(cfg) else "Setup needed", "SMTP status")

    st.markdown('<div class="section-label">Today\'s Top Signals</div>', unsafe_allow_html=True)
    signals = _flatten_digest_items(digest)[:3]
    if signals:
        for idx, item in enumerate(signals, start=1):
            summary = item.get("summary") or ""
            why_it_matters = item.get("why_it_matters") or ""
            summary_html = f'<div class="signal-text">{escape(summary)}</div>' if summary else ""
            why_html = (
                f'<div class="signal-text" style="margin-top: 8px;"><strong>Why it matters:</strong> '
                f"{escape(why_it_matters)}</div>"
                if why_it_matters
                else ""
            )
            st.markdown(
                f"""
                <div class="signal-card">
                    <div class="signal-meta">{escape(str(idx))} / {escape(item.get("category") or "Other")}</div>
                    <div class="signal-title">{escape(item.get("title") or "Untitled")}</div>
                    {summary_html}
                    {why_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        fallback = _markdown_signal_preview(md_text)
        if fallback:
            st.markdown(fallback)
        else:
            _empty_state("No signal preview yet", "Generate a digest to populate the daily top signals.")

    st.markdown('<div class="section-label">Source Health Snapshot</div>', unsafe_allow_html=True)
    if health:
        c1, c2, c3 = st.columns(3)
        with c1:
            _metric_card("Healthy sources", health_totals["ok"], "Latest source health file")
        with c2:
            _metric_card("Needs attention", health_totals["failed"], "Failed or unchecked rows")
        with c3:
            _metric_card("Candidate count", health_totals["candidates"], "Fetched candidates")
    else:
        _empty_state("No source health file found", "Run the fetch step or full pipeline to create a health snapshot.")

    st.markdown('<div class="section-label">Latest Digest Preview</div>', unsafe_allow_html=True)
    if md_path and md_text:
        st.markdown(f'<div class="path-text">{escape(str(md_path))}</div>', unsafe_allow_html=True)
        _render_downloads(md_path, html_path, "overview_latest")
        st.markdown(_markdown_preview(md_text) or "")
    else:
        _empty_state("No report output found", "Use Run Digest or the report-only test to generate Markdown and HTML outputs.")


def render_run_digest(cfg: Any) -> None:
    st.header("Run Digest")
    st.caption("Run the existing pipeline deliberately. Email is sent only by the explicit email action.")

    with st.container():
        st.subheader("Basic")
        topic = st.text_input("Topic", value=cfg.digest_topic)
        send_email = st.checkbox("Send email after generating the digest", value=False)
        llm_limit = st.slider(
            "Configured LLM candidate floor",
            min_value=5,
            max_value=max(120, int(cfg.max_llm_candidates)),
            value=min(max(120, int(cfg.max_llm_candidates)), max(5, int(cfg.max_llm_candidates))),
            step=1,
        )

    with st.expander("Advanced", expanded=False):
        lookback_hours = st.number_input(
            "Lookback hours",
            min_value=1,
            max_value=168,
            value=int(cfg.digest_lookback_hours),
            step=1,
        )
        show_debug = st.checkbox("Show output paths after run", value=True)
        st.caption("No additional debug pipeline flags are currently available; this panel reuses existing config fields.")
        if int(lookback_hours) <= 24:
            st.caption("Recommended output: 12-15 main items, 5-10 appendix items.")
        elif int(lookback_hours) <= 48:
            st.caption("Recommended output: 15-18 main items, 10-18 appendix items.")
        elif int(lookback_hours) <= 72:
            st.caption("Recommended output: 18-22 main items, 15-25 appendix items.")
        else:
            st.caption("Recommended output: 25-35 main items, 30-50 appendix items. Consider a weekly report format.")
        effective_candidate_limit = recommend_llm_candidate_limit(int(lookback_hours), int(llm_limit))
        st.caption(f"Effective LLM candidate pool for this run: {effective_candidate_limit}.")

    col1, col2, col3 = st.columns(3)
    with col1:
        generate = st.button("Generate Digest", type="primary", use_container_width=True)
    with col2:
        generate_send = st.button("Generate & Send Email", type="primary", use_container_width=True)
    with col3:
        lightweight = st.button("Lightweight Test", use_container_width=True)

    if generate or generate_send:
        should_send = bool(generate_send or send_email)
        if should_send and not _email_ready(cfg):
            st.warning("SMTP is not fully configured. The pipeline can generate the digest, but email sending may fail.")
        try:
            outputs = _run_digest_with_status(
                send_email=should_send,
                llm_limit=int(llm_limit),
                lookback_hours=int(lookback_hours),
                topic=topic,
            )
            if show_debug:
                st.json({key: str(value) for key, value in outputs.items()})
        except Exception as exc:
            with st.expander("Error details", expanded=True):
                st.exception(exc)

    if lightweight:
        try:
            os.environ["DIGEST_TOPIC"] = topic.strip() or "AI"
            os.environ["DIGEST_LOOKBACK_HOURS"] = str(int(lookback_hours))
            with st.spinner("Rendering reports from the latest digested JSON..."):
                md_path, html_path = run_report_step()
            st.success("Report rendering test completed.")
            st.write(f"Markdown: {md_path}")
            st.write(f"HTML: {html_path}")
        except Exception as exc:
            st.error("Report rendering test failed.")
            with st.expander("Error details", expanded=True):
                st.exception(exc)


def render_latest_report() -> None:
    st.header("Latest Report")
    md_path, html_path = _latest_report_paths()
    md_text = _read_text(md_path)
    html_text = _read_text(html_path)
    digest = _load_latest_digest_safe()

    if not md_path and not html_path:
        _empty_state("No report found", "Generate a digest or run Lightweight Test to render the latest digested JSON.")
        st.button("Go to Run Digest", type="primary", use_container_width=True, on_click=_set_nav, args=("Run Digest",))
        return

    st.subheader("Files")
    st.markdown(f'<div class="path-text">Markdown: {escape(str(md_path or "-"))}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="path-text">HTML: {escape(str(html_path or "-"))}</div>', unsafe_allow_html=True)
    _render_downloads(md_path, html_path, "latest_report")

    selected = _selected_item_count(digest)
    appendix = _appendix_count(digest)
    source_count = _source_count(digest)
    if selected is None or appendix is None:
        md_selected, md_appendix = _extract_counts_from_markdown(md_text)
        selected = selected if selected is not None else md_selected
        appendix = appendix if appendix is not None else md_appendix

    c1, c2, c3 = st.columns(3)
    with c1:
        _metric_card("Selected", selected if selected is not None else "-", "Main digest")
    with c2:
        _metric_card("Appendix", appendix if appendix is not None else "-", "Supplementary")
    with c3:
        _metric_card("Sources", source_count if source_count is not None else "-", "Unique sources")

    tab_structured, tab_markdown, tab_html = st.tabs(["Structured View", "Full Markdown", "HTML Preview"])

    with tab_structured:
        groups = _structured_digest_groups(digest)
        non_empty_groups = [group for group in groups if group["items"]]
        if non_empty_groups:
            for group in non_empty_groups:
                st.subheader(group["category"])
                for item in group["items"]:
                    st.markdown(f"#### {item['index']}. {item['title_primary']}")
                    if item["title_secondary"]:
                        st.markdown(item["title_secondary"])
                    st.caption(item["category"])
                    if item["tags"]:
                        st.markdown("**Tags:** " + ", ".join(str(tag) for tag in item["tags"]))
                    if item["summary"]:
                        st.markdown(f"**Summary:** {item['summary']}")
                    if item["why_it_matters"]:
                        st.markdown(f"**Why it matters:** {item['why_it_matters']}")
                    if item["insights"]:
                        st.markdown(f"**Insight:** {item['insights']}")
                    if item["source_names"]:
                        st.markdown("**Source:** " + ", ".join(str(source) for source in item["source_names"]))
                    if item["links"]:
                        st.markdown(
                            "**Links:** "
                            + " ".join(f"[{link['label']}]({link['url']})" for link in item["links"])
                        )
                    st.divider()
        else:
            _empty_state("Structured view unavailable", "The latest digest JSON could not be loaded.")

        appendix_items = getattr(digest, "appendix", []) or [] if digest is not None else []
        if appendix_items:
            st.subheader("Appendix")
            for idx, item in enumerate(appendix_items, start=1):
                title_parts = split_title(getattr(item, "title", "") or "Untitled")
                link = getattr(item, "link", "") or ""
                source = getattr(item, "source", "") or ""
                brief = getattr(item, "brief_summary", "") or ""
                label = link_label(link, [source]) if link else ""
                st.markdown(f"{idx}. **{title_parts['primary']}**")
                if title_parts["secondary"]:
                    st.markdown(title_parts["secondary"])
                if source:
                    st.markdown(f"   - Source: {source}")
                if brief:
                    st.markdown(f"   - Summary: {brief}")
                if link:
                    st.markdown(f"   - Link: [{label}]({link})")
                continue
                if link:
                    st.markdown(f"- [{title}]({link}) · {source}  \n  {brief}")
                else:
                    st.markdown(f"- **{title}** · {source}  \n  {brief}")

    with tab_markdown:
        if md_text:
            st.markdown(md_text)
        else:
            _empty_state("Markdown unavailable", "The latest Markdown file could not be found or read.")

    with tab_html:
        if html_text:
            components.html(html_text, height=900, scrolling=True)
        else:
            _empty_state("HTML preview unavailable", "The latest HTML file could not be found or read.")


def render_history() -> None:
    st.header("History")
    markdown_files = list(MARKDOWN_DIR.glob("*-ai-news-digest.md"))
    html_files = list(HTML_DIR.glob("*-ai-news-digest.html"))
    files = sorted(markdown_files + html_files, key=lambda p: p.stat().st_mtime, reverse=True)

    if not files:
        _empty_state("No historical reports found", "Generated Markdown and HTML reports will appear here.")
        return

    labels = [
        f"{path.name} | {path.suffix[1:].upper()} | {datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}"
        for path in files
    ]
    selected_label = st.selectbox("Select a report", labels)
    selected_path = files[labels.index(selected_label)]
    content = _read_text(selected_path) or ""

    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f'<div class="path-text">{escape(str(selected_path))}</div>', unsafe_allow_html=True)
    with c2:
        st.download_button(
            "Download Selected File",
            data=content,
            file_name=selected_path.name,
            mime="text/html" if selected_path.suffix == ".html" else "text/markdown",
            use_container_width=True,
        )

    if selected_path.suffix == ".html":
        components.html(content, height=720, scrolling=True)
    else:
        st.markdown(_markdown_preview(content, max_chars=8000) or "")


def render_sources() -> None:
    st.header("Sources")
    enabled_sources = get_enabled_sources()
    health = _source_health_rows()
    health_totals = _health_summary(health)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card("Enabled sources", len(enabled_sources), "Configured in sources.yaml")
    with c2:
        _metric_card("Healthy", health_totals["ok"] if health else "-", "Latest health status")
    with c3:
        _metric_card("Failed", health_totals["failed"] if health else "-", "Latest health status")
    with c4:
        _metric_card("Candidates", health_totals["candidates"] if health else "-", "Latest fetch count")

    st.subheader("Enabled Source Inventory")
    rows = _source_table_rows(enabled_only=True)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        _empty_state("No enabled sources", "Enable at least one source in config/sources.yaml.")

    st.subheader("Source Health")
    if health:
        st.dataframe(health, use_container_width=True, hide_index=True)
    else:
        _empty_state("No source health data", "Run the fetch step or full pipeline to generate data/raw/*_source_health.json.")


def render_recipients() -> None:
    st.header("Recipients")
    st.caption("Local recipient data stays in data/recipients.local.json and should not be committed.")

    try:
        recipients = load_recipients()
    except Exception as exc:
        st.error(f"Failed to load recipients: {exc}")
        recipients = []

    st.subheader("Local Recipients")
    if recipients:
        st.dataframe(
            [
                {
                    "name": r.get("name", ""),
                    "email": _mask_email(str(r.get("email", ""))),
                    "groups": ",".join(r.get("groups", [])),
                    "enabled": bool(r.get("enabled", True)),
                    "note": r.get("note", ""),
                }
                for r in recipients
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        _empty_state("No local recipients", "Add a recipient below or send to temporary addresses.")

    st.subheader("Add or Update Recipient")
    c1, c2 = st.columns(2)
    with c1:
        name_input = st.text_input("Name", key="recipient_name")
        email_input = st.text_input("Email", key="recipient_email")
    with c2:
        groups_input = st.text_input("Groups (comma separated)", value="default", key="recipient_groups")
        enabled_input = st.checkbox("Enabled", value=True, key="recipient_enabled")
    note_input = st.text_input("Note", key="recipient_note")

    if st.button("Save Recipient", type="primary", use_container_width=True):
        email_norm = email_input.strip().lower()
        if not validate_email(email_norm):
            st.error("Invalid email format. Example: someone@example.com")
        else:
            groups = [g.strip() for g in groups_input.split(",") if g.strip()]
            recipients = add_or_update_recipient(
                recipients,
                email=email_norm,
                name=name_input,
                groups=groups,
                enabled=enabled_input,
                note=note_input,
            )
            save_recipients(recipients)
            st.success("Recipient saved.")
            st.rerun()

    st.subheader("Remove Recipient")
    all_emails = [str(r.get("email", "")) for r in recipients if r.get("email")]
    if all_emails:
        selected_remove = st.selectbox("Select email to remove", options=all_emails, format_func=_mask_email)
        if st.button("Delete Recipient", use_container_width=True):
            recipients = remove_recipient(recipients, selected_remove)
            save_recipients(recipients)
            st.success(f"Removed {_mask_email(selected_remove)}.")
            st.rerun()
    else:
        st.info("No recipients available to delete.")

    st.subheader("Send Latest Digest to Selected Recipients")
    enabled_emails = get_enabled_recipients(recipients)
    selected_emails = st.multiselect("Enabled recipients", options=enabled_emails, format_func=_mask_email)
    st.info(f"You are about to send the latest digest to {len(selected_emails)} recipient(s).")
    confirm_selected = st.checkbox("Confirm selected-recipient send", key="confirm_selected_send")
    if st.button(
        "Send latest digest to selected recipients",
        disabled=not selected_emails or not confirm_selected,
        use_container_width=True,
    ):
        ok, msg = _send_to_recipients_ui(selected_emails)
        st.success(msg) if ok else st.error(msg)

    st.subheader("Send Latest Digest to Temporary Emails")
    temp_text = st.text_area("Temporary emails (comma / semicolon / newline separated)", key="temp_emails")
    parsed_preview = parse_email_list(temp_text)
    valid_preview = [email for email in parsed_preview if validate_email(email)]
    st.info(f"You are about to send the latest digest to {len(valid_preview)} recipient(s).")
    confirm_temp = st.checkbox("Confirm temporary-recipient send", key="confirm_temp_send")
    c1, c2 = st.columns([1, 1])
    with c1:
        save_temp = st.checkbox("Save these recipients", value=False, key="save_temp_recipients")
    with c2:
        temp_group = st.text_input("Group for saved temporary recipients", value="temporary", key="temp_group")

    if st.button(
        "Send latest digest to temporary emails",
        disabled=not valid_preview or not confirm_temp,
        use_container_width=True,
    ):
        invalid = [email for email in parsed_preview if not validate_email(email)]
        if invalid:
            st.error(f"Invalid emails: {', '.join(invalid)}")
        elif not valid_preview:
            st.error("No valid temporary emails found.")
        else:
            ok, msg = _send_to_recipients_ui(valid_preview)
            if ok:
                st.success(msg)
                if save_temp:
                    for email in valid_preview:
                        recipients = add_or_update_recipient(
                            recipients,
                            email=email,
                            name="",
                            groups=[temp_group.strip() or "temporary"],
                            enabled=True,
                            note="saved from streamlit temporary send",
                        )
                    save_recipients(recipients)
                    st.success("Temporary recipients saved to local list.")
                    st.rerun()
            else:
                st.error(msg)


def main() -> None:
    cfg = load_app_config()
    st.set_page_config(page_title="AI News Digest Agent", page_icon="AI", layout="wide")
    _inject_css()
    _page_top_anchor()

    pages = ["Overview", "Run Digest", "Latest Report", "History", "Sources", "Recipients"]
    if "nav" not in st.session_state:
        st.session_state["nav"] = "Overview"

    st.sidebar.title("AI Digest")
    st.sidebar.caption("Daily intelligence workspace")
    selected_page = st.sidebar.radio(
        "Navigation",
        pages,
        index=pages.index(st.session_state.get("nav", "Overview")),
        key="nav",
    )
    if st.session_state.get("_last_rendered_nav") != selected_page:
        _mark_scroll_to_top_pending()
        st.session_state["_last_rendered_nav"] = selected_page

    st.sidebar.markdown("---")
    st.sidebar.markdown('<span class="status-pill">Runtime</span>', unsafe_allow_html=True)
    st.sidebar.write(f"Topic: **{cfg.digest_topic}**")
    st.sidebar.write(f"Lookback: **{cfg.digest_lookback_hours}h**")
    st.sidebar.write(
        f"LLM pool: **{recommend_llm_candidate_limit(cfg.digest_lookback_hours, cfg.max_llm_candidates)}**"
    )
    st.sidebar.write(f"Email: **{'ready' if _email_ready(cfg) else 'setup needed'}**")

    if selected_page == "Overview":
        render_overview(cfg)
    elif selected_page == "Run Digest":
        render_run_digest(cfg)
    elif selected_page == "Latest Report":
        render_latest_report()
    elif selected_page == "History":
        render_history()
    elif selected_page == "Sources":
        render_sources()
    elif selected_page == "Recipients":
        render_recipients()

    _scroll_to_top_once()


if __name__ == "__main__":
    main()
