from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Literal

from openai import APITimeoutError, OpenAI, RateLimitError

from src.config import AppConfig, load_app_config

DEFAULT_ZHIPU_MAX_TOKENS = 8192
LLMStage = Literal['preprocess', 'final', 'repair']


class LLMClient:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_app_config()
        self.last_final_model_used: str | None = None
        self.last_final_fallback_used: bool = False
        self.last_final_fallback_reason: str = ''
        if self.config.llm_provider.lower() != 'zhipu':
            raise NotImplementedError(f"LLM provider '{self.config.llm_provider}' is not implemented yet.")

    def _to_serializable(self, value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, 'model_dump'):
            try:
                return value.model_dump(mode='json')
            except TypeError:
                return value.model_dump()
        if isinstance(value, (dict, list, str, int, float, bool)):
            return value
        return str(value)

    def _save_empty_response_debug(self, resp: Any) -> Path:
        out_dir = Path('data/digested')
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f'{date.today().isoformat()}_llm_empty_response_debug.json'

        choices = getattr(resp, 'choices', None)
        has_choices = bool(choices)
        first_choice = choices[0] if has_choices else None
        message = getattr(first_choice, 'message', None) if first_choice else None
        finish_reason = getattr(first_choice, 'finish_reason', None) if first_choice else None
        usage = getattr(resp, 'usage', None)

        debug_payload = {
            'has_choices': has_choices,
            'finish_reason': finish_reason,
            'message': self._to_serializable(message),
            'usage': self._to_serializable(usage),
            'response': self._to_serializable(resp),
        }
        out_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return out_path

    def _resolve_stage_settings(self, stage: LLMStage) -> tuple[str, str, str]:
        provider = 'zhipu'
        if stage == 'preprocess':
            provider = (self.config.llm_preprocess_provider or 'zhipu').lower()
            model = self.config.llm_preprocess_model or 'glm-4-flash-250414'
            api_key = self.config.zhipu_preprocess_api_key or self.config.zhipu_api_key
        elif stage == 'repair':
            provider = (self.config.llm_repair_provider or 'zhipu').lower()
            model = self.config.llm_repair_model or 'glm-4-flash-250414'
            api_key = self.config.zhipu_repair_api_key or self.config.zhipu_api_key
        else:
            provider = (self.config.llm_final_provider or self.config.llm_provider or 'zhipu').lower()
            model = self.config.llm_final_model or self.config.zhipu_model or 'glm-4.7-flash'
            api_key = self.config.zhipu_final_api_key or self.config.zhipu_api_key

        if self.config.llm_pipeline_mode == 'single':
            provider = (self.config.llm_provider or 'zhipu').lower()
            model = self.config.zhipu_model or self.config.llm_final_model or model
            api_key = self.config.zhipu_api_key or api_key

        if provider != 'zhipu':
            raise NotImplementedError(f"LLM provider '{provider}' is not implemented yet.")
        if not (api_key or '').strip():
            raise RuntimeError(
                f"No available Zhipu API key for stage '{stage}'. "
                "Please set stage-specific key or ZHIPU_API_KEY."
            )

        return provider, model, api_key

    def stage_info(self, stage: LLMStage) -> dict[str, str]:
        provider, model, _api_key = self._resolve_stage_settings(stage)
        return {'stage': stage, 'provider': provider, 'model': model}

    def _is_transient_error(self, message: str) -> bool:
        msg = (message or '').lower()
        tokens = [
            '访问量过大',
            '请稍后再试',
            'rate limit',
            '429',
            'server busy',
            'temporarily unavailable',
            'timeout',
            'connection reset',
            'provider overloaded',
            '5xx',
            '503',
            '502',
            '504',
        ]
        return any(t in msg for t in tokens)

    def _call_once(self, client: OpenAI, model_name: str, system_prompt: str, user_prompt: str, stage: LLMStage) -> str:
        resp = client.chat.completions.create(
            model=model_name,
            temperature=0.2,
            max_tokens=DEFAULT_ZHIPU_MAX_TOKENS,
            extra_body={'thinking': {'type': 'disabled'}},
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        )

        choices = getattr(resp, 'choices', None)
        has_choices = bool(choices)
        first_choice = choices[0] if has_choices else None
        finish_reason = getattr(first_choice, 'finish_reason', None) if first_choice else None
        message = getattr(first_choice, 'message', None) if first_choice else None
        usage = getattr(resp, 'usage', None)
        content = getattr(message, 'content', None) if message is not None else None

        print(f"LLM [{stage}] response debug: provider=zhipu, model={model_name}, has_choices={has_choices}, finish_reason={finish_reason}")
        if usage is not None:
            print(f"LLM [{stage}] usage: {self._to_serializable(usage)}")

        if not content or not str(content).strip():
            debug_path = self._save_empty_response_debug(resp)
            raise RuntimeError(f'LLM API returned empty response content. Debug response saved to: {debug_path}')

        return str(content)

    def chat_json(self, system_prompt: str, user_prompt: str, stage: LLMStage = 'final') -> str:
        provider, model_name, api_key = self._resolve_stage_settings(stage)
        client = OpenAI(
            api_key=api_key,
            base_url=self.config.zhipu_base_url,
            timeout=120,
        )
        max_attempts = self.config.llm_final_max_retries if stage == 'final' else 3
        max_attempts = max(1, int(max_attempts))
        last_exc: Exception | None = None

        self.last_final_model_used = None
        self.last_final_fallback_used = False
        self.last_final_fallback_reason = ''

        for attempt in range(1, max_attempts + 1):
            try:
                output = self._call_once(client, model_name, system_prompt, user_prompt, stage)
                if stage == 'final':
                    self.last_final_model_used = model_name
                return output
            except (APITimeoutError, RateLimitError, TimeoutError, ConnectionError, OSError) as exc:
                last_exc = exc
                if attempt < max_attempts:
                    print(f'LLM [{stage}] call failed, retrying...')
                    time.sleep(min(2 * attempt, 5))
                    continue
                break
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                if attempt < max_attempts and self._is_transient_error(msg):
                    print(f'LLM [{stage}] call failed, retrying...')
                    time.sleep(min(2 * attempt, 5))
                    continue
                break

        # Final-stage fallback model.
        if (
            stage == 'final'
            and self.config.llm_final_fallback_enabled
            and self.config.llm_pipeline_mode in {'single', 'layered'}
            and self._is_transient_error(str(last_exc or ''))
        ):
            fallback_model = (self.config.llm_final_fallback_model or 'glm-4-flash-250414').strip()
            print(f'LLM [final] final model failed after {max_attempts} attempts')
            print(f'LLM [final] fallback model = {fallback_model}')
            try:
                fallback_output = self._call_once(client, fallback_model, system_prompt, user_prompt, stage)
                self.last_final_model_used = fallback_model
                self.last_final_fallback_used = True
                self.last_final_fallback_reason = str(last_exc or '')
                return fallback_output
            except Exception as fallback_exc:
                raise RuntimeError(f'LLM API call failed at stage {stage} (fallback failed): {fallback_exc}') from fallback_exc

        raise RuntimeError(f'LLM API call failed at stage {stage}: {last_exc}') from last_exc
