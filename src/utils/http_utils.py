from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import requests

_PLACEHOLDER_MARKERS = {'', 'todo', 'placeholder', 'tbd', 'unknown', '待确认'}
_LAST_REQUEST_TIME_BY_HOST: dict[str, float] = {}


@dataclass
class SafeGetResult:
    response: requests.Response | None
    status: str
    note: str = ''


def build_default_headers() -> dict[str, str]:
    return {
        'User-Agent': 'ai-news-digest-agent/1.0 (+public-source-only)',
        'Accept': 'application/json,text/html,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    }


def is_placeholder_url(value: str) -> bool:
    normalized = (value or '').strip().lower()
    return normalized in _PLACEHOLDER_MARKERS


def _apply_request_interval(url: str, request_interval_seconds: float) -> None:
    host = urlsplit(url).netloc.lower()
    if not host:
        return
    last_ts = _LAST_REQUEST_TIME_BY_HOST.get(host)
    if last_ts is not None:
        elapsed = time.time() - last_ts
        if elapsed < request_interval_seconds:
            time.sleep(max(0.0, request_interval_seconds - elapsed))
    _LAST_REQUEST_TIME_BY_HOST[host] = time.time()


def safe_get(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 20,
    max_retries: int = 2,
    sleep_seconds: float = 1.0,
    headers: dict[str, str] | None = None,
    request_interval_seconds: float = 0.8,
) -> SafeGetResult:
    if is_placeholder_url(url):
        return SafeGetResult(response=None, status='skipped_placeholder', note='placeholder endpoint')

    req_headers = build_default_headers()
    if headers:
        req_headers.update(headers)

    attempts = max(1, max_retries + 1)
    backoff = max(0.5, sleep_seconds)

    for i in range(attempts):
        try:
            _apply_request_interval(url, request_interval_seconds=request_interval_seconds)
            resp = requests.get(url, params=params, timeout=timeout, headers=req_headers)

            if resp.status_code == 429:
                retry_after = resp.headers.get('Retry-After')
                wait = backoff
                if retry_after and retry_after.isdigit():
                    wait = max(wait, float(retry_after))
                if i < attempts - 1:
                    print(f'[http_utils] 429 for {url}. waiting {wait:.1f}s then retry...')
                    time.sleep(wait)
                    backoff *= 2
                    continue
                return SafeGetResult(response=None, status='rate_limited', note='429')

            if resp.status_code == 403:
                return SafeGetResult(response=None, status='http_403', note='403')
            if resp.status_code == 404:
                return SafeGetResult(response=None, status='http_404', note='404')

            resp.raise_for_status()
            return SafeGetResult(response=resp, status='ok')

        except requests.Timeout:
            if i < attempts - 1:
                print(f'[http_utils] timeout for {url}. retrying...')
                time.sleep(backoff)
                backoff *= 2
                continue
            return SafeGetResult(response=None, status='timeout', note='timeout')
        except requests.RequestException as exc:
            if i < attempts - 1:
                print(f'[http_utils] request error for {url}: {exc}. retrying...')
                time.sleep(backoff)
                backoff *= 2
                continue
            return SafeGetResult(response=None, status='failed_but_continued', note=str(exc))

    return SafeGetResult(response=None, status='failed_but_continued', note='unknown request failure')
