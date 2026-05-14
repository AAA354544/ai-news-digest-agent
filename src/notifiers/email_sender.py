from __future__ import annotations

from datetime import date
from email.message import EmailMessage
from pathlib import Path
import smtplib

from src.config import AppConfig, load_app_config
from src.notifiers.recipients import normalize_email, parse_email_list, validate_email


class EmailSender:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_app_config()

    def _is_placeholder(self, value: str, markers: tuple[str, ...]) -> bool:
        normalized = (value or "").strip().lower()
        if not normalized:
            return True
        return any(marker in normalized for marker in markers)

    def _validate_settings(self, require_default_recipient: bool = True) -> list[str]:
        errors: list[str] = []

        if self._is_placeholder(self.config.sender_email, ("your_email", "example", "placeholder")):
            errors.append("SENDER_EMAIL is missing or placeholder.")
        if self._is_placeholder(self.config.smtp_auth_code, ("your_smtp_authorization_code", "placeholder")):
            errors.append("SMTP_AUTH_CODE is missing or placeholder.")
        if require_default_recipient and self._is_placeholder(self.config.recipient_email, ("your_receive_email", "placeholder")):
            errors.append("RECIPIENT_EMAIL is missing or placeholder.")
        if not (self.config.smtp_host or "").strip():
            errors.append("SMTP_HOST is missing.")

        return errors

    def _resolve_recipients(self, recipients: list[str] | None = None) -> list[str]:
        values = recipients if recipients is not None else parse_email_list(self.config.recipient_email or "")
        deduped: list[str] = []
        seen: set[str] = set()
        for raw in values:
            email = normalize_email(raw)
            if not email or email in seen:
                continue
            if not validate_email(email):
                raise ValueError(f"Invalid recipient email format: '{raw}'.")
            seen.add(email)
            deduped.append(email)
        return deduped

    def send_digest_email(
        self,
        html_path: str | Path,
        markdown_path: str | Path,
        recipients: list[str] | None = None,
        subject: str | None = None,
    ) -> dict[str, object]:
        errors = self._validate_settings(require_default_recipient=recipients is None)
        if errors:
            raise ValueError("Invalid SMTP config: " + " ".join(errors))

        html_file = Path(html_path)
        md_file = Path(markdown_path)
        if not html_file.exists() or not md_file.exists():
            raise FileNotFoundError("Report files are missing. Please run: python tests/manual_test_report.py")

        final_recipients = self._resolve_recipients(recipients)
        if not final_recipients:
            raise ValueError("No valid recipients found. Please provide --to/--group or set RECIPIENT_EMAIL.")

        digest_date = date.today().isoformat()
        mail_subject = subject or f"AI News Digest - {digest_date}"

        msg = EmailMessage()
        msg["From"] = self.config.sender_email
        msg["To"] = ", ".join(final_recipients)
        msg["Subject"] = mail_subject

        msg.set_content("This email contains an HTML AI News Digest and a Markdown attachment.")
        msg.add_alternative(html_file.read_text(encoding="utf-8"), subtype="html")

        md_bytes = md_file.read_bytes()
        msg.add_attachment(
            md_bytes,
            maintype="text",
            subtype="markdown",
            filename=md_file.name,
        )

        if self.config.smtp_use_ssl:
            with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=30) as server:
                server.login(self.config.sender_email, self.config.smtp_auth_code)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.config.sender_email, self.config.smtp_auth_code)
                server.send_message(msg)
        return {
            "success": True,
            "recipients": final_recipients,
            "recipient_count": len(final_recipients),
            "subject": mail_subject,
        }
