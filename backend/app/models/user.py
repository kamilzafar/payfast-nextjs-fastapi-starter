"""User model — extends fastapi-users SQLAlchemy base table."""

from __future__ import annotations

from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(SQLAlchemyBaseUserTable[int], TimestampMixin, Base):
    """Application user.

    Inherits id, email, hashed_password, is_active, is_superuser, is_verified
    from `SQLAlchemyBaseUserTable`. Uses int PK for simplicity.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(nullable=True)
    phone: Mapped[str | None] = mapped_column(nullable=True)
