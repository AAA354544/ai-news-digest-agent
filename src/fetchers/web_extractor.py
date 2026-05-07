from __future__ import annotations

def extract_text_from_url(url: str) -> str | None:
    if not url:
        return None
    try:
        import trafilatura
    except ImportError:
        print("[web_extractor] trafilatura not available; skip extraction.")
        return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded)
        return text.strip() if text else None
    except Exception as exc:
        print(f"[web_extractor] Failed to extract text from {url}: {exc}")
        return None
