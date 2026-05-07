from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.config import load_app_config
from src.pipeline import run_email_step, run_full_pipeline, run_report_step

PROJECT_ROOT = Path(__file__).resolve().parent


def _find_latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_markdown_preview() -> tuple[str | None, Path | None]:
    md_dir = PROJECT_ROOT / "outputs" / "markdown"
    latest = _find_latest(md_dir, "*-ai-news-digest.md")
    if latest is None:
        return None, None
    return latest.read_text(encoding="utf-8"), latest


def _latest_html_path() -> Path | None:
    return _find_latest(PROJECT_ROOT / "outputs" / "html", "*-ai-news-digest.html")


def _list_history_markdown_files() -> list[Path]:
    md_dir = PROJECT_ROOT / "outputs" / "markdown"
    return sorted(md_dir.glob("*-ai-news-digest.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def main() -> None:
    cfg = load_app_config()

    st.set_page_config(page_title="AI News Digest Agent", page_icon="📰", layout="wide")
    st.title("AI News Digest Agent")
    st.caption("MVP: Multi-source fetch + LLM analysis + Markdown/HTML report + optional email sending")

    st.markdown(
        """
- Multi-source fetch
- LLM analysis
- Markdown/HTML report
- Optional email sending
"""
    )

    with st.sidebar:
        st.header("Run Config")
        topic_input = st.text_input("Topic", value=cfg.digest_topic)
        llm_limit = st.slider("LLM candidate limit", min_value=5, max_value=50, value=5, step=1)
        send_email_flag = st.checkbox("Send email after full pipeline", value=False)
        st.caption("Note: sending email is always explicit and optional.")

    if topic_input and topic_input != cfg.digest_topic:
        st.info("Current run will still use .env topic unless you update DIGEST_TOPIC in .env.")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Run Full Pipeline", use_container_width=True):
            try:
                outputs = run_full_pipeline(send_email=send_email_flag, llm_candidate_limit=llm_limit)
                st.success("Pipeline completed.")
                st.json({k: str(v) if v is not None else None for k, v in outputs.items()})
            except Exception as exc:
                st.error("Pipeline failed.")
                with st.expander("Error details"):
                    st.exception(exc)

    with col2:
        if st.button("Generate Report Only", use_container_width=True):
            try:
                md_path, html_path = run_report_step()
                st.success("Report generated.")
                st.write(f"Markdown: {md_path}")
                st.write(f"HTML: {html_path}")
            except Exception as exc:
                st.error("Report generation failed.")
                with st.expander("Error details"):
                    st.exception(exc)

    with col3:
        if st.button("Send Latest Email", use_container_width=True):
            try:
                run_email_step()
                st.success("Email sent.")
            except Exception as exc:
                st.error("Email send failed.")
                with st.expander("Error details"):
                    st.exception(exc)

    with col4:
        if st.button("Refresh Latest Report", use_container_width=True):
            st.rerun()

    st.subheader("Latest Report Preview")
    markdown_text, md_path = _load_markdown_preview()
    html_path = _latest_html_path()

    if markdown_text is None:
        st.warning("No markdown report found yet. Run full pipeline or generate report first.")
    else:
        st.write(f"Markdown path: {md_path}")
        st.write(f"HTML path: {html_path}")
        st.markdown(markdown_text)

    st.subheader("History Reports")
    history = _list_history_markdown_files()
    if not history:
        st.info("No historical reports found.")
    else:
        for item in history:
            st.write(item.name)


if __name__ == "__main__":
    main()
