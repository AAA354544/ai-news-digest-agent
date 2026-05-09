from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import run_full_pipeline


def main() -> None:
    print('Testing pipeline arg pass-through for Streamlit logic...')

    outputs = run_full_pipeline(send_email=False, llm_candidate_limit=5, topic_override='AI Agent memory')
    if not outputs.get('markdown_path') or not outputs.get('html_path'):
        raise RuntimeError('Missing report paths in pipeline output.')

    summary = outputs.get('pipeline_summary')
    print(f'pipeline summary: {summary}')
    print(f'topic in summary: {summary.get("topic") if isinstance(summary, dict) else None}')

    try:
        outputs_email = run_full_pipeline(
            send_email=True,
            llm_candidate_limit=5,
            topic_override='AI Agent memory',
            dry_run=True,
        )
        email_result = outputs_email.get('email_result')
        print(f'email result: {email_result}')
    except Exception as exc:
        # readable exception is acceptable if SMTP/report prerequisites are missing.
        print(f'email step raised readable error: {exc}')

    print('manual_test_streamlit_logic completed.')


if __name__ == '__main__':
    main()
