"""PayFast IPN signature verification.

TODO: PayFast's exact IPN signature scheme is not cleanly documented
      in public resources.  This implementation uses HMAC-SHA256 with
      the shared webhook secret (settings.PAYFAST_WEBHOOK_SECRET) and
      the X-PayFast-Signature header.

      When live IPN samples are received:
        1. Log the raw headers and body.
        2. Compare against this implementation.
        3. Update IPN_SIGNATURE_HEADER and the HMAC computation here
           if PayFast uses a different algorithm (e.g. MD5, different header).

      This function is the SINGLE place to change IPN verification logic.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping

from app.services.payfast.constants import IPN_SIGNATURE_HEADER


def verify_ipn(
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str,
) -> bool:
    """Verify the authenticity of a PayFast IPN notification.

    Algorithm (current implementation):
      1. Read the IPN_SIGNATURE_HEADER from headers (case-insensitive lookup).
      2. Compute HMAC-SHA256(raw_body, secret.encode('utf-8')).
      3. Compare using hmac.compare_digest() for constant-time equality.

    Returns True if signature matches, False otherwise (including missing header).

    TODO: Verify exact algorithm against live PayFast IPN samples.
          Update IPN_SIGNATURE_HEADER in constants.py if the header name differs.
    """
    # Case-insensitive header lookup (HTTP/1.1 headers are case-insensitive).
    header_lower = IPN_SIGNATURE_HEADER.lower()
    received_signature: str | None = None
    for key, value in headers.items():
        if key.lower() == header_lower:
            received_signature = value
            break

    if received_signature is None:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, received_signature)
