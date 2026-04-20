"""Plans router — public list of active plans."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.plan import Plan, PlanInterval

router = APIRouter(tags=["plans"])


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    amount_minor: int
    currency: str
    interval: PlanInterval
    trial_days: int
    is_active: bool


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[Plan]:
    """Return all active plans ordered by price ascending."""
    stmt = (
        select(Plan)
        .where(Plan.is_active.is_(True))
        .order_by(Plan.amount_minor.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
