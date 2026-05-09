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

## Optimization Round 2 - UI, Email, Sources, and Source Health

### Goal
Polish project presentation and improve source diversity/operability without changing core architecture.

### Changes
- README and Mermaid architecture section improved for open-source showcase.
- Streamlit UI upgraded with tabs, metrics, history preview, and Markdown/HTML download buttons.
- HTML email template refined with digest hero, cleaner cards, and appendix readability.
- High-quality source list expanded with additional company/tooling/media candidates.
- Source health summary added and persisted for fetch visibility.
- LLM prompt refined for richer source mix and reduced single-source dominance.

### Verification
- README/Mermaid static rendering check on GitHub
- `streamlit run app.py`
- `python tests/manual_test_report.py`
- `python tests/manual_test_fetchers.py`
- `set LLM_TEST_CANDIDATE_LIMIT=10 && python tests/manual_test_llm.py`

### Status
Pending verification

## Long-run Architecture Optimization - Topic Override, Event Clustering, and Layered LLM

### Problems Before
- Streamlit topic input did not effectively control final digest topic.
- Chinese sources were mostly placeholders, so chinese_count often stayed 0.
- Candidate pool stages were unclear and too aggressively reduced too early.
- URL dedup existed, but same-event multi-source merging was weak.
- Prompt behavior was closer to news-list selection than event-level intelligence.
- Single-pass LLM flow had limited fallback structure.

### What Was Implemented
- Topic override wired from UI/CLI into fetch/analyze and final digest topic field.
- Candidate pool stages clarified and controlled via new config limits.
- Deterministic event clustering module added (`event_clusterer.py`) with source-evidence merge.
- Layered mode support added with graceful fallback to candidate mode.
- Prompt upgraded for event-level synthesis and multi-source merged reporting.
- Chinese source config expanded with enabled public feeds plus disabled TODO official sources.

### Compatibility
- Kept DailyDigest output schema compatible.
- Retained JSON repair / payload normalization / fallback behavior.
- Preserved report generation and email path contracts.

### Verification
- `python tests/manual_test_fetchers.py`
- `python tests/manual_test_event_clusterer.py`
- `python tests/manual_test_pipeline.py`
- `python tests/manual_test_report.py`
- `python tests/manual_test_email.py`

### Status
Pending verification

## Streamlit Interaction & Email Send Fix

### Scope
- Audited all Streamlit controls (topic, llm limit, send-email checkbox, dry-run, run buttons, refresh, downloads).
- Fixed UI-to-backend parameter pass-through.
- Added explicit email result feedback and SMTP missing-variable messaging.
- Added pipeline return enrichment for UI summary rendering.

### Fixes
- `topic_input` now consistently flows into pipeline + analyzer.
- `llm limit` now consistently flows into analyze step.
- `send email` now returns structured result and UI feedback instead of silent behavior.
- Added `dry_run` pass-through for Streamlit-triggered email.
- Added pipeline summary and source health path to pipeline outputs.
- Added `manual_test_streamlit_logic.py` for non-browser interaction verification.

### Result
- Streamlit email behavior is now observable (`success/error/recipients/dry_run`).
- Missing SMTP config is shown as readable env var checklist.
- Download buttons remain functional after generation.

## Digest Quality Convergence Optimization

### Observed Issues
- Chinese content could dominate the final main digest after source expansion.
- Main digest length drifted too long (beyond intended 10-15).
- Appendix length drifted too long and could overlap with main digest.
- Low-value/weakly-related items occasionally entered top stories.

### Implemented Fixes
- Added post-LLM quality convergence layer (`digest_quality.py`) to enforce:
  - main digest cap (default target 12, hard cap <=15)
  - appendix cap (default target 20, cap <=25)
  - international/chinese selected ratio targeting (~70/30)
  - low-value demotion/removal
  - appendix de-dup against main digest (URL/title similarity)
- Extended source statistics with quality observability fields:
  - selected_international_count
  - selected_chinese_count
  - appendix_count
  - dropped_low_value_count
  - duplicate_removed_from_appendix_count
- Updated prompts for "AI Research & Industry Digest" quality expectations and anti-noise guidance.

### Validation
- Added `tests/manual_test_digest_quality_policy.py` (offline, no API/network).
- Existing pipeline/report/manual tests remain compatible.

