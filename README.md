# ai-news-digest-agent

A lightweight AI news digest pipeline that turns multi-source candidates into daily Chinese Markdown/HTML reports and optional email delivery.

## Three-line Overview
- Collects public AI signals (news, research, open-source, community) into normalized candidates.
- Uses a single pipeline (`fetch -> clean -> analyze -> report -> email`) reused by CLI, Streamlit, and GitHub Actions.
- Optimized for local-first operation with minimal dependencies and no database/login/backend service.

## Features
- Modular pipeline in `src/pipeline.py`
- CLI orchestration (`cli.py`)
- Streamlit dashboard (`app.py`)
- SMTP email sending with recipient override/group support
- Local recipient management via `data/recipients.local.json`
- GitHub Actions scheduled/manual automation
- Markdown + HTML report generation
- LLM JSON repair/normalization safeguards

## Architecture
```mermaid
flowchart TD
    A[config/sources.yaml] --> B[Fetchers]
    B --> C[Raw Candidates]
    C --> D[Cleaner / Deduplicator]
    D --> E[Cleaned Candidates]
    E --> F[LLM Analyzer]
    F --> G[DailyDigest JSON]
    G --> H[Report Generator]
    H --> I[Markdown]
    H --> J[HTML]
    J --> K[SMTP Email]
    L[CLI / Streamlit / GitHub Actions] --> M[src/pipeline.py]
    M --> B
```

## Quick Start
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python cli.py status
python cli.py run-pipeline
python cli.py send-email
streamlit run app.py
```

## Configuration
- Runtime env file: `.env` (never commit)
- Source config: `config/sources.yaml`
- Digest policy: `config/digest_policy.yaml`
- Recipient local file: `data/recipients.local.json` (local only)
- Recipient example file: `config/recipients.example.json`

`DEEPSEEK_*` and `QWEN_*` in `.env.example` are **reserved/future** fields. Current LLM runtime implementation is `LLM_PROVIDER=zhipu`.

## GitHub Actions Setup
- Workflow: `.github/workflows/daily_digest.yml`
- Schedule: non-top-of-hour (`UTC 14:17`) to reduce queue spikes.
- Required repo secrets include LLM + SMTP + recipient envs used in workflow.
- `workflow_dispatch` supports:
  - `topic` (override digest topic)
  - `send_email` (true/false)
  - `llm_limit` (0 uses env default)
- If `send_email=false`, workflow only generates reports and artifacts.

## Recipient Management
- Local recipient list: `data/recipients.local.json`
- Use `config/recipients.example.json` as template.
- Real emails must stay local and must not be committed.
- CLI examples:
```bash
python cli.py send-email --to a@qq.com,b@qq.com
python cli.py send-email --group default
python cli.py run-pipeline --send-email --group default
```

## Manual Verification
```bash
python cli.py preflight --mode local
python tests/manual_test_config_models.py
python tests/manual_test_fetchers.py
python tests/manual_test_cleaner.py
python tests/manual_test_llm.py
python tests/manual_test_report.py
python tests/manual_test_email.py
python tests/manual_test_pipeline.py
python tests/manual_test_recipients.py
python tests/manual_test_config_runtime.py
```

## Streamlit
```bash
streamlit run app.py
```
- Use tabs for latest digest, pipeline run, history, source health, and recipient management.

## Screenshots
Recommended paths:
- `docs/assets/streamlit-demo.png`
- `docs/assets/email-demo.png`
- `docs/assets/report-demo.png`

## Limitations
- Provider support is currently centered on Zhipu-compatible API.
- Free-tier models may hit timeout/rate limits.
- Some upstream feeds can become unstable.
- Schedule automation is suitable for daily digest, not high-precision cron jobs.

## Roadmap
- More robust source health summaries
- Better fallback prompts and confidence marking
- Lightweight regression script set
- Future provider extensions (DeepSeek/Qwen)

## Security / Repo Hygiene
- Never commit `.env` or any real secrets.
- Never commit runtime artifacts under `outputs/`.
- Never commit local recipient real data (`data/recipients.local.json`).
- Keep `data/cache` and `data/clustered` as local runtime/debug data.
