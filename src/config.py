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
    max_llm_candidates: int = Field(default=50)
    main_digest_min_items: int = Field(default=10)
    main_digest_max_items: int = Field(default=15)

    llm_provider: str = Field(default='zhipu')
    zhipu_api_key: str = Field(default='')
    zhipu_base_url: str = Field(default='https://open.bigmodel.cn/api/paas/v4/')
    zhipu_model: str = Field(default='')

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

    rsshub_base_url: str = Field(default='')
    rsshub_enabled: bool = Field(default=False)
    rsshub_timeout_seconds: int = Field(default=20)
    rsshub_max_items_per_source: int = Field(default=20)

    default_send_time: str = Field(default='22:00')
    timezone: str = Field(default='Asia/Shanghai')


def load_app_config() -> AppConfig:
    return AppConfig(
        digest_topic=os.getenv('DIGEST_TOPIC', 'AI'),
        digest_lookback_hours=int(os.getenv('DIGEST_LOOKBACK_HOURS', '24')),
        max_llm_candidates=int(os.getenv('MAX_LLM_CANDIDATES', '50')),
        main_digest_min_items=int(os.getenv('MAIN_DIGEST_MIN_ITEMS', '10')),
        main_digest_max_items=int(os.getenv('MAIN_DIGEST_MAX_ITEMS', '15')),
        llm_provider=os.getenv('LLM_PROVIDER', 'zhipu'),
        zhipu_api_key=os.getenv('ZHIPU_API_KEY', ''),
        zhipu_base_url=os.getenv('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4/'),
        zhipu_model=os.getenv('ZHIPU_MODEL', ''),
        github_token=os.getenv('GITHUB_TOKEN', ''),
        smtp_host=os.getenv('SMTP_HOST', 'smtp.qq.com'),
        smtp_port=int(os.getenv('SMTP_PORT', '465')),
        smtp_use_ssl=os.getenv('SMTP_USE_SSL', 'true').strip().lower() in {'1', 'true', 'yes', 'on'},
        sender_email=os.getenv('SENDER_EMAIL', ''),
        smtp_auth_code=os.getenv('SMTP_AUTH_CODE', ''),
        recipient_email=os.getenv('RECIPIENT_EMAIL', ''),
        recipient_emails=os.getenv('RECIPIENT_EMAILS', ''),
        max_recipients_per_run=int(os.getenv('MAX_RECIPIENTS_PER_RUN', '5')),
        send_email=os.getenv('SEND_EMAIL', 'false').strip().lower() in {'1', 'true', 'yes', 'on'},
        dry_run=os.getenv('DRY_RUN', 'false').strip().lower() in {'1', 'true', 'yes', 'on'},
        rsshub_base_url=os.getenv('RSSHUB_BASE_URL', ''),
        rsshub_enabled=os.getenv('RSSHUB_ENABLED', 'false').strip().lower() in {'1', 'true', 'yes', 'on'},
        rsshub_timeout_seconds=int(os.getenv('RSSHUB_TIMEOUT_SECONDS', '20')),
        rsshub_max_items_per_source=int(os.getenv('RSSHUB_MAX_ITEMS_PER_SOURCE', '20')),
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
    sources = data if isinstance(data, list) else data.get('sources', [])
    enabled_sources: list[dict[str, Any]] = []
    for source in sources:
        if isinstance(source, dict) and source.get('enabled', True):
            enabled_sources.append(source)
    return enabled_sources
