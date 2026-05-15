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

# Module 6-9 Final Integration Prompt

本次 prompt 目标：补齐邮件发送、CLI pipeline、Streamlit MVP 页面和 GitHub Actions 定时运行，形成端到端闭环，并保持模块化、可复用、可手动验收。

# Optimization Round 1 - Research and Industry Digest Balance Prompt

本轮优化目标：在保持模块化与合规抓取前提下，提升日报质量与来源平衡，避免论文列表化，强化“科研进展 + 产业风向”表达，并补充策略配置、模板表达和开源文档展示。

# Optimization Round 2 - UI, Email, Sources, and Source Health Prompt

本次 prompt 目标：优化项目展示与内容源质量，包括 README/Mermaid 修正、Streamlit 展示增强、HTML 邮件模板优化、来源扩展与 source health 汇总，以及更平衡的 LLM 来源策略。

# Optimization Round 1 Closure Prompt Summary

本轮目标：在不引入数据库/登录系统/复杂后端和前端框架前提下，完成第一批高性价比收口优化。重点包括：配置解析与 preflight、GitHub Actions 稳定性增强、LLM 可信度约束、程序侧统计口径修正、报告模板可读性提升、README 与验收清单完善。

# Optimization Round 3 - Recipients + Streamlit Targeted Send Prompt

本轮目标：在不引入数据库/登录系统/云后端的前提下，新增本地 JSON 收件人管理能力，并打通 CLI 与 Streamlit 的“按选择邮箱发送最新日报”流程；同时保持 GitHub Actions 继续使用 `RECIPIENT_EMAIL` 默认机制，确保兼容与轻量化。
