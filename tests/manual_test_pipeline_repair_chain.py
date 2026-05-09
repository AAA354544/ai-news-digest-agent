from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_app_config
from src.models import CandidateNews
from src.processors.analyzer import analyze_candidates_with_llm


BROKEN_FINAL_JSON = '''
{
  "date": "2026-05-09",
  "topic": "AI",
  "main_digest": [
    {
      "category_name": "技术与模型进展",
      "items": [
        {
          "title": "oracle-devrel / oracle-ai-developer-hub",
          links": [
            "https://github.com/oracle-devrel/oracle-ai-developer-hub"
          ],
          "tags": ["open_source"],
          "summary": "repo update",
          "why_it_matters": "ecosystem relevance",
          "insights": "developer trend",
          "source_names": ["GitHub Trending AI"]
        }
      ]
    }
  ],
  "appendix": [
    {
      "title": "extra item",
      "url": "https://example.com/extra",
      "source_name": "Example",
      "summary": "supplement"
    }
  ],
  "source_statistics": {
    "total_candidates": 1,
    "cleaned_candidates": 1,
    "selected_items": 99,
    "source_count": 1,
    "international_count": 1,
    "chinese_count": 0,
    "appendix_items": 26
  }
}
'''


def main() -> None:
    try:
        from src.processors import llm_client as llm_client_module
    except ModuleNotFoundError as exc:
        print(f'Skip repair-chain simulation: missing dependency ({exc}).')
        return

    cfg = load_app_config()

    candidates = [
        CandidateNews(
            id='c1',
            title='oracle-devrel / oracle-ai-developer-hub',
            url='https://github.com/oracle-devrel/oracle-ai-developer-hub',
            source_name='GitHub Trending AI',
            source_type='github_trending',
            region='international',
            language='en',
            summary_or_snippet='repo update',
        )
    ]

    original_chat_json = llm_client_module.LLMClient.chat_json

    def fake_chat_json(self, system_prompt: str, user_prompt: str, stage: str = 'final') -> str:  # noqa: ANN001
        if stage == 'final':
            return BROKEN_FINAL_JSON
        return '{"scores": []}'

    llm_client_module.LLMClient.chat_json = fake_chat_json
    try:
        digest = analyze_candidates_with_llm(candidates=candidates, config=cfg, topic_override='AI')
    finally:
        llm_client_module.LLMClient.chat_json = original_chat_json

    selected = sum(len(g.items) for g in digest.main_digest)
    appendix = len(digest.appendix)

    assert selected <= max(15, cfg.main_digest_max_items), 'selected items should be capped by postprocess'
    assert appendix <= max(25, cfg.appendix_max_items), 'appendix items should be capped by postprocess'
    assert digest.source_statistics.selected_items == selected, 'selected_items should match actual count'
    assert digest.source_statistics.appendix_items == appendix, 'appendix_items should match actual count'

    print('Pipeline repair-chain simulation passed.')


if __name__ == '__main__':
    main()
