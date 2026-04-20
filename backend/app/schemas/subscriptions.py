"""Pydantic schemas for subscription endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CreateSubscriptionRequest(BaseModel):
    plan_id: int


class CreateSubscriptionResponse(BaseModel):
    subscription_id: int
    invoice_id: int
    basket_id: str  # UUID as string
    checkout_url: str | None = None


class PlanEmbedded(BaseModel):
    """Shallow plan representation embedded in subscription responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    amount_minor: int
    currency: str
    interval: str  # "monthly" | "yearly" — serialized from PlanInterval enum
    trial_days: int


class SubscriptionOut(BaseModel):
    """Outbound subscription representation with embedded plan.

    Used by:
    - GET /me/subscription
    - POST /subscriptions/{id}/cancel
    """

    id: int
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    next_billing_at: datetime | None = None
    canceled_at: datetime | None = None
    cancel_at_period_end: bool
    plan: PlanEmbedded


class CancelSubscriptionRequest(BaseModel):
    """Body for POST /subscriptions/{id}/cancel.

    at_period_end:
      True  (default) — schedule cancellation for end of period; keep status.
      False           — cancel immediately; set status=canceled.
    """

    at_period_end: bool = True


# Public alias: the cancel endpoint returns the same shape as the GET /me/sub.
CancelSubscriptionResponse = SubscriptionOut
