"""Tests for PayFast gateway client — get_access_token().

Written FIRST (TDD Red phase) before implementation exists.
All tests use pytest-httpx to mock HTTP without live connections.
"""

from __future__ import annotations

import os

import pytest
import httpx
from pytest_httpx import HTTPXMock

# Ensure settings can load without real env
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from app.services.payfast.client import get_access_token
from app.services.payfast.exceptions import PayFastAuthError, PayFastError


BASE_URL = "https://ipguat.apps.net.pk"
MERCHANT_ID = "test_merchant"
SECURED_KEY = "test_key"
AMOUNT_MINOR = 150000  # 1500 PKR in paisa
BASKET_ID = "basket-abc-123"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def token_url() -> str:
    from app.services.payfast.constants import TOKEN_PATH
    return f"{BASE_URL}{TOKEN_PATH}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_access_token_success(httpx_mock: HTTPXMock, token_url: str) -> None:
    """A valid 200 response with an ACCESS_TOKEN field returns an AccessToken."""
    httpx_mock.add_response(
        url=token_url,
        method="POST",
        json={"ACCESS_TOKEN": "abc123", "RESPONSE_CODE": "00"},
        status_code=200,
    )

    result = await get_access_token(
        merchant_id=MERCHANT_ID,
        secured_key=SECURED_KEY,
        amount_minor=AMOUNT_MINOR,
        basket_id=BASKET_ID,
        base_url=BASE_URL,
    )

    assert result.token == "abc123"


@pytest.mark.asyncio
async def test_get_access_token_auth_error(httpx_mock: HTTPXMock, token_url: str) -> None:
    """A 401 response raises PayFastAuthError."""
    httpx_mock.add_response(
        url=token_url,
        method="POST",
        status_code=401,
        text="Unauthorized",
    )

    with pytest.raises(PayFastAuthError):
        await get_access_token(
            merchant_id=MERCHANT_ID,
            secured_key=SECURED_KEY,
            amount_minor=AMOUNT_MINOR,
            basket_id=BASKET_ID,
            base_url=BASE_URL,
        )


@pytest.mark.asyncio
async def test_get_access_token_non_2xx_raises_auth_error(
    httpx_mock: HTTPXMock, token_url: str
) -> None:
    """Any non-2xx response raises PayFastAuthError."""
    httpx_mock.add_response(
        url=token_url,
        method="POST",
        status_code=403,
        text="Forbidden",
    )

    with pytest.raises(PayFastAuthError):
        await get_access_token(
            merchant_id=MERCHANT_ID,
            secured_key=SECURED_KEY,
            amount_minor=AMOUNT_MINOR,
            basket_id=BASKET_ID,
            base_url=BASE_URL,
        )


@pytest.mark.asyncio
async def test_get_access_token_missing_token_field(
    httpx_mock: HTTPXMock, token_url: str
) -> None:
    """A 200 response without a TOKEN field raises PayFastAuthError."""
    httpx_mock.add_response(
        url=token_url,
        method="POST",
        json={"RESPONSE_CODE": "99", "MESSAGE": "something went wrong"},
        status_code=200,
    )

    with pytest.raises(PayFastAuthError, match="ACCESS_TOKEN"):
        await get_access_token(
            merchant_id=MERCHANT_ID,
            secured_key=SECURED_KEY,
            amount_minor=AMOUNT_MINOR,
            basket_id=BASKET_ID,
            base_url=BASE_URL,
        )


@pytest.mark.asyncio
async def test_get_access_token_timeout(httpx_mock: HTTPXMock, token_url: str) -> None:
    """A timeout raises PayFastError (not an unhandled httpx exception)."""
    httpx_mock.add_exception(
        httpx.TimeoutException("timed out", request=None),
        url=token_url,
        method="POST",
    )

    with pytest.raises(PayFastError):
        await get_access_token(
            merchant_id=MERCHANT_ID,
            secured_key=SECURED_KEY,
            amount_minor=AMOUNT_MINOR,
            basket_id=BASKET_ID,
            base_url=BASE_URL,
        )


@pytest.mark.asyncio
async def test_get_access_token_sends_correct_form_fields(
    httpx_mock: HTTPXMock, token_url: str
) -> None:
    """Body must include MERCHANT_ID, SECURED_KEY, TXNAMT, BASKET_ID — and NOT CURRENCY_CODE."""
    httpx_mock.add_response(
        url=token_url,
        method="POST",
        json={"ACCESS_TOKEN": "xyz789"},
        status_code=200,
    )

    await get_access_token(
        merchant_id=MERCHANT_ID,
        secured_key=SECURED_KEY,
        amount_minor=AMOUNT_MINOR,
        basket_id=BASKET_ID,
        currency="PKR",
        base_url=BASE_URL,
    )

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    req = requests[0]

    body = req.content.decode("utf-8")
    assert "MERCHANT_ID=test_merchant" in body
    assert "SECURED_KEY=test_key" in body
    assert "BASKET_ID=basket-abc-123" in body
    # 150000 paisa = 1500.00 PKR (major units)
    assert "TXNAMT=1500.00" in body
    assert "CURRENCY_CODE=PKR" in body


@pytest.mark.asyncio
async def test_get_access_token_accepts_injected_http_client(
    httpx_mock: HTTPXMock, token_url: str
) -> None:
    """Passing an explicit http_client uses that client (dependency injection)."""
    httpx_mock.add_response(
        url=token_url,
        method="POST",
        json={"ACCESS_TOKEN": "injected-token"},
        status_code=200,
    )

    async with httpx.AsyncClient() as http_client:
        result = await get_access_token(
            merchant_id=MERCHANT_ID,
            secured_key=SECURED_KEY,
            amount_minor=AMOUNT_MINOR,
            basket_id=BASKET_ID,
            base_url=BASE_URL,
            http_client=http_client,
        )

    assert result.token == "injected-token"
