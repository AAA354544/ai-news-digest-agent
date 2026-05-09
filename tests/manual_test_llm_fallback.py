from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import AppConfig

try:
    from src.processors.llm_client import LLMClient
except ModuleNotFoundError as exc:
    print(f'Skip LLM fallback test: missing dependency ({exc}).')
    raise SystemExit(0)


class FakeLLMClient(LLMClient):
    def __init__(self, config: AppConfig) -> None:
        super().__init__(config=config)
        self.calls = 0

    def _call_once(self, client, model_name: str, system_prompt: str, user_prompt: str, stage):  # type: ignore[override]
        self.calls += 1
        if stage == 'final' and model_name == 'glm-4.7-flash' and self.calls <= 2:
            raise RuntimeError('该模型当前访问量过大，请您稍后再试')
        return '{"ok": true}'


def main() -> None:
    cfg = AppConfig(
        llm_provider='zhipu',
        zhipu_api_key='fake_key_for_test',
        llm_final_model='glm-4.7-flash',
        llm_final_fallback_model='glm-4-flash-250414',
        llm_final_max_retries=2,
        llm_final_fallback_enabled=True,
    )

    client = FakeLLMClient(config=cfg)
    text = client.chat_json('system', 'user', stage='final')

    assert text.strip().startswith('{')
    assert client.last_final_model_used == 'glm-4-flash-250414'
    assert client.last_final_fallback_used is True

    print(f"final_model_used={client.last_final_model_used}")
    print(f"final_fallback_used={client.last_final_fallback_used}")
    print('Module LLM fallback test passed.')


if __name__ == '__main__':
    main()
