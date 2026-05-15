from __future__ import annotations

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_app_config, validate_runtime_config


def main() -> None:
    tracked_keys = [
        "DIGEST_LOOKBACK_HOURS",
        "MAX_LLM_CANDIDATES",
        "SMTP_USE_SSL",
        "LLM_PROVIDER",
        "ZHIPU_API_KEY",
        "ZHIPU_MODEL",
    ]
    backup = {k: os.environ.get(k) for k in tracked_keys}

    try:
        os.environ["DIGEST_LOOKBACK_HOURS"] = ""
        os.environ["MAX_LLM_CANDIDATES"] = "50"
        os.environ["SMTP_USE_SSL"] = "0"
        os.environ["LLM_PROVIDER"] = "zhipu"
        os.environ["ZHIPU_API_KEY"] = "placeholder_key"
        os.environ["ZHIPU_MODEL"] = "placeholder_model"

        cfg = load_app_config()
        assert cfg.digest_lookback_hours == 24, cfg
        assert cfg.smtp_use_ssl is False, cfg
        print("fallback/bool parsing: ok")

        os.environ["MAX_LLM_CANDIDATES"] = "abc"
        try:
            _ = load_app_config()
            raise AssertionError("Expected ValueError for invalid integer")
        except ValueError:
            print("invalid integer handling: ok")

        os.environ["MAX_LLM_CANDIDATES"] = "50"
        result = validate_runtime_config(mode="local")
        assert isinstance(result, dict), result
        assert "ok" in result and "errors" in result and "warnings" in result, result
        print("validate_runtime_config return shape: ok")
    finally:
        for key, value in backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("manual_test_config_runtime completed.")


if __name__ == "__main__":
    main()
