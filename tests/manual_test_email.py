from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.notifiers.email_sender import EmailSender


def _find_latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def main() -> None:
    html_path = _find_latest(PROJECT_ROOT / "outputs" / "html", "*-ai-news-digest.html")
    md_path = _find_latest(PROJECT_ROOT / "outputs" / "markdown", "*-ai-news-digest.md")

    if html_path is None or md_path is None:
        print("Report files not found. Please run: python tests/manual_test_report.py")
        return

    sender = EmailSender()
    cfg = sender.config

    print(f"smtp host: {cfg.smtp_host}")
    print(f"sender email: {cfg.sender_email}")
    print(f"recipient email: {cfg.recipient_email}")
    print(f"html path: {html_path}")
    print(f"markdown path: {md_path}")

    result = sender.send_digest_email(html_path=html_path, markdown_path=md_path)
    if result.get("success"):
        print(f"email result: success={result.get('success')} recipients={result.get('recipients')} dry_run={result.get('dry_run')}")
        print("Module 6 email test completed.")
        return

    print(f"Email config/send not ready: {result.get('error')}")


if __name__ == "__main__":
    main()
