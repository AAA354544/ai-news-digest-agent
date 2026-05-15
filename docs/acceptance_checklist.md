# Acceptance Checklist (Round 1 Closure)

## Config
- [ ] `.env` is created from `.env.example` and contains no placeholder secrets.
- [ ] `python cli.py preflight --mode local` passes.
- [ ] `python tests/manual_test_config_runtime.py` passes.

## Fetch
- [ ] `python cli.py fetch` generates `data/raw/*_raw_candidates.json`.

## Clean
- [ ] `python cli.py clean` generates `data/cleaned/*_cleaned_candidates.json`.

## Analyze
- [ ] `python cli.py analyze --llm-limit 10` generates `data/digested/*_digest.json`.
- [ ] Digest JSON contains `source_statistics.selected_items` matching actual main digest item count.

## Report
- [ ] `python cli.py report` generates:
  - `outputs/markdown/*-ai-news-digest.md`
  - `outputs/html/*-ai-news-digest.html`

## Email
- [ ] `python cli.py send-email` works with default `RECIPIENT_EMAIL`.
- [ ] `python cli.py send-email --to example@example.com` validates recipient flow.
- [ ] `python cli.py send-email --group default` works when local recipient file exists.

## Streamlit
- [ ] `streamlit run app.py` opens successfully.
- [ ] Latest Digest / Run Pipeline / History / Config tabs work.
- [ ] Email Recipients tab can add/update/remove recipients and send latest digest.

## GitHub Actions
- [ ] Manual trigger (`workflow_dispatch`) works with `send_email=true/false`.
- [ ] Schedule trigger remains enabled.
- [ ] Workflow uploads artifacts (`outputs/*`, `data/digested`, debug files if present).

## Git Status Hygiene
- [ ] `git status --short` does not include:
  - `.env`
  - `data/recipients.local.json`
  - `outputs/*` runtime files
  - `data/cache/*`
  - `data/clustered/*`
