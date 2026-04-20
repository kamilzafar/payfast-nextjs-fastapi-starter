"""WebhookEvent repository — idempotency helpers.

Idempotency key choice: we use `txn_id` from the IPN payload as the
`provider_event_id` when present.  If `txn_id` is absent, we fall back
to SHA-256(raw_body) as a content-based dedup key.  This is documented
here as the single place to change the strategy.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def try_insert(
    db: AsyncSession,
    provider_event_id: str,
    payload: dict[str, Any],
) -> bool:
    """Attempt to insert a webhook_event row.

    Uses INSERT ... ON CONFLICT DO NOTHING.
    Returns True if a new row was inserted (first delivery).
    Returns False if the event was a duplicate (already processed).
    """
    now = datetime.now(tz=timezone.utc)
    stmt = text(
        """
        INSERT INTO webhook_events (provider, provider_event_id, payload, processed_at, created_at, updated_at)
        VALUES ('payfast', :event_id, cast(:payload as jsonb), :now, :now, :now)
        ON CONFLICT (provider, provider_event_id) DO NOTHING
        RETURNING id
        """
    )
    result = await db.execute(
        stmt,
        {
            "event_id": provider_event_id,
            "payload": __import__("json").dumps(payload),
            "now": now,
        },
    )
    row = result.fetchone()
    return row is not None


def derive_event_id(raw_body: bytes, parsed: dict[str, Any]) -> str:
    """Derive a stable idempotency key from an IPN notification.

    Strategy (in order of preference):
      1. Use parsed['txn_id'] if present and non-empty.
      2. Fall back to SHA-256(raw_body) as a content fingerprint.
    """
    txn_id = parsed.get("txn_id") or parsed.get("TXNID") or parsed.get("transaction_id")
    if txn_id:
        return str(txn_id)
    return hashlib.sha256(raw_body).hexdigest()
