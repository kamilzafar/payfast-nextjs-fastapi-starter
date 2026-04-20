"""Pydantic v2 type models for the PayFast gateway service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AccessToken(BaseModel):
    """Parsed response from the PayFast token endpoint.

    token      — the one-time access token string.
    expires_at — expiry datetime if provided by PayFast, otherwise None.
    """

    token: str
    expires_at: datetime | None = None


class CheckoutRedirect(BaseModel):
    """Data needed to build the auto-POST HTML form that redirects the user
    to PayFast's hosted checkout page.

    action_url — the PayFast POST_TRANSACTION_PATH endpoint.
    fields     — key/value pairs to embed as hidden form inputs.
    """

    action_url: str
    fields: dict[str, str]


class IpnPayload(BaseModel):
    """Parsed PayFast IPN notification body.

    TODO: Expand field definitions when live IPN sample is available.
    Uses model_config extra='allow' so unknown PayFast fields are preserved.
    """

    model_config = {"extra": "allow"}

    # Known / expected fields (all optional until confirmed against live IPNs)
    transaction_id: str | None = None
    basket_id: str | None = None
    amount: str | None = None
    status: str | None = None

    # Raw payload preserved for audit / debugging
    raw: dict[str, Any] = {}
