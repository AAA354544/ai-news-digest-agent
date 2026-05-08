# Module 0 - Dev Log

## Module Goal
Initialize an open-source-ready Python project skeleton for `ai-news-digest-agent` with clear modular boundaries and minimal runnable placeholders.

## Completed Items
- Created top-level project structure and module directories
- Added baseline dependencies in `requirements.txt`
- Added `.env.example` for future configuration
- Added `.gitignore` with data/output retention via `.gitkeep`
- Added placeholder source config (`config/sources.yaml`)
- Added minimal Streamlit page (`app.py`)
- Added minimal Typer + Rich CLI (`cli.py`)
- Added initial project README
- Added docs and prompt record files

## Acceptance Criteria
- Required files/directories exist
- `python cli.py status` runs and shows Module 0 status
- `streamlit run app.py` shows initialization page and demo button
- No real fetching/LLM/email business logic implemented
- Structure is clean and ready for next modules

## Module 1 - Config Loading and Data Models

### Module Goal
Implement centralized configuration loading and core data models for the AI news digest project, without adding business logic such as fetching, LLM processing, digest generation, or email sending.

### New/Updated Files
- `src/config.py`
- `src/models.py`
- `tests/manual_test_config_models.py`
- `docs/dev_log.md`
- `docs/prompts.md`

### Verification Method
- Run: `python tests/manual_test_config_models.py`
- Confirm config fields print correctly, source counts are loaded, and sample model objects can be created and printed.

### Current Status
Pending verification

## Module 2 - Multi-source Fetchers

### Module Goal
Implement lightweight multi-source fetchers that normalize public-source results into `CandidateNews`, without adding LLM, deduplication, reporting, email delivery, or full pipeline orchestration.

### New/Updated Files
- `src/fetchers/base.py`
- `src/fetchers/rss_fetcher.py`
- `src/fetchers/hn_fetcher.py`
- `src/fetchers/arxiv_fetcher.py`
- `src/fetchers/github_trending_fetcher.py`
- `src/fetchers/web_extractor.py`
- `src/fetchers/__init__.py`
- `config/sources.yaml`
- `tests/manual_test_fetchers.py`
- `docs/dev_log.md`
- `docs/prompts.md`

### Verification Method
- Run: `python tests/manual_test_fetchers.py`
- Validate per-source fetch count logs, merged candidate total, top-5 preview output, and raw JSON output file under `data/raw/`.

### Current Status
Pending verification

## Module 3 - Cleaning, URL Deduplication, and Candidate Trimming

### Module Goal
Implement rule-based preprocessing on raw candidates: baseline text cleanup, hard URL deduplication, lookback filtering, lightweight ranking, and candidate trimming for downstream LLM stages.

### New/Updated Files
- `src/processors/cleaner.py`
- `src/processors/deduplicator.py`
- `src/processors/__init__.py`
- `tests/manual_test_cleaner.py`
- `docs/dev_log.md`
- `docs/prompts.md`

### Verification Method
- Run: `python tests/manual_test_cleaner.py`
- Verify latest raw file discovery, stage-by-stage counts, cleaned JSON export under `data/cleaned/`, and top-5 preview output.

### Current Status
Pending verification

## Module 4 - Zhipu LLM Analysis Layer

### Module Goal
Implement an OpenAI-compatible Zhipu LLM analysis layer that reads cleaned candidates, performs semantic deduplication/event merge/classification/selection/summarization in one structured step, and outputs validated `DailyDigest` JSON.

### New/Updated Files
- `src/processors/llm_client.py`
- `src/processors/prompts.py`
- `src/processors/analyzer.py`
- `src/processors/__init__.py`
- `tests/manual_test_llm.py`
- `docs/dev_log.md`
- `docs/prompts.md`
- `README.md`

### Verification Method
- Run: `python tests/manual_test_llm.py`
- Verify latest cleaned file discovery, LLM call status, DailyDigest validation, digest JSON export under `data/digested/`, and top selected-item preview output.

