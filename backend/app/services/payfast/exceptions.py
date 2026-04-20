"""PayFast gateway exceptions.

Hierarchy:
  PayFastError           — base for all PayFast-related errors
    PayFastAuthError     — authentication / credential failures (token endpoint)
    PayFastSignatureError — IPN signature verification failure (use in callers)
"""

from __future__ import annotations


class PayFastError(Exception):
    """Base exception for all PayFast gateway errors."""


class PayFastAuthError(PayFastError):
    """Raised when the PayFast token endpoint returns a non-2xx status or
    does not include a TOKEN in the response body."""


class PayFastSignatureError(PayFastError):
    """Raised by callers that want to treat an invalid IPN signature as an
    exception rather than a boolean.  verify_ipn() itself returns bool;
    this exception is available for router/handler use."""
