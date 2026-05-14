from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.notifiers.recipients import (
    add_or_update_recipient,
    get_enabled_recipients,
    load_recipients,
    parse_email_list,
    save_recipients,
    validate_email,
)


def main() -> None:
    parsed = parse_email_list("a@example.com, b@example.com;\nc@example.com\r\na@example.com")
    assert parsed == ["a@example.com", "b@example.com", "c@example.com"], parsed
    print("parse_email_list: ok")

    assert validate_email("dev@example.com")
    assert not validate_email("dev.example.com")
    assert not validate_email("dev@localhost")
    print("validate_email: ok")

    recipients: list[dict[str, object]] = []
    recipients = add_or_update_recipient(
        recipients,
        email="dev@example.com",
        name="Dev",
        groups=["default"],
        enabled=True,
        note="first",
    )
    recipients = add_or_update_recipient(
        recipients,
        email="DEV@example.com",
        name="Dev Updated",
        groups=["default", "team"],
        enabled=True,
        note="updated",
    )
    assert len(recipients) == 1, recipients
    assert recipients[0]["name"] == "Dev Updated", recipients
    print("add_or_update_recipient: ok")

    recipients = add_or_update_recipient(
        recipients,
        email="disabled@example.com",
        name="Disabled",
        groups=["team"],
        enabled=False,
        note="disabled test",
    )
    enabled_all = get_enabled_recipients(recipients)
    enabled_default = get_enabled_recipients(recipients, group="default")
    enabled_team = get_enabled_recipients(recipients, group="team")
    assert enabled_all == ["dev@example.com"], enabled_all
    assert enabled_default == ["dev@example.com"], enabled_default
    assert enabled_team == ["dev@example.com"], enabled_team
    print("get_enabled_recipients: ok")

    tmp_path = PROJECT_ROOT / "data" / "_tmp_recipients_test.json"
    saved = save_recipients(recipients, path=tmp_path)
    loaded = load_recipients(path=tmp_path)
    assert saved.exists()
    assert len(loaded) == 2, loaded
    print("save/load_recipients: ok")

    try:
        tmp_path.unlink(missing_ok=True)
    except Exception:
        pass

    print("manual_test_recipients completed.")


if __name__ == "__main__":
    main()
