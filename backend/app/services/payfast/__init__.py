"""PayFast gateway service package.

Public API:
  get_access_token      — fetch a one-time access token from PayFast
  build_checkout_payload — build the hosted-checkout POST form payload
  verify_ipn            — verify an IPN notification signature
  PayFastError          — base exception
  PayFastAuthError      — token / credential failure
  PayFastSignatureError — IPN signature mismatch (for use in callers)
"""

from __future__ import annotations

from app.services.payfast.client import get_access_token
from app.services.payfast.exceptions import (
    PayFastAuthError,
    PayFastError,
    PayFastSignatureError,
)
from app.services.payfast.payload import build_checkout_payload
from app.services.payfast.signature import verify_ipn

__all__ = [
    "get_access_token",
    "build_checkout_payload",
    "verify_ipn",
    "PayFastError",
    "PayFastAuthError",
    "PayFastSignatureError",
]
