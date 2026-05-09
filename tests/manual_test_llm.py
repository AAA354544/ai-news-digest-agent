from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_app_config
from src.models import CandidateNews
from src.processors.analyzer import analyze_candidates_with_llm, save_digest
from src.processors.llm_client import LLMClient


def _find_latest_cleaned_file(cleaned_dir: Path) -> Path | None:
    files = sorted(cleaned_dir.glob("*_cleaned_candidates.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_cleaned_candidates(path: Path) -> list[CandidateNews]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []

    candidates: list[CandidateNews] = []
    for idx, item in enumerate(data):
        try:
            if hasattr(CandidateNews, "model_validate"):
                candidates.append(CandidateNews.model_validate(item))
            else:
                candidates.append(CandidateNews(**item))
        except Exception as exc:
            print(f"skip invalid cleaned item at index {idx}: {exc}")
    return candidates


def _resolve_test_limit(default_limit: int = 5) -> int:
    raw = os.getenv("LLM_TEST_CANDIDATE_LIMIT", str(default_limit)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default_limit
    return max(1, value)


def main() -> None:
    cfg = load_app_config()
    cleaned_dir = PROJECT_ROOT / "data" / "cleaned"
    latest_path = _find_latest_cleaned_file(cleaned_dir)
    if latest_path is None:
        print("No cleaned candidates file found. Please run: python tests/manual_test_cleaner.py")
        return

    candidates = _load_cleaned_candidates(latest_path)
    test_limit = _resolve_test_limit(default_limit=5)
    limited = candidates[: min(len(candidates), test_limit)]

    print(f"loaded cleaned candidates count: {len(candidates)}")
    print(f"using candidates for LLM test: {len(limited)}")
    print(f"llm provider: {cfg.llm_provider}")
    print(f"zhipu model: {cfg.zhipu_model}")
    print(f"llm pipeline mode: {cfg.llm_pipeline_mode}")
    try:
        client = LLMClient(config=cfg)
        for stage in ("preprocess", "final", "repair"):
            info = client.stage_info(stage)  # type: ignore[arg-type]
            print(f"{stage} stage -> provider={info['provider']}, model={info['model']}")
    except Exception as exc:
        print(f"llm stage info unavailable: {exc}")
    print(f"topic: {cfg.digest_topic}")

    digest = analyze_candidates_with_llm(limited, config=cfg)
    saved_path = save_digest(digest, output_dir=str(PROJECT_ROOT / "data" / "digested"))

    selected_count = sum(len(group.items) for group in digest.main_digest)
    print(f"digest date: {digest.date}")
    print(f"topic: {digest.topic}")
    print(f"category count: {len(digest.main_digest)}")
    print(f"selected item count: {selected_count}")
    print(f"appendix count: {len(digest.appendix)}")
    print(f"saved path: {saved_path}")

    printed = 0
    for group in digest.main_digest:
        for item in group.items:
            summary_preview = item.summary[:80]
            print(f"- category={group.category_name} | title={item.title} | tags={item.tags} | summary={summary_preview}")
            printed += 1
            if printed >= 3:
                break
        if printed >= 3:
            break

    print("Module 4 LLM analysis test completed.")


if __name__ == "__main__":
    main()
