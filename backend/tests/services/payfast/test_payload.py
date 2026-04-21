"""Tests for build_checkout_payload().

Field names and values confirmed from PayFast's payment.php sample
(Merchant Integration Guide 2.3, Apr 2026).

Uses in-memory SQLAlchemy model instances — no DB connection required.
"""

from __future__ import annotations

import os
import re
import uuid

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from app.services.payfast.payload import build_checkout_payload
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User


RETURN_URL = "https://example.com/return"
CANCEL_URL = "https://example.com/cancel"
CHECKOUT_URL = "https://example.com/webhooks/payfast"


@pytest.fixture()
def sample_basket_id() -> uuid.UUID:
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture()
def sample_invoice(sample_basket_id: uuid.UUID) -> Invoice:
    inv = Invoice()
    inv.id = 42
    inv.subscription_id = 7
    inv.basket_id = sample_basket_id
    inv.amount = 150000  # 1500.00 PKR in paisa
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


def _call(invoice: Invoice, user: User, **overrides):
    kwargs = dict(
        invoice=invoice,
        user=user,
        token="tok_abc",
        return_url=RETURN_URL,
        cancel_url=CANCEL_URL,
        checkout_url=CHECKOUT_URL,
        merchant_id="MID123",
    )
    kwargs.update(overrides)
    return build_checkout_payload(**kwargs)


def test_amount_conversion(sample_invoice, sample_user):
    """150000 paisa -> '1500.00' PKR."""
    payload = _call(sample_invoice, sample_user)
    assert payload["TXNAMT"] == "1500.00"


def test_includes_all_payment_php_keys(sample_invoice, sample_user):
    """Every field from PayFast's payment.php sample must be present."""
    required_keys = {
        "CURRENCY_CODE",
        "MERCHANT_ID",
        "MERCHANT_NAME",
        "TOKEN",
        "BASKET_ID",
        "TXNAMT",
        "ORDER_DATE",
        "SUCCESS_URL",
        "FAILURE_URL",
        "CHECKOUT_URL",
        "CUSTOMER_EMAIL_ADDRESS",
        "CUSTOMER_MOBILE_NO",
        "SIGNATURE",
        "VERSION",
        "TXNDESC",
        "PROCCODE",
        "TRAN_TYPE",
        "STORE_ID",
        "RECURRING_TXN",
    }
    payload = _call(sample_invoice, sample_user)
    missing = required_keys - set(payload.keys())
    assert not missing, f"Missing keys: {missing}"


def test_customer_fields_from_user(sample_invoice, sample_user):
    payload = _call(sample_invoice, sample_user)
    assert payload["CUSTOMER_EMAIL_ADDRESS"] == "customer@example.com"
    assert payload["CUSTOMER_MOBILE_NO"] == "03001234567"


def test_basket_id_from_invoice(sample_invoice, sample_user, sample_basket_id):
    payload = _call(sample_invoice, sample_user)
    assert payload["BASKET_ID"] == str(sample_basket_id)


def test_token_and_merchant_id(sample_invoice, sample_user):
    payload = _call(
        sample_invoice,
        sample_user,
        token="my_token_value",
        merchant_id="MIDXYZ",
    )
    assert payload["TOKEN"] == "my_token_value"
    assert payload["MERCHANT_ID"] == "MIDXYZ"


def test_urls_present(sample_invoice, sample_user):
    payload = _call(sample_invoice, sample_user)
    assert payload["SUCCESS_URL"] == RETURN_URL
    assert payload["FAILURE_URL"] == CANCEL_URL
    assert payload["CHECKOUT_URL"] == CHECKOUT_URL


def test_currency_code_pkr(sample_invoice, sample_user):
    payload = _call(sample_invoice, sample_user)
    assert payload["CURRENCY_CODE"] == "PKR"


def test_version_proccode_tran_type(sample_invoice, sample_user):
    """VERSION, PROCCODE and TRAN_TYPE match PayFast's payment.php sample."""
    payload = _call(sample_invoice, sample_user)
    assert payload["VERSION"] == "MERCHANTCART-0.1"
    assert payload["PROCCODE"] == "00"
    assert payload["TRAN_TYPE"] == "ECOMM_PURCHASE"


def test_order_date_format(sample_invoice, sample_user):
    """ORDER_DATE is 'YYYY-MM-DD HH:MM:SS' per payment.php (date('Y-m-d H:i:s'))."""
    payload = _call(sample_invoice, sample_user)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", payload["ORDER_DATE"])


def test_signature_is_correlation_tag(sample_invoice, sample_user, sample_basket_id):
    """SIGNATURE = '<12-hex>-<basket_id>'."""
    payload = _call(sample_invoice, sample_user)
    sig = payload["SIGNATURE"]
    expected_suffix = f"-{sample_basket_id}"
    assert sig.endswith(expected_suffix)
    prefix = sig[: -len(expected_suffix)]
    assert len(prefix) == 12
    assert all(c in "0123456789abcdef" for c in prefix)


def test_recurring_txn_defaults_empty(sample_invoice, sample_user):
    payload = _call(sample_invoice, sample_user)
    assert payload["RECURRING_TXN"] == ""


def test_recurring_txn_true_when_requested(sample_invoice, sample_user):
    payload = _call(sample_invoice, sample_user, create_recurring_token=True)
    assert payload["RECURRING_TXN"] == "TRUE"


def test_all_values_are_strings(sample_invoice, sample_user):
    """Form-encoding requires string values."""
    payload = _call(sample_invoice, sample_user)
    non_strings = {k: v for k, v in payload.items() if not isinstance(v, str)}
    assert not non_strings, f"Non-string values: {non_strings}"


def test_user_with_no_phone_gives_empty_mobile(sample_invoice):
    user = User()
    user.id = 2
    user.email = "nophone@example.com"
    user.hashed_password = "hashed"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    user.name = "No Phone"
    user.phone = None

    payload = _call(sample_invoice, user)
    assert payload["CUSTOMER_MOBILE_NO"] == ""


def test_merchant_name_override(sample_invoice, sample_user):
    payload = _call(sample_invoice, sample_user, merchant_name="Acme Co")
    assert payload["MERCHANT_NAME"] == "Acme Co"
