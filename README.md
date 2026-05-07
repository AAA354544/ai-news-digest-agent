# ai-news-digest-agent

A lightweight open-source MVP for building an AI News Daily Digest Agent.

## Project Overview
This project aims to build an agent that collects AI-related news from the past 24 hours, then uses LLM-based steps (deduplication, merging, classification, summarization) to generate a Chinese daily digest in Markdown + HTML and send it via email.

## MVP Goal
Complete a 3-4 day collaboration MVP with clear modular architecture and iterative delivery.

## Current Status
**Module 0: Project Skeleton**

Implemented in this module:
- Open-source-friendly folder structure
- Basic configuration placeholders
- Minimal Streamlit demo page
- Minimal CLI entrypoint
- Documentation and environment template

Not implemented yet:
- Real fetching/parsing logic
- Real LLM processing
- Real email delivery

## Tech Stack (Planned)
- Python
- Streamlit (quick UI)
- Typer + Rich (CLI)
- Pydantic + dotenv + YAML config
- Requests/feedparser/BeautifulSoup/trafilatura (data ingestion)
- Jinja2 (HTML generation)
- OpenAI-compatible API clients (provider-switchable)

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

2. Run CLI
```bash
python cli.py status
```

3. Run Streamlit demo
```bash
streamlit run app.py
```

## Environment Variables
Copy `.env.example` to `.env` and fill your own values later.

Current `.env.example` includes placeholders for:
- Digest settings
- LLM provider settings (Zhipu/DeepSeek/Qwen)
- GitHub token
- SMTP email sending settings
- Timezone and schedule settings

## Roadmap
- Module 1: Source fetching + normalization
- Module 2: Cleaning + rough deduplication
- Module 3: LLM ranking/classification/summarization
- Module 4: Markdown/HTML rendering
- Module 5: Email delivery and scheduling
- Module 6: Observability, tests, and hardening

---
This repository currently provides only the Module 0 initialization skeleton.
