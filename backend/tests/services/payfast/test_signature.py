"""Tests for verify_ipn() and compute_validation_hash().

Contract (PayFast IPN Integration Document, Apr 2026):
    validation_hash = SHA256(basket_id|secured_key|merchant_id|err_code)

Reference example from the docs:
    "BAS-01|jdnkaabcks|102|000"
    -> e8192a7554dd699975adf39619c703a492392edf5e416a61e183866ecdf6a2a2
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from app.services.payfast.signature import compute_validation_hash, verify_ipn


DOC_EXAMPLE_HASH = (
    "e8192a7554dd699975adf39619c703a492392edf5e416a61e183866ecdf6a2a2"
)


def test_compute_validation_hash_matches_doc_example() -> None:
    """The exact worked example from the IPN Integration Document must match."""
    h = compute_validation_hash(
        basket_id="BAS-01",
        secured_key="jdnkaabcks",
        merchant_id="102",
        err_code="000",
    )
    assert h == DOC_EXAMPLE_HASH


def test_verify_ipn_valid_payload() -> None:
    payload = {
        "basket_id": "BAS-01",
        "err_code": "000",
        "err_msg": "Transaction has been completed.",
        "transaction_id": "abc-123",
        "validation_hash": DOC_EXAMPLE_HASH,
    }
    assert verify_ipn(payload, secured_key="jdnkaabcks", merchant_id="102") is True


def test_verify_ipn_tampered_basket_id() -> None:
    payload = {
        "basket_id": "BAS-99",  # tampered
        "err_code": "000",
        "validation_hash": DOC_EXAMPLE_HASH,
    }
    assert verify_ipn(payload, secured_key="jdnkaabcks", merchant_id="102") is False


def test_verify_ipn_wrong_secured_key() -> None:
    payload = {
        "basket_id": "BAS-01",
        "err_code": "000",
        "validation_hash": DOC_EXAMPLE_HASH,
    }
    assert verify_ipn(payload, secured_key="wrong_key", merchant_id="102") is False


def test_verify_ipn_wrong_merchant_id() -> None:
    payload = {
        "basket_id": "BAS-01",
        "err_code": "000",
        "validation_hash": DOC_EXAMPLE_HASH,
    }
    assert verify_ipn(payload, secured_key="jdnkaabcks", merchant_id="999") is False


def test_verify_ipn_missing_validation_hash() -> None:
    payload = {"basket_id": "BAS-01", "err_code": "000"}
    assert verify_ipn(payload, secured_key="jdnkaabcks", merchant_id="102") is False


def test_verify_ipn_missing_basket_id() -> None:
    payload = {"err_code": "000", "validation_hash": DOC_EXAMPLE_HASH}
    assert verify_ipn(payload, secured_key="jdnkaabcks", merchant_id="102") is False


def test_verify_ipn_missing_err_code() -> None:
    payload = {"basket_id": "BAS-01", "validation_hash": DOC_EXAMPLE_HASH}
    assert verify_ipn(payload, secured_key="jdnkaabcks", merchant_id="102") is False


def test_verify_ipn_hash_case_insensitive() -> None:
    """PayFast returns lowercase hex; accept uppercase too (robustness)."""
    payload = {
        "basket_id": "BAS-01",
        "err_code": "000",
        "validation_hash": DOC_EXAMPLE_HASH.upper(),
    }
    assert verify_ipn(payload, secured_key="jdnkaabcks", merchant_id="102") is True


def test_compute_validation_hash_pipe_is_literal() -> None:
    """The pipe character is part of the hashed string, not a separator operator."""
    with_pipe = compute_validation_hash("A", "B", "C", "D")
    without_pipe = compute_validation_hash("A|B|C", "", "", "D")
    # Both happen to produce 'A|B|C||...|D' / 'A|B|C|||D' — very similar input.
    # Assert the obvious: pipes are present in the input, and hashes differ.
    assert with_pipe != without_pipe


def test_real_ipn_parameters_sample_hash_is_reproducible() -> None:
    """Smoke: compute_validation_hash is deterministic for any input."""
    h1 = compute_validation_hash("ITEM-PFTOK047", "some_key", "103", "000")
    h2 = compute_validation_hash("ITEM-PFTOK047", "some_key", "103", "000")
    assert h1 == h2
