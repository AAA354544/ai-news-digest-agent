from __future__ import annotations

from src.utils.http_utils import build_default_headers, is_placeholder_url


def extract_text_from_url(url: str) -> str | None:
    if not url or is_placeholder_url(url):
        return None
    try:
        import trafilatura
    except ImportError:
        print('[web_extractor] trafilatura not available; skip extraction.')
        return None

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded)
        return text.strip() if text else None
    except Exception as exc:
        print(f'[web_extractor] failed to extract text from {url}: {exc}')
        return None
