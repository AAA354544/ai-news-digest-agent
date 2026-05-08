from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from src.config import get_enabled_sources, load_app_config
from src.pipeline import run_email_step, run_full_pipeline, run_report_step
from src.utils.source_health import load_latest_source_health

PROJECT_ROOT = Path(__file__).resolve().parent


def _find_latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_markdown(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding='utf-8')


def _sidebar_config(cfg):
    st.sidebar.header('Run Config')
    topic = st.sidebar.text_input('Topic', value=cfg.digest_topic)
    llm_limit = st.sidebar.slider('LLM candidate limit', min_value=5, max_value=50, value=10, step=1)
    send_email = st.sidebar.checkbox('Send email after full pipeline', value=False)

    zhipu_ok = 'yes' if bool((cfg.zhipu_api_key or '').strip()) and 'your_' not in (cfg.zhipu_api_key or '').lower() else 'no'
    smtp_ok = 'yes' if bool((cfg.sender_email or '').strip()) and bool((cfg.smtp_auth_code or '').strip()) and 'your_' not in (cfg.sender_email or '').lower() else 'no'
    enabled_source_count = len(get_enabled_sources())

    st.sidebar.markdown('---')
    st.sidebar.write(f'ZHIPU_API_KEY configured: **{zhipu_ok}**')
    st.sidebar.write(f'SMTP configured: **{smtp_ok}**')
    st.sidebar.write(f'Enabled source count: **{enabled_source_count}**')
    return topic, llm_limit, send_email, enabled_source_count


def _latest_report_paths() -> tuple[Path | None, Path | None]:
    md_path = _find_latest(PROJECT_ROOT / 'outputs' / 'markdown', '*-ai-news-digest.md')
    html_path = _find_latest(PROJECT_ROOT / 'outputs' / 'html', '*-ai-news-digest.html')
    return md_path, html_path


def _extract_counts(md_text: str | None) -> tuple[int | None, int | None]:
    if not md_text:
        return None, None
    selected = None
    appendix = None
    for line in md_text.splitlines():
        if line.startswith('- Selected News Count:'):
            try:
                selected = int(line.split(':', 1)[1].strip())
            except Exception:
                pass
        if line.startswith('- Appendix Count:'):
            try:
                appendix = int(line.split(':', 1)[1].strip())
            except Exception:
                pass
    return selected, appendix


def main() -> None:
    cfg = load_app_config()

    st.set_page_config(page_title='AI News Digest Agent', page_icon='📰', layout='wide')
    st.title('AI News Digest Agent')
    st.subheader('AI Research Progress + AI Industry Trend Digest')
    st.caption('Multi-source fetch -> LLM analysis -> Markdown/HTML report -> optional email delivery.')

    topic_input, llm_limit, send_email_flag, enabled_source_count = _sidebar_config(cfg)

    tabs = st.tabs(['Latest Digest', 'Run Pipeline', 'History', 'Config & Source Health'])

    with tabs[0]:
        md_path, html_path = _latest_report_paths()
        md_text = _load_markdown(md_path)

        c1, c2, c3 = st.columns(3)
        selected_count, appendix_count = _extract_counts(md_text)
        c1.metric('Selected Count', selected_count if selected_count is not None else '-')
        c2.metric('Appendix Count', appendix_count if appendix_count is not None else '-')
        c3.metric('Enabled Sources', enabled_source_count)

        if md_text is None:
            st.warning('Please run report generation first.')
        else:
            st.write(f'Markdown path: {md_path}')
            st.write(f'HTML path: {html_path}')
            st.download_button('Download Markdown', data=md_text, file_name=md_path.name if md_path else 'digest.md', mime='text/markdown')
            if html_path and html_path.exists():
                html_text = html_path.read_text(encoding='utf-8')
                st.download_button('Download HTML', data=html_text, file_name=html_path.name, mime='text/html')
            st.markdown(md_text)

    with tabs[1]:
        st.info('Pipeline actions are explicit. Email is never sent unless you choose it.')
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button('Run Full Pipeline', use_container_width=True):
                try:
                    with st.spinner('Running full pipeline...'):
                        outputs = run_full_pipeline(send_email=send_email_flag, llm_candidate_limit=llm_limit)
                    st.success('Pipeline completed.')
                    st.json({k: str(v) for k, v in outputs.items()})
                except Exception as exc:
                    st.error('Pipeline failed.')
                    with st.expander('Error details'):
                        st.exception(exc)

        with col2:
            if st.button('Generate Report Only', use_container_width=True):
                try:
                    with st.spinner('Generating report...'):
                        md, html = run_report_step()
                    st.success('Report generated.')
                    st.write(f'Markdown: {md}')
                    st.write(f'HTML: {html}')
                except Exception as exc:
                    st.error('Report generation failed.')
                    with st.expander('Error details'):
                        st.exception(exc)

        with col3:
            if st.button('Send Latest Email', use_container_width=True):
                try:
                    with st.spinner('Sending email...'):
                        run_email_step()
                    st.success('Email sent.')
                except Exception as exc:
                    st.error('Email send failed.')
                    with st.expander('Error details'):
                        st.exception(exc)

        with col4:
            if st.button('Refresh Latest Report', use_container_width=True):
                st.rerun()

    with tabs[2]:
        history_files = sorted((PROJECT_ROOT / 'outputs' / 'markdown').glob('*-ai-news-digest.md'), key=lambda p: p.stat().st_mtime, reverse=True)
        if not history_files:
            st.info('No historical reports found.')
        else:
            options = [f.name for f in history_files]
            selected = st.selectbox('Select a historical markdown report', options)
            selected_path = next((p for p in history_files if p.name == selected), None)
            if selected_path:
                mtime = datetime.fromtimestamp(selected_path.stat().st_mtime)
                st.write(f'Last modified: {mtime}')
                content = selected_path.read_text(encoding='utf-8')
                st.download_button('Download Selected Markdown', data=content, file_name=selected_path.name, mime='text/markdown')
                st.markdown(content)

    with tabs[3]:
        st.subheader('Enabled Sources')
        enabled_sources = get_enabled_sources()
        if not enabled_sources:
            st.info('No enabled sources configured.')
        else:
            st.dataframe([
                {
                    'name': s.get('name', ''),
                    'type': s.get('type', ''),
                    'category': s.get('category', ''),
                    'region': s.get('region', ''),
                    'language': s.get('language', ''),
                    'max_items': s.get('max_items', ''),
                }
                for s in enabled_sources
            ], use_container_width=True)

        st.subheader('Source Health Summary')
        health = load_latest_source_health(input_dir=str(PROJECT_ROOT / 'data' / 'raw'))
        if not health:
            st.info('Run fetchers test or pipeline to update source health.')
        else:
            st.dataframe(health, use_container_width=True)


if __name__ == '__main__':
    main()
