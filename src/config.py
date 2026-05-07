from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env only for configuration reading.
load_dotenv(BASE_DIR / '.env')


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

    default_send_time: str = Field(default='22:00')
    timezone: str = Field(default='Asia/Shanghai')


def load_app_config() -> AppConfig:
    """Read runtime settings from environment variables (.env supported)."""
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
        default_send_time=os.getenv('DEFAULT_SEND_TIME', '22:00'),
        timezone=os.getenv('TIMEZONE', 'Asia/Shanghai'),
    )


def load_sources_config(path: str = 'config/sources.yaml') -> dict[str, Any] | list[dict[str, Any]]:
    """Load source definitions from YAML file."""
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


def get_enabled_sources(path: str = 'config/sources.yaml') -> list[dict[str, Any]]:
    """Return sources with enabled=true. Missing enabled defaults to true."""
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
