from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_app_config
from src.processors.analyzer import parse_llm_json_safely


def main() -> None:
    cfg = load_app_config()
    print(f"llm_pipeline_mode={cfg.llm_pipeline_mode}")
    print(f"llm_preprocess_enabled={cfg.llm_preprocess_enabled}")
    print(f"llm_repair_enabled={cfg.llm_repair_enabled}")
    print(f"preprocess model (config): {cfg.llm_preprocess_model or 'glm-4-flash-250414'}")
    print(f"final primary model (config): {cfg.llm_final_model or cfg.zhipu_model or 'glm-4.7-flash'}")
    print(f"final fallback model (config): {cfg.llm_final_fallback_model}")
    print(f"repair model (config): {cfg.llm_repair_model or 'glm-4-flash-250414'}")

    try:
        from src.processors.llm_client import LLMClient
    except ModuleNotFoundError as exc:
        print(f'LLM client dependency missing, skip layered smoke test: {exc}')
        return

    client = LLMClient(config=cfg)
    for stage in ('preprocess', 'final', 'repair'):
        info = client.stage_info(stage)  # type: ignore[arg-type]
        print(f"{stage}: provider={info['provider']} model={info['model']}")
    print(f"final_fallback_model: {cfg.llm_final_fallback_model}")

    has_key = bool((cfg.zhipu_api_key or cfg.zhipu_preprocess_api_key or cfg.zhipu_final_api_key or cfg.zhipu_repair_api_key).strip())
    if not has_key:
        print('No available Zhipu key detected; skip API smoke tests.')
        return

    try:
        preprocess_text = client.chat_json(
            '你是评分助手，只输出JSON。',
            '返回 {"score":0.8,"label":"high"}',
            stage='preprocess',
        )
        preprocess_payload = parse_llm_json_safely(preprocess_text, config=cfg)
        print(f"preprocess smoke: {preprocess_payload}")
    except Exception as exc:
        print(f"preprocess smoke failed: {exc}")

    try:
        final_text = client.chat_json(
            '你是中文摘要助手。',
            '请用一句中文总结：AI agent memory is improving rapidly.',
            stage='final',
        )
        print(f"final smoke: {final_text[:120]}")
    except Exception as exc:
        print(f"final smoke failed: {exc}")

    try:
        broken_json = '{"a":1,}'
        repaired_text = client.chat_json(
            '你是 JSON 修复助手，只输出JSON。',
            f'请修复这个JSON：{broken_json}',
            stage='repair',
        )
        repaired_payload = parse_llm_json_safely(repaired_text, config=cfg)
        print(f"repair smoke: {repaired_payload}")
    except Exception as exc:
        print(f"repair smoke failed: {exc}")


if __name__ == '__main__':
    main()
