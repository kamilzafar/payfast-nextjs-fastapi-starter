"""Email sending abstraction for Phase 5.

Backends:
- SmtpEmailSender  — aiosmtplib, targets SMTP_HOST:SMTP_PORT (MailHog dev, no auth/TLS)
- ResendEmailSender — stub for prod; uses resend SDK keyed by RESEND_API_KEY

Factory:
- get_email_sender(settings) -> EmailSender   picks based on EMAIL_BACKEND config

Templates are Jinja2, loaded from app/templates/email/{name}.html and .txt.
Both variants are combined into a multipart/alternative MIME message.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

log = structlog.get_logger(__name__)

# Default template directory — relative to this file's package root.
_DEFAULT_TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates" / "email")


class EmailSender(ABC):
    """Abstract email sender.  All implementations must honour this interface."""

    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        template_name: str,
        context: dict[str, Any],
    ) -> None:
        """Render `template_name` with `context` and send to `to`."""
        ...


class SmtpEmailSender(EmailSender):
    """Send multipart (HTML + plain text) email via aiosmtplib.

    Designed for MailHog in development: no auth, no TLS, localhost:1025.
    """

    def __init__(
        self,
        host: str,
        port: int,
        from_addr: str,
        template_dir: str = _DEFAULT_TEMPLATE_DIR,
    ) -> None:
        self._host = host
        self._port = port
        self._from_addr = from_addr
        self._jinja = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
        )

    def _render(self, template_name: str, ext: str, context: dict[str, Any]) -> str:
        """Render a single template file; raises TemplateNotFound on miss."""
        tpl = self._jinja.get_template(f"{template_name}.{ext}")
        return tpl.render(**context)

    async def send(
        self,
        to: str,
        subject: str,
        template_name: str,
        context: dict[str, Any],
    ) -> None:
        html_body = self._render(template_name, "html", context)
        txt_body = self._render(template_name, "txt", context)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_addr
        msg["To"] = to
        msg.attach(MIMEText(txt_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        async with aiosmtplib.SMTP(hostname=self._host, port=self._port) as smtp:
            await smtp.send_message(msg)

        log.info("email.sent", to=to, subject=subject, template=template_name)


class ResendEmailSender(EmailSender):
    """Send email via the Resend SDK (production backend).

    Requires a valid RESEND_API_KEY.  Raises ValueError on empty key so
    mis-configuration is caught eagerly rather than at send time.
    """

    def __init__(
        self,
        api_key: str,
        from_addr: str,
        template_dir: str = _DEFAULT_TEMPLATE_DIR,
    ) -> None:
        self._api_key = api_key
        self._from_addr = from_addr
        self._jinja = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
        )

    def _render(self, template_name: str, ext: str, context: dict[str, Any]) -> str:
        tpl = self._jinja.get_template(f"{template_name}.{ext}")
        return tpl.render(**context)

    async def send(
        self,
        to: str,
        subject: str,
        template_name: str,
        context: dict[str, Any],
    ) -> None:
        if not self._api_key:
            raise ValueError(
                "RESEND_API_KEY is not set. Configure it before using ResendEmailSender."
            )

        import resend  # noqa: PLC0415 — optional prod dep

        html_body = self._render(template_name, "html", context)
        txt_body = self._render(template_name, "txt", context)

        resend.api_key = self._api_key
        resend.Emails.send(
            {
                "from": self._from_addr,
                "to": [to],
                "subject": subject,
                "html": html_body,
                "text": txt_body,
            }
        )
        log.info("email.sent.resend", to=to, subject=subject, template=template_name)


def get_email_sender(settings: Any) -> EmailSender:
    """Factory — returns the appropriate EmailSender based on EMAIL_BACKEND config."""
    if settings.EMAIL_BACKEND == "resend":
        return ResendEmailSender(
            api_key=settings.RESEND_API_KEY,
            from_addr=settings.EMAIL_FROM,
        )
    # Default: smtp
    return SmtpEmailSender(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        from_addr=settings.EMAIL_FROM,
    )
