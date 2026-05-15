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
            '论文与科研进展',
            '模型与技术进展',
            'Agent 与 AI 工具',
            '开源项目与开发者生态',
            '产业与公司动态',
            '政策安全与风险',
        ],
    },
}

_BOOL_TRUE = {'1', 'true', 'yes', 'on'}
_BOOL_FALSE = {'0', 'false', 'no', 'off'}
_PLACEHOLDER_MARKERS = ('your_', 'example', 'placeholder', 'changeme', 'todo')


class AppConfig(BaseModel):
    digest_topic: str = Field(default='AI')
    digest_lookback_hours: int = Field(default=24)
    max_llm_candidates: int = Field(default=50)
    main_digest_min_items: int = Field(default=12)
    main_digest_max_items: int = Field(default=15)

    llm_provider: str = Field(default='zhipu')
    zhipu_api_key: str = Field(default='')
    zhipu_base_url: str = Field(default='https://open.bigmodel.cn/api/paas/v4')
    zhipu_model: str = Field(default='')

    # Reserved for future provider support; currently not implemented by LLMClient.
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

    default_send_time: str = Field(default='22:00')
    timezone: str = Field(default='Asia/Shanghai')


def is_placeholder_value(value: str | None) -> bool:
    normalized = (value or '').strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


def _env_text(name: str, default: str = '') -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    if value == '':
        return default
    return value


def _env_int(name: str, default: int, min_value: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == '':
        value = default
    else:
        try:
            value = int(raw.strip())
        except ValueError as exc:
            raise ValueError(
                f"Environment variable {name} must be an integer. Current value: '{raw}'."
            ) from exc

    if min_value is not None and value < min_value:
        raise ValueError(f"Environment variable {name} must be >= {min_value}. Current value: {value}.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == '':
        return default
    normalized = raw.strip().lower()
    if normalized in _BOOL_TRUE:
        return True
    if normalized in _BOOL_FALSE:
        return False
    raise ValueError(
        f"Environment variable {name} must be one of true/false/1/0/yes/no/on/off. Current value: '{raw}'."
    )


def load_app_config() -> AppConfig:
    return AppConfig(
        digest_topic=_env_text('DIGEST_TOPIC', 'AI'),
        digest_lookback_hours=_env_int('DIGEST_LOOKBACK_HOURS', 24, min_value=1),
        max_llm_candidates=_env_int('MAX_LLM_CANDIDATES', 50, min_value=1),
        main_digest_min_items=_env_int('MAIN_DIGEST_MIN_ITEMS', 10, min_value=1),
        main_digest_max_items=_env_int('MAIN_DIGEST_MAX_ITEMS', 15, min_value=1),
        llm_provider=_env_text('LLM_PROVIDER', 'zhipu').lower(),
        zhipu_api_key=_env_text('ZHIPU_API_KEY', ''),
        zhipu_base_url=_env_text('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4').rstrip('/'),
        zhipu_model=_env_text('ZHIPU_MODEL', ''),
        deepseek_api_key=_env_text('DEEPSEEK_API_KEY', ''),
        deepseek_base_url=_env_text('DEEPSEEK_BASE_URL', ''),
        deepseek_model=_env_text('DEEPSEEK_MODEL', ''),
        qwen_api_key=_env_text('QWEN_API_KEY', ''),
        qwen_base_url=_env_text('QWEN_BASE_URL', ''),
        qwen_model=_env_text('QWEN_MODEL', ''),
        github_token=_env_text('GITHUB_TOKEN', ''),
        smtp_host=_env_text('SMTP_HOST', 'smtp.qq.com'),
        smtp_port=_env_int('SMTP_PORT', 465, min_value=1),
        smtp_use_ssl=_env_bool('SMTP_USE_SSL', True),
        sender_email=_env_text('SENDER_EMAIL', ''),
        smtp_auth_code=_env_text('SMTP_AUTH_CODE', ''),
        recipient_email=_env_text('RECIPIENT_EMAIL', ''),
        default_send_time=_env_text('DEFAULT_SEND_TIME', '22:00'),
        timezone=_env_text('TIMEZONE', 'Asia/Shanghai'),
    )


def validate_runtime_config(mode: str = 'local') -> dict[str, object]:
    """Validate required runtime config for different execution modes.

    Modes:
    - local: basic run without forced email sending
    - send-email: CLI/Streamlit email sending
    - github-actions-report: workflow run without sending email
    - github-actions-send: workflow run with email delivery
    """

    errors: list[str] = []
    warnings: list[str] = []

    try:
        cfg = load_app_config()
    except ValueError as exc:
        return {'ok': False, 'errors': [str(exc)], 'warnings': []}

    if cfg.llm_provider != 'zhipu':
        errors.append(
            f"LLM_PROVIDER='{cfg.llm_provider}' is not implemented yet. Please use 'zhipu'."
        )

    if is_placeholder_value(cfg.zhipu_api_key):
        errors.append('ZHIPU_API_KEY is missing or still placeholder.')
    if is_placeholder_value(cfg.zhipu_model):
        errors.append('ZHIPU_MODEL is missing or still placeholder.')

    if cfg.main_digest_min_items > cfg.main_digest_max_items:
        errors.append('MAIN_DIGEST_MIN_ITEMS should be <= MAIN_DIGEST_MAX_ITEMS.')

    send_mode = mode in {'send-email', 'github-actions-send'}
    if send_mode:
        if is_placeholder_value(cfg.sender_email):
            errors.append('SENDER_EMAIL is missing or still placeholder.')
        if is_placeholder_value(cfg.smtp_auth_code):
            errors.append('SMTP_AUTH_CODE is missing or still placeholder.')
        if is_placeholder_value(cfg.smtp_host):
            errors.append('SMTP_HOST is missing or still placeholder.')
        if is_placeholder_value(cfg.recipient_email):
            errors.append('RECIPIENT_EMAIL is missing or still placeholder.')

    if cfg.deepseek_api_key or cfg.deepseek_model or cfg.qwen_api_key or cfg.qwen_model:
        warnings.append('DEEPSEEK/QWEN fields are reserved for future provider support and are not active yet.')

    return {'ok': len(errors) == 0, 'errors': errors, 'warnings': warnings}


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
