from __future__ import annotations

from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import run_full_pipeline


def main() -> None:
    outputs = run_full_pipeline(send_email=False, llm_candidate_limit=5, topic_override="AI")
    print(f"raw path: {outputs.get('raw_path')}")
    print(f"cleaned path: {outputs.get('cleaned_path')}")
    print(f"digest path: {outputs.get('digest_path')}")
    print(f"markdown path: {outputs.get('markdown_path')}")
    print(f"html path: {outputs.get('html_path')}")
    print(f"source health path: {outputs.get('source_health_path')}")
    print(f"pipeline summary: {outputs.get('pipeline_summary')}")
    print(f"email result: {outputs.get('email_result')}")

    summary = outputs.get('pipeline_summary') or {}
    digest_path = outputs.get('digest_path')
    digest_payload = {}
    if digest_path:
        try:
            digest_payload = json.loads(Path(str(digest_path)).read_text(encoding='utf-8'))
        except Exception:
            digest_payload = {}
    selected_items = summary.get('selected_items')
    appendix_items = summary.get('appendix_items')
    if selected_items is not None:
        assert int(selected_items) <= 15, f"selected_items should be <= 15, got {selected_items}"
        assert int(selected_items) >= 10, f"selected_items should be >= 10, got {selected_items}"
        if summary.get('cleaned_candidates') and int(summary.get('cleaned_candidates') or 0) >= 50:
            assert int(selected_items) >= 10, "selected_items should be >= 10 when cleaned pool is sufficient"
    if appendix_items is not None:
        assert int(appendix_items) <= 10, f"appendix_items should be <= 10, got {appendix_items}"
        assert int(appendix_items) >= 5, f"appendix_items should be >= 5, got {appendix_items}"
        if summary.get('cleaned_candidates') and int(summary.get('cleaned_candidates') or 0) >= 50:
            assert int(appendix_items) >= 5, "appendix_items should be >= 5 when cleaned pool is sufficient"
        if int(appendix_items) < 5:
            assert bool(summary.get('appendix_shortage_reason')), 'appendix < 5 must include appendix_shortage_reason'

    print(f"selected_research_count: {summary.get('selected_research_count')}")
    print(f"research_quota_met: {summary.get('research_quota_met')}")
    print(f"raw_candidates: {summary.get('raw_candidates')}")
    print(f"cleaned_candidates: {summary.get('cleaned_candidates')}")
    print(f"dedup_candidates: {summary.get('dedup_candidates')}")
    print(f"event_clusters: {summary.get('event_clusters')}")
    print(f"final_llm_events: {summary.get('final_llm_events')}")
    print(f"selected_items: {summary.get('selected_items')}")
    print(f"appendix_items: {summary.get('appendix_items')}")
    print(f"selected_international_count: {summary.get('selected_international_count')}")
    print(f"selected_chinese_count: {summary.get('selected_chinese_count')}")
    print(f"arxiv_status: {summary.get('arxiv_status')}")
    print(f"semantic_scholar_status: {summary.get('semantic_scholar_status')}")
    print(f"final_model_used: {summary.get('final_model_used')}")
    print(f"final_fallback_used: {summary.get('final_fallback_used')}")
    print(f"final_fallback_reason: {summary.get('final_fallback_reason')}")
    print(f"appendix_shortage_reason: {summary.get('appendix_shortage_reason')}")
    print(f"main_backfill_used: {summary.get('main_backfill_used')}")
    print(f"main_backfill_count: {summary.get('main_backfill_count')}")
    rq_met = summary.get('research_quota_met')
    rq_reason = summary.get('research_shortage_reason')
    if rq_met is True:
        assert not rq_reason, "research_quota_met=True should not have shortage reason"
    if rq_met is False:
        assert bool(rq_reason), "research_quota_met=False should provide shortage reason"
    if str(summary.get('arxiv_status', '')).lower() == 'ok' and int(summary.get('raw_research_candidates') or 0) > 0:
        assert int(summary.get('cleaned_research_candidates') or 0) > 0, "arxiv ok with raw research should preserve some cleaned research"
    if str(summary.get('arxiv_status', '')).lower() == 'ok' and int(summary.get('raw_research_candidates') or 0) >= 3:
        assert int(summary.get('selected_research_count') or 0) >= 1, "arxiv ok with enough raw research should keep at least 1 selected research item"
    if str(summary.get('arxiv_status', '')).lower() == 'ok' and int(summary.get('raw_research_candidates') or 0) > 0:
        total_research = int(summary.get('selected_research_count') or 0) + int(summary.get('appendix_research_count') or 0)
        assert total_research >= 1, "when arxiv is available, selected+appendix research should not be zero"
        assert str(summary.get('research_shortage_reason') or '') != 'insufficient_research_candidates:0<3', "research shortage reason should not stay at 0<3 when arxiv is available"
    if digest_payload:
        stats = digest_payload.get('source_statistics', {})
        appendix_len = len(digest_payload.get('appendix', []))
        main_len = sum(len(g.get('items', [])) for g in digest_payload.get('main_digest', []) if isinstance(g, dict))
        assert int(stats.get('appendix_items') or 0) == appendix_len, "appendix_items must equal len(digest.appendix)"
        assert int(stats.get('appendix_count') or 0) == appendix_len, "appendix_count must equal len(digest.appendix)"
        assert int(stats.get('selected_items') or 0) == main_len, "selected_items must equal main_digest item count"

    print("Module 7 pipeline test completed.")


if __name__ == "__main__":
    main()
