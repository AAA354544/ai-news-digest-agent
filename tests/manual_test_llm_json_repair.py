from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import DailyDigest
from src.processors.analyzer import normalize_digest_payload, parse_llm_json_safely


def main() -> None:
    broken_json = """
{
  "date": "2026-05-08",
  "topic": "AI",
  "main_digest": [
    {
      "category_name": "技术与模型进展",
      "items": [
        {
          "title": "示例",
          "links": ["https://example.com"],
          "tags": ["AI"],
          "summary": "摘要",
          "why_it_matters": "重要性",
          "insights": "趋势",
          "source_names": ["Example"],
        }
      ],
    }
  ],
  "appendix": [],
  "source_statistics": {
    "total_candidates": 1,
    "cleaned_candidates": 1,
    "selected_items": 1,
    "source_count": 1,
    "international_count": 1,
    "chinese_count": 0,
  },
}
"""

    payload = parse_llm_json_safely(broken_json)
    normalized = normalize_digest_payload(payload)
    if hasattr(DailyDigest, "model_validate"):
        DailyDigest.model_validate(normalized)
    else:
        DailyDigest(**normalized)
    print("Module LLM JSON repair test passed.")


if __name__ == "__main__":
    main()