### Current Status
Pending verification

## Module 5 - Markdown and HTML Report Generation

### Module Goal
Render `DailyDigest` JSON from `data/digested/` into reusable Markdown and HTML daily report files via Jinja2 templates for downstream delivery.

### New/Updated Files
- `templates/digest.md.jinja`
- `templates/digest.html.jinja`
- `src/generators/report_generator.py`
- `src/generators/__init__.py`
- `tests/manual_test_report.py`
- `docs/dev_log.md`
- `docs/prompts.md`
- `README.md`

### Verification Method
- Run: `python tests/manual_test_report.py`
- Verify latest digest loading, Markdown/HTML rendering, file outputs under `outputs/markdown` and `outputs/html`, and Markdown preview output.

### Current Status
Pending verification

## Module 6 - Email Sending

### Module Goal
Send digest email with HTML body and Markdown attachment via SMTP (QQ/163 compatible settings).

### New/Updated Files
- `src/notifiers/email_sender.py`
- `src/notifiers/__init__.py`
- `tests/manual_test_email.py`
- `.env.example`
- `README.md`
- `docs/dev_log.md`
- `docs/prompts.md`

### Verification Method
- Run: `python tests/manual_test_email.py`
- Confirm latest HTML/Markdown report discovery, config printout, and successful SMTP delivery when credentials are valid.

### Current Status
Pending verification

## Module 7 - CLI Pipeline

### Module Goal
Provide modular CLI orchestration for fetch, clean, analyze, report, email, and full pipeline runs.

### New/Updated Files
- `src/pipeline.py`
- `cli.py`
- `tests/manual_test_pipeline.py`
- `README.md`
- `docs/dev_log.md`
- `docs/prompts.md`

### Verification Method
- Run: `python tests/manual_test_pipeline.py`
- Run: `python cli.py --help`
- Run: `python cli.py report`

### Current Status
Pending verification

## Module 8 - Streamlit UI

### Module Goal
Upgrade Streamlit app from placeholder page to MVP control panel with pipeline actions and report preview.

### New/Updated Files
- `app.py`
- `README.md`
- `docs/dev_log.md`
- `docs/prompts.md`

### Verification Method
- Run: `streamlit run app.py`
- Verify pipeline action buttons, latest report preview, and history list behavior.

### Current Status
Pending verification

## Module 9 - GitHub Actions

### Module Goal
Add scheduled + manual GitHub Actions workflow to run digest pipeline and optional email sending.

### New/Updated Files
- `.github/workflows/daily_digest.yml`
- `README.md`
- `docs/dev_log.md`
- `docs/prompts.md`

### Verification Method
- Inspect workflow config and triggers in `.github/workflows/daily_digest.yml`
- Validate required secrets setup in repository settings.

### Current Status
Pending verification

## Optimization Round 1

### Goal
Improve digest quality and source balance toward "AI research progress + AI industry and technology trend" while keeping compliant fetching and modular architecture.

### Changes
- Added source balancing layer (`balancer.py`) and integrated into candidate preparation.
- Added `config/digest_policy.yaml` and policy loader in `src/config.py`.
- Enhanced fetch robustness with `src/utils/http_utils.py` (headers, timeout, retry, 429/403/404 handling).
- Updated fetchers to use safer network behavior and placeholder-aware skipping.
- Expanded `config/sources.yaml` with more company/media sources and explicit TODO-disabled entries.
- Updated prompts to emphasize research+industry positioning and non-paper-list output style.
- Updated Markdown/HTML templates for clearer trend-oriented report presentation.
- Updated README for architecture, strategy, config, verification, and limitations.

### Verification
- `python tests/manual_test_digest_policy.py`
- `python tests/manual_test_balancer.py`
- `python tests/manual_test_fetchers.py`
- `python tests/manual_test_cleaner.py`
- `set LLM_TEST_CANDIDATE_LIMIT=10 && python tests/manual_test_llm.py`
- `python tests/manual_test_report.py`

### Status
Pending verification
