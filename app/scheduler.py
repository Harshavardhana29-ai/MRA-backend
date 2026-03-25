"""
Scheduler engine — manages APScheduler lifecycle and job registration.

Uses AsyncIOScheduler (APScheduler 3.x) running inside the FastAPI event loop.
Jobs are persisted in our own `scheduled_jobs` table; APScheduler uses an
in-memory job store that is reconciled from the database on every startup.
This approach avoids sync/async driver conflicts and is production-portable:
swap to SQLAlchemyJobStore when deploying with multiple replicas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

log = logging.getLogger("mra.scheduler")

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 3,
                "misfire_grace_time": 300,
            },
            timezone="UTC",
        )
        _scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
        _scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)
    return _scheduler


def _on_job_error(event):
    log.error("Scheduler job %s raised: %s", event.job_id, event.exception)


def _on_job_missed(event):
    log.warning("Scheduler job %s missed its fire time", event.job_id)


def _make_job_id(db_id: UUID) -> str:
    return f"sj-{db_id}"


def register_job(
    job_id: UUID,
    cron_expression: str | None,
    one_time_date: datetime | None,
    tz: str,
    schedule_type: str,
) -> None:
    """Add or replace a job in the live scheduler."""
    scheduler = get_scheduler()
    apscheduler_id = _make_job_id(job_id)

    if scheduler.get_job(apscheduler_id):
        scheduler.remove_job(apscheduler_id)

    trigger = _build_trigger(schedule_type, cron_expression, one_time_date, tz)
    if trigger is None:
        return

    from app.services.schedule_service import execute_scheduled_job

    scheduler.add_job(
        execute_scheduled_job,
        trigger=trigger,
        id=apscheduler_id,
        args=[job_id],
        replace_existing=True,
    )
    log.info("Registered scheduler job %s", apscheduler_id)


def unregister_job(job_id: UUID) -> None:
    scheduler = get_scheduler()
    apscheduler_id = _make_job_id(job_id)
    if scheduler.get_job(apscheduler_id):
        scheduler.remove_job(apscheduler_id)
        log.info("Unregistered scheduler job %s", apscheduler_id)


def get_next_fire_time(job_id: UUID) -> datetime | None:
    scheduler = get_scheduler()
    job = scheduler.get_job(_make_job_id(job_id))
    if job and job.next_run_time:
        return job.next_run_time.astimezone(timezone.utc)
    return None


def _build_trigger(schedule_type, cron_expression, one_time_date, tz):
    if schedule_type == "recurring" and cron_expression:
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            log.warning("Invalid cron expression: %s", cron_expression)
            return None
        minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            minute=minute, hour=hour, day=day,
            month=month, day_of_week=day_of_week,
            timezone=tz,
        )
    if schedule_type == "one-time" and one_time_date:
        return DateTrigger(run_date=one_time_date, timezone=tz)
    return None


async def load_jobs_from_db() -> int:
    """Called on startup — loads all enabled jobs from DB into the scheduler."""
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.scheduled_job import ScheduledJob

    loaded = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScheduledJob).where(
                ScheduledJob.enabled.is_(True),
                ScheduledJob.status.in_(["active", "running"]),
            )
        )
        jobs = result.scalars().all()
        for job in jobs:
            try:
                register_job(
                    job.id,
                    job.cron_expression,
                    job.one_time_date,
                    job.timezone,
                    job.schedule_type,
                )
                nft = get_next_fire_time(job.id)
                if nft and nft != job.next_run_at:
                    job.next_run_at = nft
                loaded += 1
            except Exception:
                log.exception("Failed to register job %s on startup", job.id)
        await db.commit()

    log.info("Loaded %d scheduled jobs from database", loaded)
    return loaded