## Zhipu Multi-stage LLM Config Support

### Goal
Allow preprocess/final/repair stages to use different Zhipu models while keeping single-key compatibility and safe fallback behavior.

### Implemented
- Added stage-level provider/model configuration fields.
- Added optional stage-specific Zhipu API keys with fallback to `ZHIPU_API_KEY`.
- Normalized `ZHIPU_BASE_URL` to avoid duplicated `/chat/completions` paths.
- Analyzer now calls stage-specific LLM invocations:
  - preprocess stage in layered mode
  - final stage for digest generation
  - optional repair stage for JSON repair fallback
- Added `manual_test_llm_layers.py` for configuration and optional smoke tests.

### Fallback Rules
- preprocess failure -> deterministic local scoring
- repair failure -> local repair/normalizer path
- final failure -> explicit error

## Report Display Quality and Appendix Cleanup Optimization

### Issues Fixed
- Appendix leaked internal policy/debug wording into reader-facing reports.
- Irrelevant non-AI items could still appear in appendix.
- Event clustering was too permissive for some HN/YouTube cases.
- HTML newsletter still looked like a generic web report.

### Changes
- Rebuilt src/processors/digest_quality.py with reader-safe text sanitization, appendix relevance filtering, low-value demotion, and main/appendix de-dup.
- Tightened merge rules in src/processors/event_clusterer.py (stricter HN/YouTube and specific-token requirements).
- Strengthened appendix constraints in src/processors/prompts.py.
- Upgraded 	emplates/digest.html.jinja to newsletter-style layout (preheader, brief, top-3, short link labels, run summary).
- Expanded markdown source statistics fields in 	emplates/digest.md.jinja.
- Updated 	ests/manual_test_event_clusterer.py and 	ests/manual_test_digest_quality_policy.py for regression checks.

### Verification
- python tests/manual_test_digest_quality_policy.py
- python tests/manual_test_event_clusterer.py
- python tests/manual_test_pipeline.py
- python tests/manual_test_report.py
- python tests/manual_test_email.py


## Research Coverage Recovery Optimization

### Problem
- Research/paper items were squeezed out by tool/news/community content, causing weak scientific coverage in final digest.

### Fixes
- Added research quota controls (min/target/max) and enabled quota logic in final quality policy.
- Protected research candidates in pre-LLM candidate selection and final digest postprocess.
- Expanded arXiv topic queries for agent/tool-use/memory/workflow focus areas and broader ML categories.
- Added arXiv cache fallback on rate-limit/timeout with health status cache_fallback.
- Added Semantic Scholar fetcher as research fallback source.
- Added research observability metrics in source statistics and pipeline summary.

### Verification
- python tests/manual_test_research_quota.py
- python tests/manual_test_fetchers.py
- python tests/manual_test_pipeline.py

## Final Quality Closure - Research and Relevance

### Problems
- Research quota not effectively enforced in final digest selection.
- Chinese share could dominate final main digest.
- Appendix still had noisy/weakly-related items.
- Topic relevance was too loose for reasoning/long-context/memory topics.

### Fixes
- Enforced research quota in final quality policy with shortage reason reporting.
- Added research-preserving selection before final LLM events and in final postprocess.
- Expanded arXiv/Semantic Scholar query sets for reasoning/long-context/memory topics.
- Added arXiv cache fallback usage visibility and research status metrics.
- Added hard appendix reject patterns and stronger topic relevance thresholds.
- Added hard final-region ratio enforcement to keep main digest near 70/30 target.
## Stability Closure - Final Selection Recovery
- Fixed regression where final digest could shrink to 5 items despite large cleaned candidate pool.
- Added backfill mechanism to enforce main digest lower bound when candidates are sufficient.
- Strengthened research quota enforcement in final selection and added shortage diagnostics.
- Unified stats semantics between pipeline logs and report output (`cleaned` vs `final_llm_events` mismatch fixed via cleaning stats sidecar).
## Final Small Stability Adjustments
- Relaxed appendix selection from overly strict behavior (Appendix=0) to target 5-10 high-quality supplemental items.
- Added final-model fallback: `glm-4.7-flash` retries 2 times on transient errors, then falls back to `glm-4-flash-250414`.
- Added fallback observability fields (`final_model_used`, `final_fallback_used`, `final_fallback_reason`) and appendix shortage diagnostics.
