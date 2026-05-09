from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import DailyDigest
from src.processors.analyzer import local_repair_json_text, normalize_digest_payload


def _must_parse(text: str) -> dict:
    repaired = local_repair_json_text(text)
    return json.loads(repaired)


def main() -> None:
    case1 = '''
{
  "title": "oracle-devrel / oracle-ai-developer-hub",
  links": [
    "https://github.com/oracle-devrel/oracle-ai-developer-hub"
  ]
}
'''
    obj1 = _must_parse(case1)
    assert 'links' in obj1 and isinstance(obj1['links'], list)

    case2 = '''
{
  title: "x",
  links: ["https://example.com"]
}
'''
    obj2 = _must_parse(case2)
    assert obj2.get('title') == 'x'

    case3 = '''
{
  "title": "x",
}
'''
    obj3 = _must_parse(case3)
    assert obj3.get('title') == 'x'

    case4 = '''```json
{"title": "x"}
```'''
    obj4 = _must_parse(case4)
    assert obj4.get('title') == 'x'

    case5 = '''
{
  “title”: “x”,
  "summary": "ok"
}
'''
    obj5 = _must_parse(case5)
    assert obj5.get('title') == 'x'

    case6 = """
{
  'title': 'x',
  'summary': 'hello'
}
"""
    obj6 = _must_parse(case6)
    assert obj6.get('summary') == 'hello'

    # near-complete broken DailyDigest payload should be repairable and normalizable
    case7 = """
```json
{
  date: "2026-05-09",
  topic: "AI",
  main_digest: [
    {
      category_name: "技术与模型进展",
      items: [
        {
          title: "oracle-devrel / oracle-ai-developer-hub",
          links": [
            "https://github.com/oracle-devrel/oracle-ai-developer-hub"
          ],
          tags: ["open_source"],
          summary: "repo update",
          why_it_matters: "ecosystem",
          insights: "developer trend",
          source_names: ["GitHub Trending AI"],
        }
      ],
    }
  ],
  appendix: [
    {
      title: "appendix sample",
      url: "https://example.com/a",
      source_name: "Example",
      summary: "extra"
    }
  ],
  source_statistics: {
    total_candidates: 1,
    cleaned_candidates: 1,
    selected_items: 99,
    source_count: 1,
    international_count: 1,
    chinese_count: 0,
  },
}
```
"""
    repaired7 = local_repair_json_text(case7)
    parsed7 = json.loads(repaired7)
    normalized7 = normalize_digest_payload(parsed7)
    digest7 = DailyDigest.model_validate(normalized7)
    assert digest7.main_digest and digest7.main_digest[0].items
    assert digest7.main_digest[0].items[0].links
    assert digest7.appendix and digest7.appendix[0].link == "https://example.com/a"

    print('Module JSON repair test passed.')


if __name__ == '__main__':
    main()
