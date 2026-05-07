from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models import DailyDigest


def _selected_item_count(digest: DailyDigest) -> int:
    return sum(len(group.items) for group in digest.main_digest)


def load_latest_digest(input_dir: str = "data/digested") -> DailyDigest:
    base = Path(input_dir)
    files = sorted(base.glob("*_digest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError("No digest file found. Please run: python tests/manual_test_llm.py")

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    if hasattr(DailyDigest, "model_validate"):
        return DailyDigest.model_validate(payload)
    return DailyDigest(**payload)


def _build_env(template_dir: str = "templates") -> Environment:
    return Environment(loader=FileSystemLoader(template_dir), autoescape=False, trim_blocks=True, lstrip_blocks=True)


def render_markdown_report(digest: DailyDigest, template_dir: str = "templates") -> str:
    env = _build_env(template_dir)
    template = env.get_template("digest.md.jinja")
    return template.render(digest=digest, selected_count=_selected_item_count(digest))


def render_html_report(digest: DailyDigest, template_dir: str = "templates") -> str:
    env = _build_env(template_dir)
    template = env.get_template("digest.html.jinja")
    return template.render(digest=digest, selected_count=_selected_item_count(digest))


def save_report_files(
    digest: DailyDigest, markdown_text: str, html_text: str, output_base_dir: str = "outputs"
) -> tuple[Path, Path]:
    out_base = Path(output_base_dir)
    md_dir = out_base / "markdown"
    html_dir = out_base / "html"
    md_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)

    md_path = md_dir / f"{digest.date}-ai-news-digest.md"
    html_path = html_dir / f"{digest.date}-ai-news-digest.html"

    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    return md_path, html_path


def generate_reports_from_latest_digest() -> tuple[Path, Path]:
    digest = load_latest_digest()
    markdown_text = render_markdown_report(digest)
    html_text = render_html_report(digest)
    return save_report_files(digest, markdown_text, html_text)
