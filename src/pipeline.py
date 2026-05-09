from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.config import get_enabled_sources, load_app_config
from src.fetchers.base import BaseFetcher
from src.models import CandidateNews
from src.utils.http_utils import is_placeholder_url
from src.utils.source_health import save_source_health


def _find_latest_file(input_dir: str, pattern: str) -> Path:
    base = Path(input_dir)
    files = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No files found for pattern '{pattern}' in '{input_dir}'.")
    return files[0]


def _to_json_compatible(items: list[CandidateNews]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, 'model_dump'):
            result.append(item.model_dump(mode='json'))
        else:
            result.append(item.dict())
    return result


def _load_candidates(path: Path) -> list[CandidateNews]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, list):
        return []

    items: list[CandidateNews] = []
    for idx, entry in enumerate(payload):
        try:
            if hasattr(CandidateNews, 'model_validate'):
                items.append(CandidateNews.model_validate(entry))
            else:
                items.append(CandidateNews(**entry))
        except Exception as exc:
            print(f'skip invalid item at index {idx}: {exc}')
    return items


def _build_fetcher(source: dict[str, Any]) -> BaseFetcher | None:
    source_type = source.get('type', '').strip()
    if source_type == 'rss':
        from src.fetchers.rss_fetcher import RSSFetcher

        return RSSFetcher(source)
    if source_type == 'hn_algolia':
        from src.fetchers.hn_fetcher import HackerNewsFetcher

        return HackerNewsFetcher(source)
    if source_type == 'arxiv':
        from src.fetchers.arxiv_fetcher import ArxivFetcher

        return ArxivFetcher(source)
    if source_type == 'github_trending':
        from src.fetchers.github_trending_fetcher import GitHubTrendingFetcher

        return GitHubTrendingFetcher(source)
    if source_type == 'rss_or_web':
        from src.fetchers.rss_fetcher import RSSFetcher

        return RSSFetcher(source)
    if source_type == 'semantic_scholar':
        from src.fetchers.semantic_scholar_fetcher import SemanticScholarFetcher

        return SemanticScholarFetcher(source)
    if source_type == 'crossref':
        from src.fetchers.crossref_fetcher import CrossrefFetcher

        return CrossrefFetcher(source)
    if source_type == 'gdelt':
        from src.fetchers.gdelt_fetcher import GDELTFetcher

        return GDELTFetcher(source)
    if source_type == 'github_api':
        from src.fetchers.github_api_fetcher import GitHubAPIFetcher

        return GitHubAPIFetcher(source)
    if source_type == 'rsshub':
        from src.fetchers.rsshub_fetcher import RSSHubFetcher

        cfg = load_app_config()
        return RSSHubFetcher(source, rsshub_base_url=cfg.rsshub_base_url, enabled=cfg.rsshub_enabled)
    return None


def run_fetch_step() -> Path:
    enabled_sources = get_enabled_sources()
    all_candidates: list[CandidateNews] = []
    health_records: list[dict[str, Any]] = []

    for source in enabled_sources:
        source_name = source.get('name', 'UNKNOWN')
        source_type = source.get('type', '')
        endpoint = str(source.get('url_or_endpoint', ''))

        fetcher = _build_fetcher(source)
        if fetcher is None:
            print(f'[fetch] skipped unsupported source type: {source_name} ({source_type})')
            health_records.append(
                {
                    'name': source_name,
                    'type': source_type,
                    'enabled': bool(source.get('enabled', True)),
                    'status': 'failed_but_continued',
                    'count': 0,
                    'note': 'unsupported source type',
                }
            )
            continue

        if is_placeholder_url(endpoint):
            print(f'[fetch] {source_name}: 0 (skipped_placeholder)')
            health_records.append(
                {
                    'name': source_name,
                    'type': source_type,
                    'enabled': bool(source.get('enabled', True)),
                    'status': 'skipped_placeholder',
                    'count': 0,
                    'note': 'placeholder endpoint',
                }
            )
            continue

        try:
            items = fetcher.fetch()
            health = fetcher.get_health()
            status = health.get('status', 'ok')
            note = health.get('note', '')
            print(f'[fetch] {source_name}: {len(items)} ({status})')
            all_candidates.extend(items)
            health_records.append(
                {
                    'name': source_name,
                    'type': source_type,
                    'enabled': bool(source.get('enabled', True)),
                    'status': 'ok' if len(items) > 0 else (status or 'empty'),
                    'count': len(items),
                    'note': note,
                }
            )
        except Exception as exc:
            print(f'[fetch] failed {source_name}: {exc}')
            health_records.append(
                {
                    'name': source_name,
                    'type': source_type,
                    'enabled': bool(source.get('enabled', True)),
                    'status': 'failed_but_continued',
                    'count': 0,
                    'note': str(exc),
                }
            )

    out_dir = Path('data/raw')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_raw_candidates.json"
    out_path.write_text(json.dumps(_to_json_compatible(all_candidates), ensure_ascii=False, indent=2), encoding='utf-8')

    health_path = save_source_health(health_records, output_dir=str(out_dir))
    print(f'[fetch] source health saved: {health_path}')
    return out_path


