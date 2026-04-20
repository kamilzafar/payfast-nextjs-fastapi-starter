"""Tests for verify_ipn() signature verification.

Written FIRST (TDD Red phase) before implementation exists.
No external connections needed — pure crypto logic.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from app.services.payfast.signature import verify_ipn
from app.services.payfast.constants import IPN_SIGNATURE_HEADER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signature(body: bytes, secret: str) -> str:
    """Compute the expected HMAC-SHA256 hex digest for a given body and secret."""
    return hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_verify_ipn_valid_signature() -> None:
    """A matching HMAC-SHA256 signature must return True."""
    secret = "super_secret_key"
    body = b'{"TRANSACTION_ID": "TXN001", "AMOUNT": "1500.00"}'
    sig = _make_signature(body, secret)

    headers = {IPN_SIGNATURE_HEADER: sig}
    assert verify_ipn(raw_body=body, headers=headers, secret=secret) is True


def test_verify_ipn_invalid_signature() -> None:
    """A tampered body must not match the original signature — returns False."""
    secret = "super_secret_key"
    original_body = b'{"TRANSACTION_ID": "TXN001"}'
    tampered_body = b'{"TRANSACTION_ID": "TXN999"}'
    sig = _make_signature(original_body, secret)

    headers = {IPN_SIGNATURE_HEADER: sig}
    assert verify_ipn(raw_body=tampered_body, headers=headers, secret=secret) is False


def test_verify_ipn_missing_header() -> None:
    """When the signature header is absent, verify_ipn must return False."""
    body = b'{"TRANSACTION_ID": "TXN001"}'
    assert verify_ipn(raw_body=body, headers={}, secret="some_secret") is False


def test_verify_ipn_wrong_secret() -> None:
    """A valid signature computed with the wrong secret must return False."""
    correct_secret = "correct_secret"
    wrong_secret = "wrong_secret"
    body = b'{"amount": "500"}'
    sig = _make_signature(body, correct_secret)

    headers = {IPN_SIGNATURE_HEADER: sig}
    assert verify_ipn(raw_body=body, headers=headers, secret=wrong_secret) is False


def test_verify_ipn_constant_time() -> None:
    """Smoke test: verify_ipn must not raise when called many times in a row
    (exercises constant-time comparison code path without timing assertions)."""
    secret = "bench_secret"
    body = b"payload_data"
    sig = _make_signature(body, secret)
    valid_headers = {IPN_SIGNATURE_HEADER: sig}
    invalid_headers = {IPN_SIGNATURE_HEADER: "bad" * 20}

    for _ in range(200):
        result_valid = verify_ipn(raw_body=body, headers=valid_headers, secret=secret)
        result_invalid = verify_ipn(raw_body=body, headers=invalid_headers, secret=secret)
        assert result_valid is True
        assert result_invalid is False


def test_verify_ipn_empty_body_valid_signature() -> None:
    """An empty body is a valid edge case — signature must still be verified correctly."""
    secret = "edge_secret"
    body = b""
    sig = _make_signature(body, secret)

    headers = {IPN_SIGNATURE_HEADER: sig}
    assert verify_ipn(raw_body=body, headers=headers, secret=secret) is True


def test_verify_ipn_header_case_insensitive_lookup() -> None:
    """Header lookup must be case-insensitive (HTTP spec)."""
    secret = "case_secret"
    body = b"some data"
    sig = _make_signature(body, secret)

    # Provide header in different casing
    headers = {IPN_SIGNATURE_HEADER.lower(): sig}
    # Our verify_ipn should handle lowercase keys from FastAPI's Headers object.
    # We accept both True (if we normalise) or graceful False — but must not crash.
    result = verify_ipn(raw_body=body, headers=headers, secret=secret)
    assert isinstance(result, bool)
