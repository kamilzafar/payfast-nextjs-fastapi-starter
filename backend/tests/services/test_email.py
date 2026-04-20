"""Tests for app.services.email — TDD: written BEFORE implementation (RED first).

Tests use mock SMTP and in-memory template rendering; no real network calls.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# test_smtp_sender_renders_template_and_sends
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smtp_sender_renders_template_and_sends(tmp_path: Path) -> None:
    """SmtpEmailSender renders a Jinja2 template and passes the message
    to aiosmtplib.SMTP.  Uses a mock SMTP client so no real connection is made.
    """
    # Create a minimal temp template so Jinja2 can render it.
    email_dir = tmp_path / "email"
    email_dir.mkdir()
    (email_dir / "receipt.html").write_text(
        "<p>Payment received: {{ invoice.amount }}. Invoice #{{ invoice.id }}.</p>"
    )
    (email_dir / "receipt.txt").write_text(
        "Payment received: {{ invoice.amount }}. Invoice #{{ invoice.id }}."
    )

    from app.services.email import SmtpEmailSender  # noqa: PLC0415

    sender = SmtpEmailSender(
        host="localhost",
        port=1025,
        from_addr="billing@test.local",
        template_dir=str(email_dir),
    )

    invoice_ctx = MagicMock()
    invoice_ctx.amount = "150000"
    invoice_ctx.id = "42"

    mock_smtp = AsyncMock()
    mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
    mock_smtp.__aexit__ = AsyncMock(return_value=False)
    mock_smtp.send_message = AsyncMock()

    with patch("app.services.email.aiosmtplib.SMTP", return_value=mock_smtp):
        await sender.send(
            to="user@example.com",
            subject="Your receipt",
            template_name="receipt",
            context={"invoice": invoice_ctx},
        )

    mock_smtp.send_message.assert_awaited_once()
    sent_msg = mock_smtp.send_message.call_args[0][0]
    # Verify multipart — has both HTML and text payloads
    payloads = [p.get_payload(decode=True).decode() for p in sent_msg.walk()
                if p.get_content_maintype() != "multipart"]
    html_found = any("150000" in p for p in payloads)
    txt_found = any("150000" in p for p in payloads)
    assert html_found, "HTML payload should contain rendered amount"
    assert txt_found, "Text payload should contain rendered amount"


@pytest.mark.asyncio
async def test_smtp_sender_sets_correct_headers(tmp_path: Path) -> None:
    """SmtpEmailSender sets From, To, and Subject headers on the outgoing message."""
    email_dir = tmp_path / "email"
    email_dir.mkdir()
    (email_dir / "welcome.html").write_text("<p>Welcome {{ user.name }}</p>")
    (email_dir / "welcome.txt").write_text("Welcome {{ user.name }}")

    from app.services.email import SmtpEmailSender  # noqa: PLC0415

    sender = SmtpEmailSender(
        host="localhost",
        port=1025,
        from_addr="billing@test.local",
        template_dir=str(email_dir),
    )

    user_ctx = MagicMock()
    user_ctx.name = "Alice"

    mock_smtp = AsyncMock()
    mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
    mock_smtp.__aexit__ = AsyncMock(return_value=False)
    mock_smtp.send_message = AsyncMock()

    with patch("app.services.email.aiosmtplib.SMTP", return_value=mock_smtp):
        await sender.send(
            to="alice@example.com",
            subject="Welcome!",
            template_name="welcome",
            context={"user": user_ctx},
        )

    sent_msg = mock_smtp.send_message.call_args[0][0]
    assert sent_msg["To"] == "alice@example.com"
    assert sent_msg["From"] == "billing@test.local"
    assert sent_msg["Subject"] == "Welcome!"


# ---------------------------------------------------------------------------
# test_template_missing_raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_template_missing_raises(tmp_path: Path) -> None:
    """SmtpEmailSender raises TemplateNotFound when the named template
    does not exist on disk — prevents silently swallowed rendering errors.
    """
    empty_dir = tmp_path / "email_empty"
    empty_dir.mkdir()

    from app.services.email import SmtpEmailSender  # noqa: PLC0415
    from jinja2 import TemplateNotFound  # noqa: PLC0415

    sender = SmtpEmailSender(
        host="localhost",
        port=1025,
        from_addr="billing@test.local",
        template_dir=str(empty_dir),
    )

    mock_smtp = AsyncMock()
    mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
    mock_smtp.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.email.aiosmtplib.SMTP", return_value=mock_smtp):
        with pytest.raises(TemplateNotFound):
            await sender.send(
                to="user@example.com",
                subject="Test",
                template_name="nonexistent",
                context={},
            )


# ---------------------------------------------------------------------------
# test_get_email_sender_factory
# ---------------------------------------------------------------------------

def test_get_email_sender_returns_smtp_for_smtp_backend() -> None:
    """get_email_sender returns SmtpEmailSender when EMAIL_BACKEND=smtp."""
    from app.services.email import get_email_sender, SmtpEmailSender  # noqa: PLC0415

    mock_settings = MagicMock()
    mock_settings.EMAIL_BACKEND = "smtp"
    mock_settings.SMTP_HOST = "localhost"
    mock_settings.SMTP_PORT = 1025
    mock_settings.EMAIL_FROM = "billing@test.local"

    sender = get_email_sender(mock_settings)
    assert isinstance(sender, SmtpEmailSender)


def test_get_email_sender_returns_resend_for_resend_backend() -> None:
    """get_email_sender returns ResendEmailSender when EMAIL_BACKEND=resend."""
    from app.services.email import get_email_sender, ResendEmailSender  # noqa: PLC0415

    mock_settings = MagicMock()
    mock_settings.EMAIL_BACKEND = "resend"
    mock_settings.RESEND_API_KEY = "re_test_key"
    mock_settings.EMAIL_FROM = "billing@prod.com"

    sender = get_email_sender(mock_settings)
    assert isinstance(sender, ResendEmailSender)


# ---------------------------------------------------------------------------
# test_resend_sender_stub
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resend_sender_raises_without_api_key(tmp_path: Path) -> None:
    """ResendEmailSender.send raises ValueError when RESEND_API_KEY is empty."""
    email_dir = tmp_path / "email"
    email_dir.mkdir()
    (email_dir / "receipt.html").write_text("<p>Test</p>")
    (email_dir / "receipt.txt").write_text("Test")

    from app.services.email import ResendEmailSender  # noqa: PLC0415

    sender = ResendEmailSender(api_key="", from_addr="billing@prod.com", template_dir=str(email_dir))
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        await sender.send(
            to="user@example.com",
            subject="Test",
            template_name="receipt",
            context={},
        )
