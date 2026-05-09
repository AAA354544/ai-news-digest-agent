from __future__ import annotations

from pathlib import Path
import sys

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
    selected_items = summary.get('selected_items')
    appendix_items = summary.get('appendix_items')
    if selected_items is not None:
        assert int(selected_items) <= 15, f"selected_items should be <= 15, got {selected_items}"
    if appendix_items is not None:
        assert int(appendix_items) <= 25, f"appendix_items should be <= 25, got {appendix_items}"
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

    print("Module 7 pipeline test completed.")


if __name__ == "__main__":
    main()
