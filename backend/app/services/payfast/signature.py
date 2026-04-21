"""PayFast IPN validation-hash verification.

Per PayFast's IPN Integration Document (Apr 2026), PayFast authenticates
IPN callbacks with a `validation_hash` field IN the body:

    validation_hash = SHA256(
        f"{basket_id}|{secured_key}|{merchant_id}|{err_code}"
    ).hexdigest()

Example from the docs:
    "BAS-01|jdnkaabcks|102|000"
    -> e8192a7554dd699975adf39619c703a492392edf5e416a61e183866ecdf6a2a2

There is no header-based HMAC. The secured_key that's used for
GetAccessToken is the same key used for IPN validation.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping


def compute_validation_hash(
    basket_id: str,
    secured_key: str,
    merchant_id: str,
    err_code: str,
) -> str:
    """Compute the SHA-256 validation hash PayFast expects.

    Order is fixed by the docs: basket_id | secured_key | merchant_id | err_code.
    """
    raw = f"{basket_id}|{secured_key}|{merchant_id}|{err_code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_ipn(
    payload: Mapping[str, str],
    secured_key: str,
    merchant_id: str,
) -> bool:
    """Verify an IPN payload's `validation_hash` against the expected value.

    Returns True iff all four required fields are present and the received
    `validation_hash` matches the locally-computed SHA-256. Uses constant-time
    comparison.

    Missing or blank basket_id / err_code / validation_hash -> False.
    """
    basket_id = (payload.get("basket_id") or "").strip()
    err_code = (payload.get("err_code") or "").strip()
    received = (payload.get("validation_hash") or "").strip().lower()

    if not basket_id or not err_code or not received:
        return False

    expected = compute_validation_hash(
        basket_id=basket_id,
        secured_key=secured_key,
        merchant_id=merchant_id,
        err_code=err_code,
    )
    return hmac.compare_digest(expected, received)
