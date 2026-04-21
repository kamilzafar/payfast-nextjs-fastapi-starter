"""Build the PayFast hosted-checkout POST payload.

Field names and casing confirmed from PayFast's official `payment.php`
sample (Merchant Integration Guide 2.3, Apr 2026).

The returned dict is used to render a self-submitting HTML form that
redirects the user to PayFast's hosted checkout page.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from app.models.invoice import Invoice
from app.models.user import User


MERCHANT_NAME_DEFAULT = "PayFast Subscriptions"
VERSION = "MERCHANTCART-0.1"
TRAN_TYPE = "ECOMM_PURCHASE"
PROCCODE = "00"


def _minor_to_major(amount_minor: int) -> str:
    """Convert paisa (minor units) to PKR string with 2 decimal places.

    Example: 150000 paisa -> "1500.00"
    """
    major = amount_minor / 100
    return f"{major:.2f}"


def _build_signature(basket_id: str) -> str:
    """Build the SIGNATURE field.

    The SIGNATURE field in PayFast's checkout form is a merchant-chosen
    correlation tag — PayFast's sample uses 'SOMERANDOM-STRING'. We generate
    12 hex chars + '-' + basket_id so we can spot our own traffic.
    """
    return f"{secrets.token_hex(6)}-{basket_id}"


def build_checkout_payload(
    *,
    invoice: Invoice,
    user: User,
    token: str,
    return_url: str,
    cancel_url: str,
    checkout_url: str,
    merchant_id: str,
    merchant_name: str = MERCHANT_NAME_DEFAULT,
    create_recurring_token: bool = False,
) -> dict[str, str]:
    """Build the POST payload dict for PayFast's hosted checkout redirect.

    Fields (from payment.php):
      CURRENCY_CODE, MERCHANT_ID, MERCHANT_NAME, TOKEN, BASKET_ID, TXNAMT,
      ORDER_DATE ("YYYY-MM-DD HH:MM:SS" UTC), SUCCESS_URL, FAILURE_URL,
      CHECKOUT_URL (IPN endpoint), CUSTOMER_EMAIL_ADDRESS, CUSTOMER_MOBILE_NO,
      SIGNATURE, VERSION="MERCHANTCART-0.1", TXNDESC, PROCCODE="00",
      TRAN_TYPE="ECOMM_PURCHASE", STORE_ID="", RECURRING_TXN ("TRUE" or "").

    SUCCESS_URL / FAILURE_URL: browser redirect after payment (UX).
    CHECKOUT_URL: IPN callback PayFast POSTs to (server-to-server, auth via
      validation_hash in the body).
    """
    order_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    basket_id = str(invoice.basket_id)

    return {
        "CURRENCY_CODE": "PKR",
        "MERCHANT_ID": merchant_id,
        "MERCHANT_NAME": merchant_name,
        "TOKEN": token,
        "BASKET_ID": basket_id,
        "TXNAMT": _minor_to_major(invoice.amount),
        "ORDER_DATE": order_date,
        "SUCCESS_URL": return_url,
        "FAILURE_URL": cancel_url,
        "CHECKOUT_URL": checkout_url,
        "CUSTOMER_EMAIL_ADDRESS": user.email,
        "CUSTOMER_MOBILE_NO": user.phone or "",
        "SIGNATURE": _build_signature(basket_id),
        "VERSION": VERSION,
        "TXNDESC": f"Invoice {invoice.id}",
        "PROCCODE": PROCCODE,
        "TRAN_TYPE": TRAN_TYPE,
        "STORE_ID": "",
        "RECURRING_TXN": "TRUE" if create_recurring_token else "",
    }
