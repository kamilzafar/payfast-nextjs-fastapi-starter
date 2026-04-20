"""APScheduler startup + job registration — Phase 5.

Creates an AsyncIOScheduler with three jobs:
  - daily_renewal_sweep    : CronTrigger at 02:00 UTC daily
  - reconciliation_sweep   : IntervalTrigger every 15 minutes
  - hourly_dunning_check   : IntervalTrigger every 60 minutes

Feature flag: SCHEDULER_ENABLED (bool, default True).
  - Set to False in test environments to prevent scheduler from starting.
  - Tests call renewal functions directly rather than via scheduler.

Jobstore: in-memory (MemoryJobStore) — no persistence needed between restarts;
          jobs are re-registered on each startup.
Executor: AsyncIOExecutor — matches FastAPI's async event loop.
"""

from __future__ import annotations

import structlog
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = structlog.get_logger(__name__)


def build_scheduler(
    db_session_factory,
    settings,
    charger,
    email_sender,
    http_client,
) -> AsyncIOScheduler:
    """Construct and configure the scheduler.

    Does NOT call scheduler.start() — the caller (lifespan) does that.

    Returns:
        Configured AsyncIOScheduler ready to start.
    """
    from app.services.renewals import (  # noqa: PLC0415
        daily_renewal_sweep,
        hourly_dunning_check,
        reconciliation_sweep,
    )

    scheduler = AsyncIOScheduler(
        jobstores={"default": MemoryJobStore()},
        executors={"default": AsyncIOExecutor()},
        job_defaults={
            "coalesce": True,       # collapse missed runs into one
            "max_instances": 1,     # never run a job concurrently with itself
            "misfire_grace_time": 300,  # tolerate up to 5-min late start
        },
        timezone="UTC",
    )

    # Job 1: Daily renewal sweep at 02:00 UTC
    scheduler.add_job(
        daily_renewal_sweep,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="daily_renewal_sweep",
        name="Daily Renewal Sweep",
        kwargs={
            "db_session_factory": db_session_factory,
            "settings": settings,
            "charger": charger,
            "email_sender": email_sender,
        },
    )

    # Job 2: Reconciliation sweep every 15 minutes
    scheduler.add_job(
        reconciliation_sweep,
        trigger=IntervalTrigger(minutes=15, timezone="UTC"),
        id="reconciliation_sweep",
        name="PayFast Reconciliation Sweep",
        kwargs={
            "db_session_factory": db_session_factory,
            "settings": settings,
            "http_client": http_client,
        },
    )

    # Job 3: Hourly dunning check
    scheduler.add_job(
        hourly_dunning_check,
        trigger=IntervalTrigger(minutes=60, timezone="UTC"),
        id="hourly_dunning_check",
        name="Hourly Dunning Check",
        kwargs={
            "db_session_factory": db_session_factory,
            "settings": settings,
            "email_sender": email_sender,
        },
    )

    return scheduler
