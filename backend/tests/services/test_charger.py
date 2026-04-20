"""Tests for app.services.charger — TDD: written BEFORE implementation (RED first).

Charger tests use mocked email_sender so no real SMTP is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_invoice(id: int = 1, amount: int = 150000) -> MagicMock:
    inv = MagicMock()
    inv.id = id
    inv.amount = amount
    inv.basket_id = "aaaaaaaa-0000-0000-0000-000000000001"
    return inv


def _make_user(email: str = "user@example.com", name: str = "Test User") -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.email = email
    u.name = name
    return u


def _make_plan(name: str = "Pro Monthly", amount_minor: int = 150000) -> MagicMock:
    p = MagicMock()
    p.id = 1
    p.name = name
    p.amount_minor = amount_minor
    return p


# ---------------------------------------------------------------------------
# test_hosted_redirect_charger_sends_email_and_returns_requires_user_action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hosted_redirect_charger_sends_email_and_returns_requires_user_action() -> None:
    """HostedRedirectCharger.charge sends a payment-link email and returns
    ChargeResult(attempted=True, succeeded=False, requires_user_action=True).
    """
    from app.services.charger import HostedRedirectCharger, ChargeResult  # noqa: PLC0415

    mock_email_sender = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.FRONTEND_URL = "http://localhost:3000"

    charger = HostedRedirectCharger(
        email_sender=mock_email_sender,
        template_name="payment_due",
        settings=mock_settings,
    )

    db = AsyncMock()
    invoice = _make_invoice(id=99)
    user = _make_user()
    plan = _make_plan()

    result = await charger.charge(db, invoice, user, plan)

    assert isinstance(result, ChargeResult)
    assert result.attempted is True
    assert result.succeeded is False
    assert result.requires_user_action is True

    mock_email_sender.send.assert_awaited_once()
    call_kwargs = mock_email_sender.send.call_args
    assert call_kwargs.kwargs["to"] == user.email or call_kwargs.args[0] == user.email


@pytest.mark.asyncio
async def test_hosted_redirect_charger_constructs_pay_url() -> None:
    """HostedRedirectCharger builds pay_url = FRONTEND_URL + /checkout/{invoice.id}
    and passes it in the email context.
    """
    from app.services.charger import HostedRedirectCharger  # noqa: PLC0415

    mock_email_sender = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.FRONTEND_URL = "http://localhost:3000"

    charger = HostedRedirectCharger(
        email_sender=mock_email_sender,
        template_name="upcoming_renewal",
        settings=mock_settings,
    )

    db = AsyncMock()
    invoice = _make_invoice(id=42)
    user = _make_user()
    plan = _make_plan()

    await charger.charge(db, invoice, user, plan)

    call_kwargs = mock_email_sender.send.call_args
    # Accept both positional and keyword call styles
    context = call_kwargs.kwargs.get("context") or call_kwargs.args[3]
    assert "pay_url" in context
    assert "42" in context["pay_url"]
    assert "http://localhost:3000" in context["pay_url"]


# ---------------------------------------------------------------------------
# test_token_charger_raises_not_implemented
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_charger_raises_not_implemented() -> None:
    """TokenCharger.charge raises NotImplementedError — placeholder for MIT API."""
    from app.services.charger import TokenCharger  # noqa: PLC0415

    charger = TokenCharger()
    db = AsyncMock()
    invoice = _make_invoice()
    user = _make_user()
    plan = _make_plan()

    with pytest.raises(NotImplementedError):
        await charger.charge(db, invoice, user, plan)


# ---------------------------------------------------------------------------
# test_charge_result_dataclass
# ---------------------------------------------------------------------------

def test_charge_result_fields() -> None:
    """ChargeResult is a dataclass-like object with expected fields."""
    from app.services.charger import ChargeResult  # noqa: PLC0415

    r = ChargeResult(attempted=True, succeeded=True, requires_user_action=False)
    assert r.attempted is True
    assert r.succeeded is True
    assert r.requires_user_action is False
