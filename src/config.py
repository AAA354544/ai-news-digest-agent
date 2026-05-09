from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

DEFAULT_DIGEST_POLICY: dict[str, Any] = {
    'candidate_quotas': {
        'arxiv': 20,
        'hn_algolia': 18,
        'github_trending': 8,
        'rss': 12,
        'rss_or_web': 12,
        'official_blog': 12,
        'ai_media': 12,
    },
    'main_digest_policy': {
        'max_research_ratio': 0.4,
        'positioning': 'AI research progress plus AI industry and technology trend digest',
        'preferred_categories': [
            '技术与模型进展',
            '科研与论文前沿',
            'Agent 与 AI 工具',
            '产业与公司动态',
            '开源生态与开发者趋势',
            '算力、芯片与基础设施',
            '安全、政策与监管',
            '其他',
        ],
    },
}


class AppConfig(BaseModel):
    digest_topic: str = Field(default='AI')
    digest_lookback_hours: int = Field(default=24)

    # candidate pool controls
    max_raw_candidates: int = Field(default=300)
    max_cluster_input_candidates: int = Field(default=120)
    max_llm_events: int = Field(default=50)
    appendix_max_items: int = Field(default=30)
    max_llm_candidates: int = Field(default=50)  # backward-compatible alias

    main_digest_min_items: int = Field(default=10)
    main_digest_max_items: int = Field(default=15)

    # LLM pipeline mode
    llm_pipeline_mode: str = Field(default='single')
    llm_preprocess_enabled: bool = Field(default=False)
    llm_preprocess_provider: str = Field(default='zhipu')
    llm_preprocess_model: str = Field(default='')
    llm_final_provider: str = Field(default='zhipu')
    llm_final_model: str = Field(default='')
    llm_repair_provider: str = Field(default='zhipu')
    llm_repair_model: str = Field(default='')

    # provider
    llm_provider: str = Field(default='zhipu')
    zhipu_api_key: str = Field(default='')
    zhipu_base_url: str = Field(default='https://open.bigmodel.cn/api/paas/v4/')
    zhipu_model: str = Field(default='')

    deepseek_api_key: str = Field(default='')
    deepseek_base_url: str = Field(default='')
    deepseek_model: str = Field(default='')

    qwen_api_key: str = Field(default='')
    qwen_base_url: str = Field(default='')
    qwen_model: str = Field(default='')

    github_token: str = Field(default='')

    smtp_host: str = Field(default='smtp.qq.com')
    smtp_port: int = Field(default=465)
    smtp_use_ssl: bool = Field(default=True)
    sender_email: str = Field(default='')
    smtp_auth_code: str = Field(default='')
    recipient_email: str = Field(default='')
    recipient_emails: str = Field(default='')
    max_recipients_per_run: int = Field(default=5)
    send_email: bool = Field(default=False)
    dry_run: bool = Field(default=False)

    default_send_time: str = Field(default='22:00')
    timezone: str = Field(default='Asia/Shanghai')


