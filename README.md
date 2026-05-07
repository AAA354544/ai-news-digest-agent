# ai-news-digest-agent

A modular open-source MVP for generating a daily AI news digest.

## Project Overview
The project collects AI-related updates from multiple public sources, performs rule-based preprocessing, uses LLM analysis for semantic consolidation, and generates Markdown + HTML reports. Optional SMTP sending delivers the digest by email.

## Current Status
- Module 0-5: completed
- Module 6-9: implemented, pending verification

## Implemented Modules
- Module 0: Project skeleton
- Module 1: Config loading and data models
- Module 2: Multi-source fetchers
- Module 3: Cleaning, URL deduplication, and candidate trimming
- Module 4: Zhipu LLM analysis layer
- Module 5: Markdown and HTML report generation
- Module 6: Email sending (HTML body + Markdown attachment)
- Module 7: CLI pipeline orchestration
- Module 8: Streamlit MVP UI
- Module 9: GitHub Actions scheduled automation

## Local Run
1. Install dependencies
```bash
pip install -r requirements.txt
```

2. Step-by-step manual tests
```bash
python tests/manual_test_fetchers.py
python tests/manual_test_cleaner.py
python tests/manual_test_llm.py
python tests/manual_test_report.py
python tests/manual_test_email.py
```

3. CLI usage
```bash
python cli.py --help
python cli.py run-pipeline --llm-limit 5
python cli.py run-pipeline --send-email --llm-limit 5
```

4. Streamlit UI
```bash
streamlit run app.py
```

## Email Configuration
Set SMTP values in `.env` (do not commit `.env`):
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_SSL`
- `SENDER_EMAIL`
- `SMTP_AUTH_CODE`
- `RECIPIENT_EMAIL`

Notes:
- QQ/163 usually require SMTP authorization code, not account login password.
- Recommended first run: send to your own mailbox.
- Multiple recipients are supported using comma-separated emails in `RECIPIENT_EMAIL`.

## GitHub Actions (Module 9)
Workflow file: `.github/workflows/daily_digest.yml`

- Trigger types:
  - `schedule` at Beijing 22:00 (UTC 14:00, cron `0 14 * * *`)
  - `workflow_dispatch` for manual trigger

Configure repository secrets in: `Settings -> Secrets and variables -> Actions`.

Required secrets:
- `ZHIPU_API_KEY`
- `ZHIPU_BASE_URL`
- `ZHIPU_MODEL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USE_SSL`
- `SENDER_EMAIL`
- `SMTP_AUTH_CODE`
- `RECIPIENT_EMAIL`

Optional secrets:
- `DIGEST_TOPIC`
- `MAX_LLM_CANDIDATES`

## Repo Hygiene
- Never commit `.env`
- Never commit generated runtime outputs in `data/` and `outputs/`

---
This repository is an MVP and is still under iterative verification.
