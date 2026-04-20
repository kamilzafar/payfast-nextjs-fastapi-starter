"""PayFast HTTP client — get_access_token().

Wraps httpx.AsyncClient to fetch a one-time access token from PayFast.

TODO: Verify TOKEN_PATH and all request field names against live PayFast UAT
      documentation once credentials are available.
      Base URL is configurable (pass base_url from settings.PAYFAST_BASE_URL).
"""

from __future__ import annotations

import contextlib
from typing import Any

import httpx

from app.services.payfast.constants import DEFAULT_TIMEOUT, TOKEN_PATH
from app.services.payfast.exceptions import PayFastAuthError, PayFastError
from app.services.payfast.types import AccessToken


def _minor_to_major(amount_minor: int) -> str:
    """Convert a minor-unit integer (paisa) to a 2-decimal major-unit string (PKR).

    Example: 150000 → "1500.00"
    """
    major = amount_minor / 100
    return f"{major:.2f}"


async def get_access_token(
    merchant_id: str,
    secured_key: str,
    amount_minor: int,
    basket_id: str,
    currency: str = "PKR",
    *,
    base_url: str,
    http_client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> AccessToken:
    """POST form-encoded credentials to the PayFast token endpoint.

    Expected request payload (best-known from integration docs):
      MERCHANT_ID   — merchant identifier
      SECURED_KEY   — merchant secret / API key
      TXNAMT        — transaction amount in major units (PKR), 2 decimal places
      BASKET_ID     — merchant-side transaction reference
      CURRENCY_CODE — ISO currency code (default PKR)

    Returns an AccessToken on success.
    Raises PayFastAuthError on non-2xx status or missing TOKEN in response.
    Raises PayFastError on network/timeout errors.

    TODO: Confirm exact field names against live PayFast UAT response.
    """
    url = f"{base_url}{TOKEN_PATH}"
    form_data: dict[str, Any] = {
        "MERCHANT_ID": merchant_id,
        "SECURED_KEY": secured_key,
        "TXNAMT": _minor_to_major(amount_minor),
        "BASKET_ID": basket_id,
        "CURRENCY_CODE": currency,
    }

    _owns_client = http_client is None
    if _owns_client:
        http_client = httpx.AsyncClient(timeout=timeout)

    try:
        response = await http_client.post(url, data=form_data)  # type: ignore[union-attr]
    except httpx.TimeoutException as exc:
        raise PayFastError(f"Request to PayFast token endpoint timed out: {exc}") from exc
    except httpx.HTTPError as exc:
        raise PayFastError(f"HTTP error communicating with PayFast: {exc}") from exc
    finally:
        if _owns_client:
            await http_client.aclose()  # type: ignore[union-attr]

    if not response.is_success:
        raise PayFastAuthError(
            f"PayFast token endpoint returned {response.status_code}: {response.text}"
        )

    try:
        body = response.json()
    except Exception as exc:
        raise PayFastAuthError(
            f"PayFast token response was not valid JSON: {response.text}"
        ) from exc

    # TODO: Confirm exact key name — "TOKEN" is assumed from common PayFast docs.
    token_value: str | None = body.get("TOKEN") or body.get("token")
    if not token_value:
        raise PayFastAuthError(
            f"PayFast response missing TOKEN field. Response body: {body}"
        )

    # TODO: Parse expires_at if PayFast returns an expiry field.
    return AccessToken(token=token_value, expires_at=None)
