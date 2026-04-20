"""Plan repository — DB access helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan


async def list_active_plans(db: AsyncSession) -> list[Plan]:
    """Return all active plans ordered by price ascending."""
    result = await db.execute(
        select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.amount_minor.asc())
    )
    return list(result.scalars().all())


async def get_plan_by_id(db: AsyncSession, plan_id: int) -> Plan | None:
    """Fetch a single plan by its primary key."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    return result.scalar_one_or_none()
