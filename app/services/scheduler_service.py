import asyncio
import logging
import time
from datetime import datetime, timezone as tz
from uuid import UUID
from zoneinfo import ZoneInfo

from croniter import croniter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.scheduled_job import ScheduledJob, ScheduledJobRun
from app.models.workflow import Workflow, WorkflowAgent
from app.models.run import WorkflowRun
from app.schemas.scheduled_job import (
    ScheduledJobCreate, ScheduledJobUpdate, ScheduledJobResponse,
    JobHistoryResponse, JobCountsResponse,
)
from app.services.run_service import _execute_run

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 3,
                "misfire_grace_time": 300,
            },
        )
    return _scheduler


# ─── Lifecycle ────────────────────────────────────────────────

async def start_scheduler():
    scheduler = _get_scheduler()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScheduledJob).where(ScheduledJob.enabled.is_(True))
        )
        jobs = result.scalars().all()
        loaded = 0
        for job in jobs:
            if _add_to_apscheduler(job):
                loaded += 1
    scheduler.start()
    log.info("Scheduler started — %d active jobs loaded", loaded)


async def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
    _scheduler = None


# ─── APScheduler helpers ─────────────────────────────────────

def _add_to_apscheduler(job: ScheduledJob) -> bool:
    scheduler = _get_scheduler()
    try:
        if job.schedule_type == "recurring" and job.cron_expression:
            parts = job.cron_expression.strip().split()
            if len(parts) != 5:
                log.warning("Invalid cron for job %s: %s", job.id, job.cron_expression)
                return False
            trigger = CronTrigger(
                minute=parts[0], hour=parts[1], day=parts[2],
                month=parts[3], day_of_week=parts[4],
                timezone=job.timezone or "UTC",
            )
        elif job.schedule_type == "one-time" and job.one_time_date:
            from datetime import timedelta
            run_dt = job.one_time_date if job.one_time_date.tzinfo else job.one_time_date.replace(tzinfo=tz.utc)
            if run_dt < datetime.now(tz.utc) - timedelta(seconds=300):
                return False
            trigger = DateTrigger(
                run_date=run_dt,
                timezone=job.timezone or "UTC",
            )
        else:
            return False

        scheduler.add_job(
            _run_scheduled_job,
            trigger=trigger,
            id=str(job.id),
            args=[job.id],
            replace_existing=True,
            name=job.job_name,
        )
        return True
    except Exception as e:
        log.error("Failed to register job %s: %s", job.id, e)
        return False


def _remove_from_apscheduler(job_id: UUID):
    try:
        _get_scheduler().remove_job(str(job_id))
    except (JobLookupError, KeyError):
        pass


# ─── Time helpers ────────────────────────────────────────────

def _compute_next_run(cron_expression: str, tz_str: str) -> datetime | None:
    try:
        zone = ZoneInfo(tz_str) if tz_str else ZoneInfo("UTC")
        now = datetime.now(zone)
        return croniter(cron_expression, now).get_next(datetime)
    except Exception:
        return None


def _cron_to_type(cron: str) -> str:
    parts = cron.strip().split()
    if len(parts) != 5:
        return "Custom"
    minute, hour, dom, _month, dow = parts
    if minute == "*" and hour == "*":
        return "Every Minute"
    if hour == "*":
        return "Hourly"
    if dom == "*" and dow == "*":
        return "Daily"
    if dow != "*":
        return "Weekly"
    if dom != "*":
        return "Monthly"
    return "Custom"


_DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _cron_to_schedule_time(cron: str) -> str:
    parts = cron.strip().split()
    if len(parts) != 5:
        return cron
    minute, hour, dom, _month, dow = parts
    m = minute.zfill(2)
    h = hour.zfill(2)
    if minute == "*" and hour == "*":
        return "* * * * *"
    if hour == "*":
        return f":{m}"
    if dow != "*" and dom == "*":
        try:
            name = _DAY_NAMES[int(dow)]
        except (ValueError, IndexError):
            name = dow
        return f"{name} {h}:{m}"
    if dom != "*":
        try:
            d = int(dom)
            s = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"}.get(d, "th")
        except ValueError:
            d, s = dom, ""
        return f"{d}{s} {h}:{m}"
    return f"{h}:{m}"


