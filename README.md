# ai-news-digest-agent

A lightweight open-source MVP for building an AI News Daily Digest Agent.

## Project Overview
This project aims to build an agent that collects AI-related news from the past 24 hours, then uses LLM-based steps (deduplication, merging, classification, summarization) to generate a Chinese daily digest in Markdown + HTML and send it via email.

## MVP Goal
Complete a 3-4 day collaboration MVP with clear modular architecture and iterative delivery.

## Current Status
Current implementation is progressing in modules. Core scaffolding, config/models, fetchers, and rule-based preprocessing are in place. LLM analysis layer is introduced in Module 4.

## Tech Stack (Planned)
- Python
- Streamlit (quick UI)
- Typer + Rich (CLI)
- Pydantic + dotenv + YAML config
- Requests/feedparser/BeautifulSoup/trafilatura (data ingestion)
- OpenAI-compatible API clients (provider-switchable)
- Jinja2 (HTML generation)

## Directory Structure
```text
.
├── app.py
├── cli.py
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   └── sources.yaml
├── docs/
│   ├── dev_log.md
│   └── prompts.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── pipeline.py
│   ├── fetchers/
│   ├── processors/
│   ├── generators/
│   ├── notifiers/
│   └── utils/
├── templates/
├── data/
│   ├── raw/
│   ├── cleaned/
│   └── digested/
├── outputs/
│   ├── markdown/
│   └── html/
└── tests/
```

## Local Run
1. Install dependencies
```bash
pip install -r requirements.txt
```

2. Run module tests in sequence
```bash
python tests/manual_test_fetchers.py
python tests/manual_test_cleaner.py
python tests/manual_test_llm.py
```

3. Run Streamlit demo page
```bash
streamlit run app.py
```

## Environment Variables
Copy `.env.example` to `.env` and fill your own values.

Key groups:
- Digest settings
- LLM provider settings (Zhipu/DeepSeek/Qwen)
- Source/API tokens
- SMTP email settings
- Timezone and schedule settings

## Roadmap
- Module 0: Project skeleton
- Module 1: Config loading and data models
- Module 2: Multi-source fetchers
- Module 3: Cleaning, URL deduplication, and candidate trimming
- Module 4: LLM analysis layer
- Module 5: Markdown and HTML report generation
- Module 6: Email delivery and scheduling
- Module 7: Observability, tests, and hardening

---
This repository is under active MVP development and does not claim full end-to-end completion yet.
