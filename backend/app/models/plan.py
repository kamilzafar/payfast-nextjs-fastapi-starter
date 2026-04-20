"""Subscription plan model."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PlanInterval(str, enum.Enum):
    """Billing interval for a plan."""

    monthly = "monthly"
    yearly = "yearly"


class Plan(TimestampMixin, Base):
    """A purchasable subscription plan.

    amount_minor — plan price in minor units (paisa for PKR).
                   e.g. 150000 = 1500.00 PKR.
    currency     — ISO 4217 currency code (default 'PKR').
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    interval: Mapped[PlanInterval] = mapped_column(
        Enum(PlanInterval, name="plan_interval"),
        nullable=False,
        default=PlanInterval.monthly,
    )
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
