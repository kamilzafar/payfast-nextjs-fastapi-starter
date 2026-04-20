"""Add cancel_at_period_end to subscriptions.

Phase 4 introduces self-serve cancel. Users can schedule a cancellation that
takes effect at the end of the current billing period. This column stores
that intent; the Phase 5 renewal cron flips `status` to `canceled` when
`cancel_at_period_end = true` AND `current_period_end <= now()`.

Default: `false` (existing rows stay active until explicitly cancelled).
Server-side default keeps the column NOT NULL without needing a data
backfill.

Revision ID: 0002_add_cancel_at_period_end
Revises: 0001_initial
Create Date: 2026-04-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_cancel_at_period_end"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "cancel_at_period_end")
