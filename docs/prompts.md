# Module 0 - Project Skeleton Prompt

本模块由 AI 协作生成项目骨架。

范围：
- 仅完成初始化与开源骨架
- 不实现真实抓取、LLM 调用、邮件发送逻辑

# Module 1 - Config Loading and Data Models Prompt

本次 prompt 目标：实现配置加载（.env + sources.yaml）与核心数据模型（Pydantic），并提供可直接运行的手动测试脚本用于模块 1 验收。

# Module 2 - Multi-source Fetchers Prompt

本次 prompt 目标：实现多来源抓取器（RSS、Hacker News Algolia、arXiv、GitHub Trending）并统一输出 `CandidateNews`，同时提供模块 2 手动验收脚本。

# Module 3 - Cleaning, URL Deduplication, and Candidate Trimming Prompt

本次 prompt 目标：实现规则层清洗、URL 硬去重与候选裁剪流程，并提供模块 3 手动验收脚本，输出 cleaned candidates 供后续模块使用。

# Module 4 - Zhipu LLM Analysis Layer Prompt

本次 prompt 目标：实现智谱 OpenAI-compatible LLM 分析层，读取 cleaned candidates，完成语义去重与分类总结，并输出可校验的 `DailyDigest` JSON。

# Module 5 - Markdown and HTML Report Generation Prompt

本次 prompt 目标：基于模块 4 的 `DailyDigest` JSON，使用 Jinja2 渲染并输出 Markdown 与 HTML 日报文件，供后续邮件发送模块复用。