def run_clean_step() -> Path:
    from src.processors.cleaner import clean_candidates
    from src.processors.deduplicator import deduplicate_by_url, prepare_llm_candidates

    cfg = load_app_config()
    raw_path = _find_latest_file('data/raw', '*_raw_candidates.json')
    raw_candidates = _load_candidates(raw_path)

    cleaned_only = clean_candidates(raw_candidates, lookback_hours=cfg.digest_lookback_hours)
    deduped_only = deduplicate_by_url(cleaned_only)
    final_candidates = prepare_llm_candidates(
        raw_candidates,
        lookback_hours=cfg.digest_lookback_hours,
        max_candidates=cfg.max_llm_candidates,
    )

    print(f'[clean] raw={len(raw_candidates)}, cleaned={len(cleaned_only)}, dedup={len(deduped_only)}, final={len(final_candidates)}')

    out_dir = Path('data/cleaned')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}_cleaned_candidates.json"
    out_path.write_text(json.dumps(_to_json_compatible(final_candidates), ensure_ascii=False, indent=2), encoding='utf-8')
    return out_path


def run_analyze_step(limit_for_test: int | None = None) -> Path:
    from src.processors.analyzer import analyze_candidates_with_llm, save_digest

    cfg = load_app_config()
    cleaned_path = _find_latest_file('data/cleaned', '*_cleaned_candidates.json')
    candidates = _load_candidates(cleaned_path)

    limit = limit_for_test if limit_for_test is not None else cfg.max_llm_candidates
    limit = max(1, limit)
    limited = candidates[: min(len(candidates), limit)]

    digest = analyze_candidates_with_llm(limited, config=cfg)
    return save_digest(digest, output_dir='data/digested')


def run_report_step() -> tuple[Path, Path]:
    from src.generators.report_generator import load_latest_digest, render_html_report, render_markdown_report, save_report_files

    digest = load_latest_digest(input_dir='data/digested')
    markdown_text = render_markdown_report(digest, template_dir='templates')
    html_text = render_html_report(digest, template_dir='templates')
    return save_report_files(digest, markdown_text, html_text, output_base_dir='outputs')


def run_email_step() -> None:
    from src.notifiers.email_sender import EmailSender

    html_path = _find_latest_file('outputs/html', '*-ai-news-digest.html')
    md_path = _find_latest_file('outputs/markdown', '*-ai-news-digest.md')
    EmailSender().send_digest_email(html_path=html_path, markdown_path=md_path)


def run_full_pipeline(send_email: bool = False, llm_candidate_limit: int | None = None) -> dict[str, Path | None]:
    raw_path = run_fetch_step()
    cleaned_path = run_clean_step()
    digest_path = run_analyze_step(limit_for_test=llm_candidate_limit)
    md_path, html_path = run_report_step()

    if send_email:
        run_email_step()

    return {
        'raw_path': raw_path,
        'cleaned_path': cleaned_path,
        'digest_path': digest_path,
        'markdown_path': md_path,
        'html_path': html_path,
    }