def _format_relative(dt: datetime | None) -> str:
    if not dt:
        return "—"
    now = datetime.now(tz.utc)
    dt_utc = dt.astimezone(tz.utc) if dt.tzinfo else dt.replace(tzinfo=tz.utc)
    diff_days = (dt_utc.date() - now.date()).days
    hm = dt_utc.strftime("%H:%M")
    if diff_days == 0:
        return f"Today {hm}"
    if diff_days == 1:
        return f"Tomorrow {hm}"
    if diff_days == -1:
        return f"Yesterday {hm}"
    return dt_utc.strftime("%b %d %H:%M")


# ─── Model → Response mapping ────────────────────────────────

def _to_response(job: ScheduledJob, wf_title: str = "—") -> ScheduledJobResponse:
    if job.schedule_type == "one-time":
        jtype = "One-time"
        stime = job.one_time_date.strftime("%Y-%m-%d %H:%M") if job.one_time_date else "—"
    else:
        jtype = _cron_to_type(job.cron_expression or "")
        stime = _cron_to_schedule_time(job.cron_expression or "")

    return ScheduledJobResponse(
        id=job.id,
        job_name=job.job_name,
        type=jtype,
        workflow_id=job.workflow_id,
        workflow_title=wf_title,
        schedule_time=stime,
        next_run=_format_relative(job.next_run_at),
        last_run=_format_relative(job.last_run_at),
        status=job.status,
        enabled=job.enabled,
        jobs_done=job.jobs_done,
        user_prompt=job.user_prompt,
        cron_expression=job.cron_expression,
        timezone=job.timezone,
        wake_mode=job.wake_mode,
        output_format=job.output_format,
        output_schema=job.output_schema_text,
        delivery_methods=job.delivery_methods or ["internal-log"],
        failure_behavior={
            "concurrency": job.concurrency_policy,
            "retry": {
                "enabled": job.retry_enabled,
                "maxAttempts": job.retry_max_attempts,
                "delaySeconds": job.retry_delay_seconds,
                "backoff": job.retry_backoff,
            },
            "autoDisableAfter": job.auto_disable_after,
        },
    )


# ─── CRUD ────────────────────────────────────────────────────

async def create_job(
    db: AsyncSession, data: ScheduledJobCreate, user_id: UUID | None = None,
) -> ScheduledJobResponse:
    wf = await db.execute(
        select(Workflow).where(Workflow.id == data.workflow_id, Workflow.deleted_at.is_(None))
    )
    workflow = wf.scalar_one_or_none()
    if not workflow:
        raise ValueError("Workflow not found")

    one_time_dt = None
    if data.schedule_type == "one-time" and data.one_time_date:
        from dateutil.parser import parse as dt_parse
        one_time_dt = dt_parse(data.one_time_date)
        if one_time_dt.tzinfo is None:
            user_tz = ZoneInfo(data.timezone) if data.timezone else ZoneInfo("UTC")
            one_time_dt = one_time_dt.replace(tzinfo=user_tz)

    job = ScheduledJob(
        user_id=user_id,
        job_name=data.name,
        workflow_id=data.workflow_id,
        user_prompt=data.user_prompt,
        enabled=data.enabled,
        schedule_type=data.schedule_type,
        cron_expression=data.cron_expression if data.schedule_type == "recurring" else None,
        one_time_date=one_time_dt,
        timezone=data.timezone,
        wake_mode=data.wake_mode,
        output_format=data.output_format,
        output_schema_text=data.output_schema,
        delivery_methods=data.delivery_methods,
        concurrency_policy=data.concurrency_policy,
        retry_enabled=data.retry_enabled,
        retry_max_attempts=data.retry_max_attempts,
        retry_delay_seconds=data.retry_delay_seconds,
        retry_backoff=data.retry_backoff,
        auto_disable_after=data.auto_disable_after,
        status="active" if data.enabled else "paused",
    )

    if data.schedule_type == "recurring" and data.cron_expression:
        job.next_run_at = _compute_next_run(data.cron_expression, data.timezone)
    elif data.schedule_type == "one-time" and one_time_dt:
        job.next_run_at = one_time_dt

    db.add(job)
    await db.commit()
    await db.refresh(job)

    if data.enabled:
        _add_to_apscheduler(job)

    return _to_response(job, workflow.title)


