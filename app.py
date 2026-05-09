from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.config import load_app_config
from src.pipeline import run_email_step, run_full_pipeline, run_report_step
from src.utils.source_health import load_latest_source_health

PROJECT_ROOT = Path(__file__).resolve().parent


def _find_latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_text(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding='utf-8')


def _latest_report_paths() -> tuple[Path | None, Path | None]:
    md_path = _find_latest(PROJECT_ROOT / 'outputs' / 'markdown', '*-ai-news-digest.md')
    html_path = _find_latest(PROJECT_ROOT / 'outputs' / 'html', '*-ai-news-digest.html')
    return md_path, html_path


def _safe_bool_configured(value: str) -> bool:
    raw = (value or '').strip().lower()
    return bool(raw) and 'your_' not in raw and 'placeholder' not in raw


def _smtp_missing_keys(cfg) -> list[str]:
    missing = []
    if not _safe_bool_configured(cfg.sender_email):
        missing.append('SENDER_EMAIL')
    if not _safe_bool_configured(cfg.smtp_auth_code):
        missing.append('SMTP_AUTH_CODE')
    if not _safe_bool_configured(cfg.recipient_email) and not _safe_bool_configured(cfg.recipient_emails):
        missing.append('RECIPIENT_EMAIL or RECIPIENT_EMAILS')
    if not (cfg.smtp_host or '').strip():
        missing.append('SMTP_HOST')
    if not int(cfg.smtp_port or 0):
        missing.append('SMTP_PORT')
    return missing


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

    st.sidebar.header('Run Config')
    topic_input = st.sidebar.text_input('Topic', value=cfg.digest_topic, key='topic_input')
    llm_limit = st.sidebar.slider('Final events/candidates sent to LLM', min_value=5, max_value=60, value=30, step=1, key='llm_limit')
    send_email_flag = st.sidebar.checkbox('Send email after full pipeline', value=False, key='send_email_after_pipeline')
    dry_run_flag = st.sidebar.checkbox('Email dry run (no SMTP send)', value=cfg.dry_run, key='email_dry_run')

    zhipu_ok = 'yes' if _safe_bool_configured(cfg.zhipu_api_key) else 'no'
    smtp_ok = 'yes' if not _smtp_missing_keys(cfg) else 'no'
    st.sidebar.markdown('---')
    st.sidebar.write(f'ZHIPU_API_KEY configured: **{zhipu_ok}**')
    st.sidebar.write(f'SMTP configured: **{smtp_ok}**')
    st.sidebar.write(f'MAX_RECIPIENTS_PER_RUN: **{cfg.max_recipients_per_run}**')

    tabs = st.tabs(['Latest Digest', 'Run Pipeline', 'History', 'Config & Source Health'])

    with tabs[0]:
        md_path, html_path = _latest_report_paths()
        md_text = _load_text(md_path)
        html_text = _load_text(html_path)

        c1, c2, c3 = st.columns(3)
        selected_count, appendix_count = _extract_counts(md_text)
        c1.metric('Selected Count', selected_count if selected_count is not None else '-')
        c2.metric('Appendix Count', appendix_count if appendix_count is not None else '-')
        c3.metric('Topic Input', topic_input)

        if md_text is None:
            st.warning('Please run report generation first.')
        else:
            st.write(f'Markdown path: {md_path}')
            st.write(f'HTML path: {html_path}')
            st.download_button('Download Markdown', data=md_text, file_name=md_path.name if md_path else 'digest.md', mime='text/markdown', key='download_md_latest')
            if html_text is not None and html_path is not None:
                st.download_button('Download HTML', data=html_text, file_name=html_path.name, mime='text/html', key='download_html_latest')
            st.markdown(md_text)
            with st.expander('HTML Preview (raw)'):
                if html_text:
                    st.code(html_text[:3000], language='html')

    with tabs[1]:
        st.info('Run full pipeline, report-only, or email-only actions. Email is explicit and observable.')
        if send_email_flag and _smtp_missing_keys(cfg):
            st.warning('SMTP config missing: ' + ', '.join(_smtp_missing_keys(cfg)))

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button('Run Full Pipeline', width='stretch', key='run_full_pipeline_btn'):
                try:
                    with st.spinner('Running full pipeline...'):
                        # Temporarily apply dry_run in runtime config object without touching .env.
                        outputs = run_full_pipeline(
                            send_email=send_email_flag,
                            llm_candidate_limit=llm_limit,
                            topic_override=topic_input,
                            dry_run=dry_run_flag,
                        )
                    st.success('Pipeline completed.')

                    summary = outputs.get('pipeline_summary') if isinstance(outputs, dict) else None
                    if isinstance(summary, dict) and summary:
                        st.subheader('Pipeline Summary')
                        st.json(summary)
                    else:
                        st.info('Pipeline summary not available.')

                    email_result = outputs.get('email_result') if isinstance(outputs, dict) else None
                    if send_email_flag:
                        if isinstance(email_result, dict):
                            if email_result.get('success'):
                                st.success(f"Email sent successfully. Recipients: {email_result.get('recipients')}")
                                if email_result.get('dry_run'):
                                    st.info('Dry run enabled: SMTP send was skipped.')
                            else:
                                st.error(f"Email send failed: {email_result.get('error')}")
                        else:
                            st.warning('Email was requested, but no email_result returned by pipeline.')

                    st.json({k: str(v) if not isinstance(v, dict) else v for k, v in outputs.items()})
                except Exception as exc:
                    st.error('Pipeline failed. Please check stage errors below.')
                    with st.expander('Error details'):
                        st.exception(exc)

        with col2:
            if st.button('Generate Report Only', width='stretch', key='report_only_btn'):
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
            if st.button('Send Latest Email', width='stretch', key='send_latest_email_btn'):
                try:
                    if _smtp_missing_keys(cfg):
                        st.error('SMTP config missing: ' + ', '.join(_smtp_missing_keys(cfg)))
                    else:
                        with st.spinner('Sending email...'):
                            result = run_email_step(dry_run_override=dry_run_flag)
                        if isinstance(result, dict) and result.get('success'):
                            st.success(f"Email sent. Recipients: {result.get('recipients')}")
                            if result.get('dry_run'):
                                st.info('Dry run enabled: SMTP send was skipped.')
                        else:
                            msg = result.get('error') if isinstance(result, dict) else 'Unknown email send error.'
                            st.error(f'Email send failed: {msg}')
                except Exception as exc:
                    st.error('Email send failed.')
                    with st.expander('Error details'):
                        st.exception(exc)

        with col4:
            if st.button('Refresh Latest Report', width='stretch', key='refresh_report_btn'):
                st.rerun()

    with tabs[2]:
        history_files = sorted((PROJECT_ROOT / 'outputs' / 'markdown').glob('*-ai-news-digest.md'), key=lambda p: p.stat().st_mtime, reverse=True)
        if not history_files:
            st.info('No historical reports found.')
        else:
            options = [f.name for f in history_files]
            selected = st.selectbox('Select a historical markdown report', options, key='history_select')
            selected_path = next((p for p in history_files if p.name == selected), None)
            if selected_path:
                mtime = datetime.fromtimestamp(selected_path.stat().st_mtime)
                st.write(f'Last modified: {mtime}')
                content = selected_path.read_text(encoding='utf-8')
                st.download_button('Download Selected Markdown', data=content, file_name=selected_path.name, mime='text/markdown', key='download_selected_md')
                st.markdown(content)

    with tabs[3]:
        st.subheader('Config Snapshot')
        st.json(
            {
                'topic_input': topic_input,
                'llm_limit': llm_limit,
                'send_email_checkbox': send_email_flag,
                'dry_run_checkbox': dry_run_flag,
                'smtp_missing_keys': _smtp_missing_keys(cfg),
            }
        )

        st.subheader('Source Health Summary')
        health = load_latest_source_health(input_dir=str(PROJECT_ROOT / 'data' / 'raw'))
        if not health:
            st.info('Run fetchers test or pipeline to update source health.')
        else:
            st.dataframe(health, width='stretch')

        latest_digest = _find_latest(PROJECT_ROOT / 'data' / 'digested', '*_digest.json')
        if latest_digest and latest_digest.exists():
            try:
                payload = json.loads(latest_digest.read_text(encoding='utf-8'))
                stats = payload.get('source_statistics', {}) if isinstance(payload, dict) else {}
                st.subheader('Latest Pipeline Statistics')
                st.json(stats)
            except Exception:
                st.info('Latest digest statistics not available.')


if __name__ == '__main__':
    main()
