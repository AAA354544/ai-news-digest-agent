from __future__ import annotations

import time
from typing import Any

import requests

_PLACEHOLDER_MARKERS = {
    '',
    'todo',
    'placeholder',
    'tbd',
    'unknown',
    '待确认',
}


def build_default_headers() -> dict[str, str]:
    return {
        'User-Agent': 'ai-news-digest-agent/0.1 (+https://github.com/)',
        'Accept': 'application/json,text/html,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    }


def is_placeholder_url(value: str) -> bool:
    normalized = (value or '').strip().lower()
    return normalized in _PLACEHOLDER_MARKERS


def safe_get(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 20,
    max_retries: int = 2,
    sleep_seconds: float = 1.0,
    headers: dict[str, str] | None = None,
) -> requests.Response | None:
    if is_placeholder_url(url):
        return None

    req_headers = build_default_headers()
    if headers:
        req_headers.update(headers)

    attempts = max_retries + 1
    for i in range(attempts):
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers=req_headers)

            if resp.status_code == 429:
                retry_after = resp.headers.get('Retry-After')
                wait = sleep_seconds
                if retry_after and retry_after.isdigit():
                    wait = max(wait, float(retry_after))
                if i < max_retries:
                    print(f"[http_utils] 429 for {url}. waiting {wait}s then retry...")
                    time.sleep(wait)
                    continue
                print(f"[http_utils] 429 for {url}. skip.")
                return None

            if resp.status_code in {403, 404}:
                print(f"[http_utils] {resp.status_code} for {url}. skip.")
                return None

            resp.raise_for_status()
            return resp
        except requests.Timeout:
            if i < max_retries:
                print(f"[http_utils] timeout for {url}. retrying...")
                time.sleep(sleep_seconds)
                continue
            print(f"[http_utils] timeout for {url}. skip.")
            return None
        except requests.RequestException as exc:
            if i < max_retries:
                print(f"[http_utils] request error for {url}: {exc}. retrying...")
                time.sleep(sleep_seconds)
                continue
            print(f"[http_utils] request error for {url}: {exc}. skip.")
            return None

    return None
