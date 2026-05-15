from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config import load_app_config
from src.models import DailyDigest
from src.processors.analyzer import normalize_digest_payload
from src.processors.prompts import recommend_digest_shape


def _selected_item_count(digest: DailyDigest) -> int:
    return sum(len(group.items) for group in digest.main_digest)


def load_latest_digest(input_dir: str = "data/digested") -> DailyDigest:
    base = Path(input_dir)
    files = sorted(base.glob("*_digest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError("No digest file found. Please run: python tests/manual_test_llm.py")

    payload = normalize_digest_payload(json.loads(files[0].read_text(encoding="utf-8")))
    if hasattr(DailyDigest, "model_validate"):
        return DailyDigest.model_validate(payload)
    return DailyDigest(**payload)


def _build_env(template_dir: str = "templates") -> Environment:
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=False, trim_blocks=True, lstrip_blocks=True)
    env.globals["split_title"] = split_title
    env.globals["link_label"] = link_label
    return env


def split_title(title: str) -> dict[str, str]:
    raw = (title or "").strip()
    for separator in ("｜", "|"):
        if separator in raw:
            primary, secondary = raw.split(separator, 1)
            return {"primary": primary.strip(), "secondary": secondary.strip()}
    return {"primary": raw, "secondary": ""}


def link_label(link: str, source_names: list[str] | None = None) -> str:
    value = (link or "").lower()
    sources = " ".join(source_names or []).lower()
    if "arxiv.org" in value or "arxiv" in sources:
        return "arXiv"
    if "github.com" in value or "github" in sources:
        return "GitHub 仓库"
    if "openai.com" in value or "openai" in sources:
        return "OpenAI 原文"
    if "anthropic.com" in value or "anthropic" in sources:
        return "Anthropic 原文"
    if "microsoft.com" in value or "microsoft" in sources:
        return "Microsoft 原文"
    if "nvidia.com" in value or "nvidia" in sources:
        return "NVIDIA 原文"
    if "huggingface.co" in value or "hugging face" in sources:
        return "Hugging Face 原文"
    if "news.ycombinator.com" in value or "hacker news" in sources:
        return "社区讨论"
    if any(domain in value for domain in ("techcrunch.com", "technologyreview.com", "venturebeat.com")):
        return "媒体报道"
    return "阅读原文"


def _report_context(digest: DailyDigest) -> dict[str, object]:
    cfg = load_app_config()
    shape = recommend_digest_shape(cfg.digest_lookback_hours)
    context = {
        "lookback_hours": cfg.digest_lookback_hours,
        "report_window": shape["window_label"],
        "report_type": shape["report_type"],
        "recommended_main_range": f"{shape['main_min']}-{shape['main_max']}",
        "recommended_appendix_range": f"{shape['appendix_min']}-{shape['appendix_max']}",
    }
    meta_path = Path("data/digested") / f"{digest.date}_digest_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                context.update({key: value for key, value in meta.items() if value is not None})
        except Exception:
            pass
    return context


def render_markdown_report(digest: DailyDigest, template_dir: str = "templates") -> str:
    env = _build_env(template_dir)
    template = env.get_template("digest.md.jinja")
    return template.render(digest=digest, selected_count=_selected_item_count(digest), **_report_context(digest))


def render_html_report(digest: DailyDigest, template_dir: str = "templates") -> str:
    env = _build_env(template_dir)
    template = env.get_template("digest.html.jinja")
    return template.render(digest=digest, selected_count=_selected_item_count(digest), **_report_context(digest))


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