_BOOL_TRUE = {'1', 'true', 'yes', 'on'}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _BOOL_TRUE


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_app_config() -> AppConfig:
    max_llm_candidates = _env_int('MAX_LLM_CANDIDATES', 50)
    max_llm_events = _env_int('MAX_LLM_EVENTS', max_llm_candidates)

    return AppConfig(
        digest_topic=os.getenv('DIGEST_TOPIC', 'AI'),
        digest_lookback_hours=_env_int('DIGEST_LOOKBACK_HOURS', 24),
        max_raw_candidates=_env_int('MAX_RAW_CANDIDATES', 300),
        max_cluster_input_candidates=_env_int('MAX_CLUSTER_INPUT_CANDIDATES', 120),
        max_llm_events=max_llm_events,
        appendix_max_items=_env_int('APPENDIX_MAX_ITEMS', 30),
        max_llm_candidates=max_llm_candidates,
        main_digest_min_items=_env_int('MAIN_DIGEST_MIN_ITEMS', 10),
        main_digest_max_items=_env_int('MAIN_DIGEST_MAX_ITEMS', 15),
        llm_pipeline_mode=os.getenv('LLM_PIPELINE_MODE', 'single').strip().lower(),
        llm_preprocess_enabled=_env_bool('LLM_PREPROCESS_ENABLED', False),
        llm_preprocess_provider=os.getenv('LLM_PREPROCESS_PROVIDER', 'zhipu'),
        llm_preprocess_model=os.getenv('LLM_PREPROCESS_MODEL', ''),
        llm_final_provider=os.getenv('LLM_FINAL_PROVIDER', 'zhipu'),
        llm_final_model=os.getenv('LLM_FINAL_MODEL', ''),
        llm_repair_provider=os.getenv('LLM_REPAIR_PROVIDER', 'zhipu'),
        llm_repair_model=os.getenv('LLM_REPAIR_MODEL', ''),
        llm_provider=os.getenv('LLM_PROVIDER', 'zhipu'),
        zhipu_api_key=os.getenv('ZHIPU_API_KEY', ''),
        zhipu_base_url=os.getenv('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4/'),
        zhipu_model=os.getenv('ZHIPU_MODEL', ''),
        deepseek_api_key=os.getenv('DEEPSEEK_API_KEY', ''),
        deepseek_base_url=os.getenv('DEEPSEEK_BASE_URL', ''),
        deepseek_model=os.getenv('DEEPSEEK_MODEL', ''),
        qwen_api_key=os.getenv('QWEN_API_KEY', ''),
        qwen_base_url=os.getenv('QWEN_BASE_URL', ''),
        qwen_model=os.getenv('QWEN_MODEL', ''),
        github_token=os.getenv('GITHUB_TOKEN', ''),
        smtp_host=os.getenv('SMTP_HOST', 'smtp.qq.com'),
        smtp_port=_env_int('SMTP_PORT', 465),
        smtp_use_ssl=_env_bool('SMTP_USE_SSL', True),
        sender_email=os.getenv('SENDER_EMAIL', ''),
        smtp_auth_code=os.getenv('SMTP_AUTH_CODE', ''),
        recipient_email=os.getenv('RECIPIENT_EMAIL', ''),
        recipient_emails=os.getenv('RECIPIENT_EMAILS', ''),
        max_recipients_per_run=_env_int('MAX_RECIPIENTS_PER_RUN', 5),
        send_email=_env_bool('SEND_EMAIL', False),
        dry_run=_env_bool('DRY_RUN', False),
        default_send_time=os.getenv('DEFAULT_SEND_TIME', '22:00'),
        timezone=os.getenv('TIMEZONE', 'Asia/Shanghai'),
    )


def load_sources_config(path: str = 'config/sources.yaml') -> dict[str, Any] | list[dict[str, Any]]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = BASE_DIR / config_path

    if not config_path.exists():
        return {'sources': []}

    with config_path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data
    return {'sources': []}


def load_digest_policy(path: str = 'config/digest_policy.yaml') -> dict[str, Any]:
    policy_path = Path(path)
    if not policy_path.is_absolute():
        policy_path = BASE_DIR / policy_path

    if not policy_path.exists():
        return DEFAULT_DIGEST_POLICY.copy()

    try:
        with policy_path.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return DEFAULT_DIGEST_POLICY.copy()

        merged = DEFAULT_DIGEST_POLICY.copy()
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                tmp = dict(merged[key])
                tmp.update(value)
                merged[key] = tmp
            else:
                merged[key] = value
        return merged
    except Exception:
        return DEFAULT_DIGEST_POLICY.copy()


def get_enabled_sources(path: str = 'config/sources.yaml') -> list[dict[str, Any]]:
    data = load_sources_config(path)

    if isinstance(data, list):
        sources = data
    else:
        sources = data.get('sources', [])

    enabled_sources: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        if source.get('enabled', True):
            enabled_sources.append(source)
    return enabled_sources
