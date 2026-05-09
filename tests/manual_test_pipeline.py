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
    print("Module 7 pipeline test completed.")


if __name__ == "__main__":
    main()
