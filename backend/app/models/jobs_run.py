"""JobsRun — idempotency marker for daily cron jobs."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JobsRun(TimestampMixin, Base):
    """Records that `job_name` ran on `run_date` — UNIQUE pair for idempotency."""

    __tablename__ = "jobs_runs"
    __table_args__ = (
        UniqueConstraint("job_name", "run_date", name="uq_jobs_name_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
