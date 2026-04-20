"""Import all models so Alembic's autogenerate can discover them."""

from app.models.base import Base, TimestampMixin
from app.models.invoice import Invoice, InvoiceStatus
from app.models.jobs_run import JobsRun
from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.models.webhook_event import WebhookEvent

__all__ = [
    "Base",
    "TimestampMixin",
    "Invoice",
    "InvoiceStatus",
    "JobsRun",
    "PaymentAttempt",
    "PaymentAttemptStatus",
    "Plan",
    "PlanInterval",
    "Subscription",
    "SubscriptionStatus",
    "User",
    "WebhookEvent",
]
