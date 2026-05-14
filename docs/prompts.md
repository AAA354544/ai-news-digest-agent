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

# Long-run Architecture Optimization Prompt Summary

本次长程优化聚焦 6 个问题：topic override 生效、中文源接入、候选池分层控制、事件级聚类、多来源合并、分层 LLM pipeline。
关键设计决策：
1. 保持 DailyDigest 输出兼容，不改核心渲染/邮件链路；
2. 先做可解释 deterministic event clustering，再接入 layered LLM；
3. layered 失败必须 fallback 到旧候选流程；
4. 所有新增 source 可开关、可失败、可降级，不影响全 pipeline 连续性。

# Streamlit Interaction and Email Send Repair Prompt Summary

本次修复聚焦 Streamlit 控件到后端调用链的完整性：
- topic / llm limit / send_email / dry_run 参数是否真正传递；
- 邮件发送是否返回明确成功或失败结果；
- 缺少 SMTP 配置时是否给出可读提示；
- pipeline 返回结构是否足够支撑页面 summary 与状态反馈。

关键决策：
1) 为 email sender 返回结构化结果，而不是仅抛异常或 print；
2) pipeline 返回 `pipeline_summary/source_health_path/email_result`；
3) Streamlit 页面统一显示运行状态、错误详情与可下载产物。

# Digest Quality Convergence and Selection Policy Prompt Summary

本次优化目标：把日报从“信息堆叠”收敛为“少而精”的 AI 科研与产业风向简报。
核心策略：
1) 正文与附录数量上限配置化；
2) 最终正文按 international/chinese 约 70/30 做比例控制；
3) 低价值内容降级或剔除；
4) appendix 与正文严格去重；
5) prompt 强化事件级分析与质量优先；
6) 增加可观察性统计字段用于回归调优。

# Zhipu Multi-stage LLM Configuration Prompt Summary

本次调整目标：在不引入新 SDK 的前提下，让 preprocess/final/repair 三个阶段可配置不同智谱模型与可选不同 API key，同时保持单 key 兼容。

关键决策：
1) 统一沿用 OpenAI-compatible client；
2) 增加 stage-aware model/key 解析与 fallback；
3) 保留 single 模式兼容旧流程；
4) repair 失败回退本地逻辑，final 失败明确报错。

# Report Display Quality and Appendix Cleanup Prompt

本次 prompt 目标：在不破坏现有 pipeline 的前提下，清理附录中的内部筛选痕迹，过滤明显无关内容，收紧事件聚类误合并，并将 HTML 报告优化为更专业的 newsletter 呈现。

# Research Coverage Recovery Prompt

本次 prompt 目标：修复日报中科研论文内容缺失问题，通过 research quota、arXiv query expansion、cache fallback 和 research 指标增强，确保“AI 科研 + 产业风向”定位稳定生效。
# Final Quality Closure Prompt Summary

本轮目标：修复“科研保底失败、中文占比偏高、appendix 噪声、topic 相关性不足”。核心策略：在候选、事件、最终后处理三层强约束 research quota，并对 reasoning/long-context/memory 主题做查询扩展与相关性硬过滤。
# Stability Closure Prompt Summary

本次收口目标：解决最终正文仅 5 条、research quota 失效、统计口径不一致和 appendix 噪声问题。核心方案是“先选后裁再回填”、研究保底硬约束、region ratio 非删空化、以及统计字段统一。
# Final Small Stability Adjustment Prompt Summary

本次仅做两项小修：放宽 Appendix 到 5-10 条高质量补充（仍保持硬过滤），以及 final LLM 在 `glm-4.7-flash` 连续 2 次临时失败后自动回退到 `glm-4-flash-250414`。

# GitHub Actions Daily Email Stability Prompt Summary

本次优化仅聚焦 GitHub Actions 自动发送稳定性：调整 cron 避开整点、增加 concurrency 防重入、增加 timeout 防卡死、增加 preflight 环境检查（不打印 secret 明文）、并在任务结束后上传 `outputs/` artifact 便于下载日报与排障；不改 CLI/pipeline/邮件核心逻辑，不引入数据库或复杂后台。
