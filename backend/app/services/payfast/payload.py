"""Build the PayFast hosted-checkout POST payload.

The returned dict is used to render a self-submitting HTML form that
redirects the user to PayFast's hosted checkout page.

TODO: Verify all field names against live PayFast UAT documentation.
      POST_TRANSACTION_PATH and field names are based on best-known
      integration guides — update when UAT credentials land.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.invoice import Invoice
from app.models.user import User


def _minor_to_major(amount_minor: int) -> str:
    """Convert paisa (minor units) to PKR string with 2 decimal places.

    Example: 150000 → "1500.00"
    """
    major = amount_minor / 100
    return f"{major:.2f}"


def build_checkout_payload(
    *,
    invoice: Invoice,
    user: User,
    token: str,
    return_url: str,
    cancel_url: str,
    merchant_id: str,
) -> dict[str, str]:
    """Build the POST payload dict for PayFast's hosted checkout redirect.

    Converts invoice.amount (integer paisa) to TXNAMT (PKR major units, 2dp).

    Keys included (best-known from PayFast integration docs):
      MERCHANT_ID             — merchant identifier
      TOKEN                   — one-time access token from get_access_token()
      TXNAMT                  — transaction amount in PKR (major units)
      BASKET_ID               — merchant-side reference (invoice.basket_id)
      ORDER_DATE              — ISO 8601 UTC timestamp
      CURRENCY_CODE           — ISO currency (PKR)
      CUSTOMER_EMAIL_ADDRESS  — user.email
      CUSTOMER_MOBILE_NO      — user.phone (empty string if None)
      SUCCESS_URL             — return_url (on successful payment)
      FAILURE_URL             — cancel_url (on failure / cancellation)
      SIGNATURE               — left blank per PayFast docs (TOKEN authenticates)
      PROCCODE                — processing code (TODO: confirm value with PayFast)
      TXNDESC                 — transaction description
      CHECKOUT_URL            — TODO: confirm if needed by PayFast

    TODO: Confirm exact field list and values against live PayFast UAT.
    TODO: Confirm whether CHECKOUT_URL, PROCCODE are required or optional.
    TODO: Confirm SIGNATURE handling — some integrations compute it; others leave blank.
    """
    order_date = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")

    return {
        "MERCHANT_ID": merchant_id,
        "TOKEN": token,
        "TXNAMT": _minor_to_major(invoice.amount),
        "BASKET_ID": str(invoice.basket_id),
        "ORDER_DATE": order_date,
        "CURRENCY_CODE": "PKR",
        "CUSTOMER_EMAIL_ADDRESS": user.email,
        "CUSTOMER_MOBILE_NO": user.phone or "",
        "SUCCESS_URL": return_url,
        "FAILURE_URL": cancel_url,
        # TODO: Determine correct PROCCODE for standard purchases (e.g. "00")
        "PROCCODE": "00",
        # TODO: Confirm whether TXNDESC content is prescribed by PayFast
        "TXNDESC": f"Invoice {invoice.id}",
        # TODO: Confirm whether SIGNATURE must be computed or left blank
        "SIGNATURE": "",
        # TODO: Confirm whether CHECKOUT_URL is required and what it should contain
        "CHECKOUT_URL": return_url,
    }
