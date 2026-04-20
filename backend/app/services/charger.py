"""Charger abstraction — encapsulates how we attempt to collect payment.

Today's implementation (HostedRedirectCharger) sends the user an email
containing a pay link and returns requires_user_action=True.  No actual charge
happens server-side; we rely on the user clicking through PayFast's hosted page.

Future implementation (TokenCharger) will perform a server-initiated MIT charge
via the PayFast Permanent Token API when that becomes available.

State returned via ChargeResult dataclass so callers can branch on the outcome.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChargeResult:
    """Outcome of a charge attempt."""

    attempted: bool
    succeeded: bool
    requires_user_action: bool


class Charger(ABC):
    """Abstract charger interface."""

    @abstractmethod
    async def charge(
        self,
        db: Any,
        invoice: Any,
        user: Any,
        plan: Any,
    ) -> ChargeResult:
        """Attempt to charge the user for `invoice`.

        Args:
            db:      AsyncSession — may be used to persist attempt records.
            invoice: Invoice ORM object.
            user:    User ORM object (has .email, .name).
            plan:    Plan ORM object (has .name, .amount_minor).

        Returns:
            ChargeResult describing what happened.
        """
        ...


class HostedRedirectCharger(Charger):
    """Email the user a payment link; no direct charge.

    This is the current implementation while we wait for PayFast's MIT
    (Merchant Initiated Transaction / Permanent Token) API.

    Flow:
    1. Build pay_url = FRONTEND_URL/checkout/{invoice.id}
    2. Send email using the provided email_sender + template_name
    3. Return ChargeResult(attempted=True, succeeded=False, requires_user_action=True)
    """

    def __init__(
        self,
        email_sender: Any,
        template_name: str,
        settings: Any,
    ) -> None:
        self._email_sender = email_sender
        self._template_name = template_name
        self._settings = settings

    async def charge(
        self,
        db: Any,
        invoice: Any,
        user: Any,
        plan: Any,
    ) -> ChargeResult:
        pay_url = f"{self._settings.FRONTEND_URL}/checkout/{invoice.id}"

        amount_display = invoice.amount / 100  # minor units -> major

        await self._email_sender.send(
            to=user.email,
            subject=f"Action required: {plan.name} renewal",
            template_name=self._template_name,
            context={
                "user": user,
                "plan": plan,
                "invoice": invoice,
                "pay_url": pay_url,
                "amount_display": f"{amount_display:.2f}",
            },
        )

        return ChargeResult(
            attempted=True,
            succeeded=False,
            requires_user_action=True,
        )


class TokenCharger(Charger):
    """Server-initiated charge via PayFast Permanent Token (MIT).

    NOT YET AVAILABLE — stub kept here for future implementation.
    Enable when PayFast MIT API becomes available and a stored token
    per-user can be used to initiate charges without user interaction.
    """

    async def charge(
        self,
        db: Any,
        invoice: Any,
        user: Any,
        plan: Any,
    ) -> ChargeResult:
        raise NotImplementedError(
            "PayFast permanent-token MIT not available yet. "
            "Use HostedRedirectCharger until token-based charging is supported."
        )
