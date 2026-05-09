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
        if self._is_placeholder(self.config.recipient_email, ("your_receive_email", "placeholder")) and self._is_placeholder(
            self.config.recipient_emails, ("your_receive_email", "placeholder")
        ):
            errors.append("RECIPIENT_EMAIL / RECIPIENT_EMAILS is missing or placeholder.")
        if not (self.config.smtp_host or "").strip():
            errors.append("SMTP_HOST is missing.")

        return errors

    def _parse_recipients(self) -> list[str]:
        raw_values = [self.config.recipient_email or "", self.config.recipient_emails or ""]
        recipients: list[str] = []
        for raw in raw_values:
            recipients.extend([item.strip() for item in raw.split(",") if item.strip()])

        deduped: list[str] = []
        seen: set[str] = set()
        for r in recipients:
            lowered = r.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(r)

        max_allowed = max(1, int(self.config.max_recipients_per_run or 5))
        return deduped[:max_allowed]

    def _mask_email(self, email: str) -> str:
        v = (email or "").strip()
        if "@" not in v:
            return "***"
        name, domain = v.split("@", 1)
        if len(name) <= 2:
            return f"{name[:1]}*@{domain}"
        return f"{name[:2]}***@{domain}"

    def send_digest_email(
        self,
        html_path: str | Path,
        markdown_path: str | Path,
        subject: str | None = None,
    ) -> dict[str, object]:
        errors = self._validate_settings()
        if errors:
            return {
                "success": False,
                "recipients": [],
                "subject": subject or "",
                "error": "Invalid SMTP config: " + " ".join(errors),
            }

        html_file = Path(html_path)
        md_file = Path(markdown_path)
        if not html_file.exists() or not md_file.exists():
            return {
                "success": False,
                "recipients": [],
                "subject": subject or "",
                "error": "Report files are missing. Please run: python tests/manual_test_report.py",
            }

        recipients = self._parse_recipients()
        if not recipients:
            return {
                "success": False,
                "recipients": [],
                "subject": subject or "",
                "error": "No valid RECIPIENT_EMAIL/RECIPIENT_EMAILS found.",
            }

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

        masked = [self._mask_email(r) for r in recipients]
        if self.config.dry_run:
            return {
                "success": True,
                "recipients": masked,
                "subject": mail_subject,
                "error": "",
                "dry_run": True,
            }

        try:
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
                "recipients": masked,
                "subject": mail_subject,
                "error": "",
                "dry_run": False,
            }
        except Exception as exc:
            return {
                "success": False,
                "recipients": masked,
                "subject": mail_subject,
                "error": str(exc),
                "dry_run": False,
            }
