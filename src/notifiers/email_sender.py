from __future__ import annotations

from datetime import date
from email.message import EmailMessage
from pathlib import Path
import smtplib

from src.config import AppConfig, load_app_config


class EmailSender:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_app_config()

    def _is_placeholder(self, value: str, markers: tuple[str, ...]) -> bool:
        normalized = (value or "").strip().lower()
        if not normalized:
            return True
        return any(marker in normalized for marker in markers)

    def _validate_settings(self) -> list[str]:
        errors: list[str] = []

        if self._is_placeholder(self.config.sender_email, ("your_email", "example", "placeholder")):
            errors.append("SENDER_EMAIL is missing or placeholder.")
        if self._is_placeholder(self.config.smtp_auth_code, ("your_smtp_authorization_code", "placeholder")):
            errors.append("SMTP_AUTH_CODE is missing or placeholder.")
        if self._is_placeholder(self.config.recipient_email, ("your_receive_email", "placeholder")):
            errors.append("RECIPIENT_EMAIL is missing or placeholder.")
        if not (self.config.smtp_host or "").strip():
            errors.append("SMTP_HOST is missing.")

        return errors

    def _parse_recipients(self) -> list[str]:
        raw = self.config.recipient_email or ""
        recipients = [item.strip() for item in raw.split(",") if item.strip()]
        return recipients

    def send_digest_email(
        self,
        html_path: str | Path,
        markdown_path: str | Path,
        subject: str | None = None,
    ) -> None:
        errors = self._validate_settings()
        if errors:
            raise ValueError("Invalid SMTP config: " + " ".join(errors))

        html_file = Path(html_path)
        md_file = Path(markdown_path)
        if not html_file.exists() or not md_file.exists():
            raise FileNotFoundError("Report files are missing. Please run: python tests/manual_test_report.py")

        recipients = self._parse_recipients()
        if not recipients:
            raise ValueError("No valid RECIPIENT_EMAIL found.")

        digest_date = date.today().isoformat()
        mail_subject = subject or f"AI News Digest - {digest_date}"

        msg = EmailMessage()
        msg["From"] = self.config.sender_email
        msg["To"] = ", ".join(recipients)
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
