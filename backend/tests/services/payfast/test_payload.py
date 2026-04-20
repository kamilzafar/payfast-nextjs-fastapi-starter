"""Tests for build_checkout_payload().

Written FIRST (TDD Red phase) before implementation exists.
Uses in-memory SQLAlchemy model instances — no DB connection required.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from app.services.payfast.payload import build_checkout_payload
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures — build in-memory model instances, no session needed
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_basket_id() -> uuid.UUID:
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture()
def sample_invoice(sample_basket_id: uuid.UUID) -> Invoice:
    inv = Invoice()
    inv.id = 42
    inv.subscription_id = 7
    inv.basket_id = sample_basket_id
    inv.amount = 150000  # paisa (minor units)
    inv.status = InvoiceStatus.open
    inv.due_at = None
    inv.paid_at = None
    inv.payfast_txn_id = None
    return inv


@pytest.fixture()
def sample_user() -> User:
    user = User()
    user.id = 1
    user.email = "customer@example.com"
    user.hashed_password = "hashed"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    user.name = "Test Customer"
    user.phone = "03001234567"
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_checkout_payload_amount_conversion(
    sample_invoice: Invoice, sample_user: User
) -> None:
    """150000 paisa must be converted to '1500.00' PKR for TXNAMT."""
    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="tok_abc",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MID123",
    )

    assert payload["TXNAMT"] == "1500.00"


def test_build_checkout_payload_includes_all_required_keys(
    sample_invoice: Invoice, sample_user: User
) -> None:
    """Payload must contain all documented keys PayFast expects."""
    required_keys = {
        "MERCHANT_ID",
        "TOKEN",
        "TXNAMT",
        "BASKET_ID",
        "ORDER_DATE",
        "CURRENCY_CODE",
        "SUCCESS_URL",
        "FAILURE_URL",
    }

    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="tok_abc",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MID123",
    )

    missing = required_keys - set(payload.keys())
    assert not missing, f"Missing keys in payload: {missing}"


def test_build_checkout_payload_uses_user_email_and_mobile(
    sample_invoice: Invoice, sample_user: User
) -> None:
    """Customer email and phone must be populated from the User model."""
    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="tok_abc",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MID123",
    )

    assert payload["CUSTOMER_EMAIL_ADDRESS"] == "customer@example.com"
    assert payload["CUSTOMER_MOBILE_NO"] == "03001234567"


def test_build_checkout_payload_basket_id_from_invoice(
    sample_invoice: Invoice, sample_user: User, sample_basket_id: uuid.UUID
) -> None:
    """BASKET_ID in payload must match invoice.basket_id (as string)."""
    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="tok_abc",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MID123",
    )

    assert payload["BASKET_ID"] == str(sample_basket_id)


def test_build_checkout_payload_token_and_merchant_id(
    sample_invoice: Invoice, sample_user: User
) -> None:
    """TOKEN and MERCHANT_ID must be set from the arguments."""
    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="my_token_value",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MIDXYZ",
    )

    assert payload["TOKEN"] == "my_token_value"
    assert payload["MERCHANT_ID"] == "MIDXYZ"


def test_build_checkout_payload_urls_present(
    sample_invoice: Invoice, sample_user: User
) -> None:
    """SUCCESS_URL and FAILURE_URL must be set from return_url and cancel_url."""
    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="tok",
        return_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        merchant_id="MID",
    )

    assert payload["SUCCESS_URL"] == "https://example.com/success"
    assert payload["FAILURE_URL"] == "https://example.com/cancel"


def test_build_checkout_payload_currency_code_pkr(
    sample_invoice: Invoice, sample_user: User
) -> None:
    """CURRENCY_CODE must default to PKR."""
    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="tok",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MID",
    )

    assert payload["CURRENCY_CODE"] == "PKR"


def test_build_checkout_payload_all_values_are_strings(
    sample_invoice: Invoice, sample_user: User
) -> None:
    """All dict values must be strings (form-encoding requirement)."""
    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=sample_user,
        token="tok",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MID",
    )

    non_strings = {k: v for k, v in payload.items() if not isinstance(v, str)}
    assert not non_strings, f"Non-string values found: {non_strings}"


def test_build_checkout_payload_user_with_no_phone(
    sample_invoice: Invoice,
) -> None:
    """A user without a phone number should produce an empty string for mobile."""
    user = User()
    user.id = 2
    user.email = "nophone@example.com"
    user.hashed_password = "hashed"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    user.name = "No Phone"
    user.phone = None

    payload = build_checkout_payload(
        invoice=sample_invoice,
        user=user,
        token="tok",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        merchant_id="MID",
    )

    assert payload["CUSTOMER_MOBILE_NO"] == ""
