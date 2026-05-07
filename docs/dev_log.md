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
