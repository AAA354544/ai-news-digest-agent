from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

import requests

_PLACEHOLDER_MARKERS = {'', 'todo', 'placeholder', 'tbd', 'unknown', '待确认'}

_LAST_REQUEST_TS_BY_HOST: dict[str, float] = {}
_CACHE: dict[str, tuple[float, 'SafeHTTPResponse']] = {}


@dataclass
class SafeHTTPResponse:
    status_code: int
    text: str
    headers: dict[str, str]
    url: str

    def json(self) -> Any:
        return json.loads(self.text)


@dataclass
class SafeGetResult:
    response: SafeHTTPResponse | None
    status: str
    note: str = ''


def build_default_headers() -> dict[str, str]:
    return {
        'User-Agent': 'ai-news-digest-agent/0.1 (+public-feed-fetch; contact: maintainers)',
        'Accept': 'application/json,text/html,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    }


def is_placeholder_url(value: str) -> bool:
    normalized = (value or '').strip().lower()
    return normalized in _PLACEHOLDER_MARKERS


def _cache_key(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    return f"{url}?{urlencode(sorted(params.items()), doseq=True)}"


def safe_get(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 20,
    max_retries: int = 2,
    sleep_seconds: float = 1.0,
    headers: dict[str, str] | None = None,
    request_interval_seconds: float = 0.5,
    cache_ttl_seconds: int = 0,
) -> SafeGetResult:
    if is_placeholder_url(url):
        return SafeGetResult(response=None, status='skipped_placeholder', note='placeholder endpoint')

    key = _cache_key(url, params)
    now = time.time()
    if cache_ttl_seconds > 0 and key in _CACHE:
        ts, cached = _CACHE[key]
        if now - ts <= cache_ttl_seconds:
            return SafeGetResult(response=cached, status='ok', note='cache_hit')

    req_headers = build_default_headers()
    if headers:
        req_headers.update(headers)

    host = urlsplit(url).netloc
    last_ts = _LAST_REQUEST_TS_BY_HOST.get(host)
    if last_ts is not None and request_interval_seconds > 0:
        delta = now - last_ts
        if delta < request_interval_seconds:
            time.sleep(request_interval_seconds - delta)

    attempts = max_retries + 1
    backoff = max(0.5, sleep_seconds)
    for i in range(attempts):
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers=req_headers)
            _LAST_REQUEST_TS_BY_HOST[host] = time.time()

            if resp.status_code == 429:
                retry_after = resp.headers.get('Retry-After')
                wait = backoff
                if retry_after and retry_after.isdigit():
                    wait = max(wait, float(retry_after))
                if i < max_retries:
                    print(f"[http_utils] 429 for {url}. wait {wait:.1f}s and retry...")
                    time.sleep(wait)
                    backoff *= 2
                    continue
                return SafeGetResult(response=None, status='rate_limited', note='429')

            if resp.status_code == 403:
                return SafeGetResult(response=None, status='http_403', note='403')
            if resp.status_code == 404:
                return SafeGetResult(response=None, status='http_404', note='404')

            resp.raise_for_status()
            safe_resp = SafeHTTPResponse(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                url=resp.url,
            )
            if cache_ttl_seconds > 0:
                _CACHE[key] = (time.time(), safe_resp)
            return SafeGetResult(response=safe_resp, status='ok')

        except requests.Timeout:
            if i < max_retries:
                print(f"[http_utils] timeout for {url}. retry...")
                time.sleep(backoff)
                backoff *= 2
                continue
            return SafeGetResult(response=None, status='timeout', note='timeout')
        except requests.RequestException as exc:
            if i < max_retries:
                print(f"[http_utils] request error for {url}: {exc}. retry...")
                time.sleep(backoff)
                backoff *= 2
                continue
            return SafeGetResult(response=None, status='failed_but_continued', note=str(exc))

    return SafeGetResult(response=None, status='failed_but_continued', note='unknown')
