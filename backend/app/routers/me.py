"""/me endpoints — authenticated user + current subscription."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserRead
from app.auth.users import current_active_user
from app.deps import get_db
from app.models.user import User
from app.repositories import subscriptions as sub_repo
from app.routers.subscriptions import _subscription_to_out
from app.schemas.subscriptions import SubscriptionOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserRead)
async def read_me(user: User = Depends(current_active_user)) -> User:
    """Return the currently authenticated user."""
    return user


@router.get("/me/subscription", response_model=SubscriptionOut | None)
async def read_me_subscription(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut | None:
    """Return the caller's current (non-canceled) subscription, or null.

    Returns 200 with null body when the user has no subscription — this is
    deliberately not a 404 so the frontend can render an "empty" state
    without branching on error codes.
    """
    sub = await sub_repo.get_current_for_user(db, user.id)
    if sub is None:
        return None
    return _subscription_to_out(sub)