async def update_job(
    db: AsyncSession, job_id: UUID, data: ScheduledJobUpdate, user_id: UUID | None = None,
) -> ScheduledJobResponse:
    query = select(ScheduledJob).where(ScheduledJob.id == job_id)
    if user_id:
        query = query.where(ScheduledJob.user_id == user_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError("Scheduled job not found")

    wf = await db.execute(
        select(Workflow).where(Workflow.id == data.workflow_id, Workflow.deleted_at.is_(None))
    )
    workflow = wf.scalar_one_or_none()
    if not workflow:
        raise ValueError("Workflow not found")

    _remove_from_apscheduler(job_id)

    one_time_dt = None
    if data.schedule_type == "one-time" and data.one_time_date:
        from dateutil.parser import parse as dt_parse
        one_time_dt = dt_parse(data.one_time_date)
        if one_time_dt.tzinfo is None:
            user_tz = ZoneInfo(data.timezone) if data.timezone else ZoneInfo("UTC")
            one_time_dt = one_time_dt.replace(tzinfo=user_tz)

    job.job_name = data.name
    job.workflow_id = data.workflow_id
    job.user_prompt = data.user_prompt
    job.enabled = data.enabled
    job.schedule_type = data.schedule_type
    job.cron_expression = data.cron_expression if data.schedule_type == "recurring" else None
    job.one_time_date = one_time_dt
    job.timezone = data.timezone
    job.wake_mode = data.wake_mode
    job.output_format = data.output_format
    job.output_schema_text = data.output_schema
    job.delivery_methods = data.delivery_methods
    job.concurrency_policy = data.concurrency_policy
    job.retry_enabled = data.retry_enabled
    job.retry_max_attempts = data.retry_max_attempts
    job.retry_delay_seconds = data.retry_delay_seconds
    job.retry_backoff = data.retry_backoff
    job.auto_disable_after = data.auto_disable_after
    job.status = "active" if data.enabled else "paused"

    if data.schedule_type == "recurring" and data.cron_expression:
        job.next_run_at = _compute_next_run(data.cron_expression, data.timezone)
    elif data.schedule_type == "one-time" and one_time_dt:
        job.next_run_at = one_time_dt
    else:
        job.next_run_at = None

    await db.commit()
    await db.refresh(job)

    if data.enabled:
        _add_to_apscheduler(job)

    return _to_response(job, workflow.title)


async def delete_job(db: AsyncSession, job_id: UUID, user_id: UUID | None = None):
    query = select(ScheduledJob).where(ScheduledJob.id == job_id)
    if user_id:
        query = query.where(ScheduledJob.user_id == user_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError("Scheduled job not found")

    _remove_from_apscheduler(job_id)
    await db.delete(job)
    await db.commit()


async def toggle_job(
    db: AsyncSession, job_id: UUID, user_id: UUID | None = None,
) -> ScheduledJobResponse:
    query = (
        select(ScheduledJob).options(selectinload(ScheduledJob.workflow))
        .where(ScheduledJob.id == job_id)
    )
    if user_id:
        query = query.where(ScheduledJob.user_id == user_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError("Scheduled job not found")

    job.enabled = not job.enabled

    if job.enabled:
        job.status = "active"
        if job.schedule_type == "recurring" and job.cron_expression:
            job.next_run_at = _compute_next_run(job.cron_expression, job.timezone)
        _add_to_apscheduler(job)
    else:
        job.status = "paused"
        job.next_run_at = None
        _remove_from_apscheduler(job_id)

    await db.commit()
    await db.refresh(job)

    wf_title = job.workflow.title if job.workflow else "—"
    return _to_response(job, wf_title)


async def list_jobs(
    db: AsyncSession, status_filter: str | None = None, user_id: UUID | None = None,
) -> list[ScheduledJobResponse]:
    query = (
        select(ScheduledJob)
        .options(selectinload(ScheduledJob.workflow))
        .order_by(ScheduledJob.created_at.desc())
    )
    if user_id:
        query = query.where(ScheduledJob.user_id == user_id)
    if status_filter and status_filter != "all":
        query = query.where(ScheduledJob.status == status_filter)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        _to_response(j, j.workflow.title if j.workflow else "—")
        for j in jobs
    ]


async def get_job(
    db: AsyncSession, job_id: UUID, user_id: UUID | None = None,
) -> ScheduledJobResponse:
    query = (
        select(ScheduledJob).options(selectinload(ScheduledJob.workflow))
        .where(ScheduledJob.id == job_id)
    )
    if user_id:
        query = query.where(ScheduledJob.user_id == user_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError("Scheduled job not found")
    return _to_response(job, job.workflow.title if job.workflow else "—")


async def get_counts(
    db: AsyncSession, user_id: UUID | None = None,
) -> JobCountsResponse:
    query = select(ScheduledJob.status, sa_func.count()).group_by(ScheduledJob.status)
    if user_id:
        query = query.where(ScheduledJob.user_id == user_id)
    rows = await db.execute(query)
    mapping = {row[0]: row[1] for row in rows}
    return JobCountsResponse(
        active=mapping.get("active", 0),
        running=mapping.get("running", 0),
        failed=mapping.get("failed", 0),
        paused=mapping.get("paused", 0),
    )


async def get_job_history(
    db: AsyncSession, job_id: UUID, user_id: UUID | None = None,
) -> list[JobHistoryResponse]:
    query = (
        select(ScheduledJobRun)
        .where(ScheduledJobRun.scheduled_job_id == job_id)
    )
    # Verify job belongs to user
    if user_id:
        job_q = await db.execute(
            select(ScheduledJob.id).where(
                ScheduledJob.id == job_id,
                ScheduledJob.user_id == user_id,
            )
        )
        if not job_q.scalar_one_or_none():
            return []
    result = await db.execute(
        query
        .options(
            selectinload(ScheduledJobRun.workflow_run)
            .selectinload(WorkflowRun.workflow)
            .selectinload(Workflow.agent_associations)
            .selectinload(WorkflowAgent.agent),
        )
        .order_by(ScheduledJobRun.started_at.desc())
        .limit(50)
    )
    runs = result.scalars().all()

    entries: list[JobHistoryResponse] = []
    for run in runs:
        wf_run = run.workflow_run
        agents: list[str] = []
        workflow_title = "—"
        description = ""
        report_md = None

        if wf_run:
            report_md = wf_run.report_markdown
            if wf_run.workflow:
                workflow_title = wf_run.workflow.title
                agents = [
                    a.agent.name
                    for a in wf_run.workflow.agent_associations
                    if a.agent
                ]
            if run.status == "completed":
                description = f"Workflow executed successfully via {len(agents)} agent(s)"
            elif run.status == "failed":
                description = run.error_message or "Execution failed"
            else:
                description = "Execution in progress"
        else:
            description = "No run data available"

        dur = "—"
        if run.duration_seconds is not None:
            m = int(run.duration_seconds // 60)
            s = int(run.duration_seconds % 60)
            dur = f"{m}m {s}s"

        entries.append(JobHistoryResponse(
            id=run.id,
            run_date=run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "—",
            status="Completed" if run.status == "completed" else ("Failed" if run.status == "failed" else "Running"),
            duration=dur,
            workflow=workflow_title,
            agents=agents,
            description=description,
            report_markdown=report_md,
        ))

    return entries


async def get_recent_runs(
    db: AsyncSession, hours: int = 24, user_id: UUID | None = None,
) -> list:
    from datetime import timedelta
    from app.schemas.scheduled_job import RecentRunResponse

    cutoff = datetime.now(tz.utc) - timedelta(hours=hours)
    query = (
        select(ScheduledJobRun)
        .join(ScheduledJob, ScheduledJobRun.scheduled_job_id == ScheduledJob.id)
        .where(ScheduledJobRun.started_at >= cutoff)
    )
    if user_id:
        query = query.where(ScheduledJob.user_id == user_id)
    result = await db.execute(
        query
        .options(
            selectinload(ScheduledJobRun.scheduled_job),
            selectinload(ScheduledJobRun.workflow_run)
            .selectinload(WorkflowRun.workflow),
        )
        .order_by(ScheduledJobRun.started_at.desc())
        .limit(20)
    )
    runs = result.scalars().all()

    entries: list[RecentRunResponse] = []
    for run in runs:
        job_name = run.scheduled_job.job_name if run.scheduled_job else "—"
        wf_title = "—"
        report_md = None
        if run.workflow_run:
            report_md = run.workflow_run.report_markdown
            if run.workflow_run.workflow:
                wf_title = run.workflow_run.workflow.title

        status_label = {"completed": "Completed", "failed": "Failed", "running": "Running"}.get(run.status, run.status)

        entries.append(RecentRunResponse(
            id=run.id,
            job_name=job_name,
            run_date=run.started_at.strftime("%b %d, %Y") if run.started_at else "—",
            workflow=wf_title,
            status=status_label,
            report_markdown=report_md,
        ))

    return entries


# ─── Execution (called by APScheduler) ──────────────────────

async def _run_scheduled_job(job_id: UUID):
    """Triggered by APScheduler — executes the workflow for a scheduled job."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ScheduledJob).where(ScheduledJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job or not job.enabled:
            return

        if job.status == "running" and job.concurrency_policy == "skip":
            log.info("Skipping %s — already running (skip policy)", job.job_name)
            return

        job.status = "running"
        await db.commit()

    job_workflow_id = job.workflow_id
    job_user_id = job.user_id
    job_user_prompt = job.user_prompt or ""
    job_name = job.job_name
    job_retry_enabled = job.retry_enabled
    job_retry_max = job.retry_max_attempts
    job_retry_delay = job.retry_delay_seconds
    job_retry_backoff = job.retry_backoff
    job_auto_disable = job.auto_disable_after
    job_schedule_type = job.schedule_type
    job_cron = job.cron_expression
    job_tz = job.timezone

    max_attempts = job_retry_max if job_retry_enabled else 1
    attempt = 0
    success = False
    last_job_run_id = None

    while attempt < max_attempts and not success:
        attempt += 1
        t0 = time.monotonic()
        run_id = None
        job_run_id = None

        try:
            async with AsyncSessionLocal() as db:
                wf = await db.execute(
                    select(Workflow).where(Workflow.id == job_workflow_id, Workflow.deleted_at.is_(None))
                )
                if not wf.scalar_one_or_none():
                    raise ValueError("Workflow not found or deleted")

                wf_run = WorkflowRun(
                    workflow_id=job_workflow_id,
                    user_id=job_user_id,
                    user_prompt=job_user_prompt or f"Scheduled: {job_name}",
                    status="running",
                    progress=0.0,
                    started_at=datetime.now(tz.utc),
                )
                db.add(wf_run)
                await db.commit()
                run_id = wf_run.id

                sjr = ScheduledJobRun(
                    scheduled_job_id=job_id,
                    workflow_run_id=run_id,
                    status="running",
                    started_at=datetime.now(tz.utc),
                )
                db.add(sjr)
                await db.commit()
                job_run_id = sjr.id
                last_job_run_id = job_run_id

            await _execute_run(run_id, job_workflow_id, job_user_prompt)

            duration = time.monotonic() - t0

            async with AsyncSessionLocal() as db:
                wf_run_q = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
                wf_run = wf_run_q.scalar_one()

                sjr_q = await db.execute(select(ScheduledJobRun).where(ScheduledJobRun.id == job_run_id))
                sjr = sjr_q.scalar_one()
                sjr.completed_at = datetime.now(tz.utc)
                sjr.duration_seconds = duration

                if wf_run.status == "completed":
                    sjr.status = "completed"
                    success = True
                else:
                    sjr.status = "failed"
                    sjr.error_message = "Workflow did not complete successfully"

                await db.commit()

        except Exception as e:
            duration = time.monotonic() - t0
            log.error("Job %s attempt %d error: %s", job_name, attempt, e)

            if job_run_id:
                try:
                    async with AsyncSessionLocal() as db:
                        sjr_q = await db.execute(select(ScheduledJobRun).where(ScheduledJobRun.id == job_run_id))
                        sjr = sjr_q.scalar_one_or_none()
                        if sjr:
                            sjr.completed_at = datetime.now(tz.utc)
                            sjr.duration_seconds = duration
                            sjr.status = "failed"
                            sjr.error_message = str(e)[:500]
                            await db.commit()
                except Exception:
                    pass

        if attempt < max_attempts and not success:
            delay = job_retry_delay
            if job_retry_backoff == "exponential":
                delay = job_retry_delay * (2 ** (attempt - 1))
            log.info("Retrying %s in %ds (attempt %d/%d)", job_name, delay, attempt + 1, max_attempts)
            await asyncio.sleep(delay)

    # Final status update
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ScheduledJob).where(ScheduledJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return

        job.last_run_at = datetime.now(tz.utc)

        if success:
            job.consecutive_failures = 0
            job.jobs_done += 1
            job.status = "active"
        else:
            job.consecutive_failures += 1
            if job_auto_disable > 0 and job.consecutive_failures >= job_auto_disable:
                job.enabled = False
                job.status = "paused"
                _remove_from_apscheduler(job_id)
                log.warning("Job %s auto-disabled after %d consecutive failures", job_name, job.consecutive_failures)
            else:
                job.status = "failed"

        if job_schedule_type == "one-time":
            _remove_from_apscheduler(job_id)
            if not success:
                job.status = "failed"
        elif job_schedule_type == "recurring" and job_cron and job.enabled:
            job.next_run_at = _compute_next_run(job_cron, job_tz)

        await db.commit()

    log.info("Job %s finished: %s", job_name, "success" if success else "failed")
