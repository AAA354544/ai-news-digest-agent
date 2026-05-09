from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any

from openai import APITimeoutError, OpenAI, RateLimitError

from src.config import AppConfig, load_app_config

DEFAULT_ZHIPU_MAX_TOKENS = 8192


class LLMClient:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_app_config()
        if self.config.llm_provider.lower() != "zhipu":
            raise NotImplementedError(f"LLM provider '{self.config.llm_provider}' is not implemented yet.")

        self.client = OpenAI(
            api_key=self.config.zhipu_api_key,
            base_url=self.config.zhipu_base_url,
            timeout=120,
        )
        self.model_name = self.config.llm_final_model or self.config.zhipu_model

    def _to_serializable(self, value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump(mode="json")
            except TypeError:
                return value.model_dump()
        if isinstance(value, (dict, list, str, int, float, bool)):
            return value
        return str(value)

    def _save_empty_response_debug(self, resp: Any) -> Path:
        out_dir = Path("data/digested")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{date.today().isoformat()}_llm_empty_response_debug.json"

        choices = getattr(resp, "choices", None)
        has_choices = bool(choices)
        first_choice = choices[0] if has_choices else None
        message = getattr(first_choice, "message", None) if first_choice else None
        finish_reason = getattr(first_choice, "finish_reason", None) if first_choice else None
        usage = getattr(resp, "usage", None)

        debug_payload = {
            "has_choices": has_choices,
            "finish_reason": finish_reason,
            "message": self._to_serializable(message),
            "usage": self._to_serializable(usage),
            "response": self._to_serializable(resp),
        }
        out_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_path

    def chat_json(self, system_prompt: str, user_prompt: str) -> str:
        max_attempts = 3  # initial try + up to 2 retries
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=0.2,
                    max_tokens=DEFAULT_ZHIPU_MAX_TOKENS,
                    extra_body={
                        "thinking": {
                            "type": "disabled",
                        }
                    },
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )

                choices = getattr(resp, "choices", None)
                has_choices = bool(choices)
                first_choice = choices[0] if has_choices else None
                finish_reason = getattr(first_choice, "finish_reason", None) if first_choice else None
                message = getattr(first_choice, "message", None) if first_choice else None
                usage = getattr(resp, "usage", None)
                content = getattr(message, "content", None) if message is not None else None

                print(f"LLM response debug: has_choices={has_choices}, finish_reason={finish_reason}")
                if usage is not None:
                    print(f"LLM response usage: {self._to_serializable(usage)}")

                if not content or not str(content).strip():
                    debug_path = self._save_empty_response_debug(resp)
                    raise RuntimeError(
                        f"LLM API returned empty response content. Debug response saved to: {debug_path}"
                    )

                return str(content)
            except (APITimeoutError, RateLimitError, TimeoutError, ConnectionError, OSError) as exc:
                last_exc = exc
                if attempt < max_attempts:
                    print("LLM call failed, retrying...")
                    time.sleep(min(2 * attempt, 5))
                    continue
                break
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                if attempt < max_attempts and any(token in msg for token in ["timeout", "429", "rate", "temporar", "connection"]):
                    print("LLM call failed, retrying...")
                    time.sleep(min(2 * attempt, 5))
                    continue
                break

        raise RuntimeError(f"LLM API call failed: {last_exc}") from last_exc
