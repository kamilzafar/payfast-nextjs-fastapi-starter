"""Initial schema.

Creates the pgcrypto extension, all enum types, and all tables required by
phase 1 (users, plans, subscriptions, invoices, payment_attempts,
webhook_events, jobs_runs).

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgcrypto for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Enum types
    plan_interval = postgresql.ENUM("monthly", "yearly", name="plan_interval")
    plan_interval.create(op.get_bind(), checkfirst=True)

    subscription_status = postgresql.ENUM(
        "trialing", "active", "past_due", "canceled", name="subscription_status"
    )
    subscription_status.create(op.get_bind(), checkfirst=True)

    invoice_status = postgresql.ENUM(
        "open", "paid", "void", name="invoice_status"
    )
    invoice_status.create(op.get_bind(), checkfirst=True)

    payment_attempt_status = postgresql.ENUM(
        "pending", "succeeded", "failed", name="payment_attempt_status"
    )
    payment_attempt_status.create(op.get_bind(), checkfirst=True)

    # users (fastapi-users base columns + our extras)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # plans
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="PKR"),
        sa.Column(
            "interval",
            postgresql.ENUM(name="plan_interval", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "trial_days", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="subscription_status", create_type=False),
            nullable=False,
        ),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_billing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index(
        "ix_subscriptions_next_billing_at", "subscriptions", ["next_billing_at"]
    )

    # invoices
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "basket_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="invoice_status", create_type=False),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payfast_txn_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_invoices_subscription_id", "invoices", ["subscription_id"]
    )
    op.create_index("ix_invoices_payfast_txn_id", "invoices", ["payfast_txn_id"])

    # payment_attempts
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "invoice_id",
            sa.Integer(),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "basket_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="payment_attempt_status", create_type=False),
            nullable=False,
        ),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_payment_attempts_invoice_id", "payment_attempts", ["invoice_id"]
    )
    op.create_index(
        "ix_payment_attempts_basket_id", "payment_attempts", ["basket_id"]
    )

    # webhook_events
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_event_id", sa.String(length=200), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_webhook_provider_event"
        ),
    )

    # jobs_runs
    op.create_table(
        "jobs_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("job_name", "run_date", name="uq_jobs_name_date"),
    )


def downgrade() -> None:
    op.drop_table("jobs_runs")
    op.drop_table("webhook_events")
    op.drop_index("ix_payment_attempts_basket_id", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_invoice_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")
    op.drop_index("ix_invoices_payfast_txn_id", table_name="invoices")
    op.drop_index("ix_invoices_subscription_id", table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_subscriptions_next_billing_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    for enum_name in (
        "payment_attempt_status",
        "invoice_status",
        "subscription_status",
        "plan_interval",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
