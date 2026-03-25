"""
Schedule service — CRUD, execution, and history for scheduled jobs.

Execution flow:
  APScheduler fires → execute_scheduled_job(job_id)
    → checks concurrency policy
    → creates a WorkflowRun via run_service.start_run()
    → records JobHistory entry
    → monitors run completion in background
    → updates job stats (jobs_done, last_run_at, consecutive_failures)
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.scheduled_job import ScheduledJob, JobHistory
from app.models.workflow import Workflow, WorkflowAgent
from app.models.run import WorkflowRun
from app.schemas.schedule import (
    ScheduledJobCreate, ScheduledJobUpdate, ScheduledJobResponse,
    ScheduledJobListResponse, ScheduledJobStats,
    JobHistoryResponse,
)
from app import scheduler as sched_engine

log = logging.getLogger("mra.schedule_service")


def _job_to_response(job: ScheduledJob) -> ScheduledJobResponse:
    wf_title = job.workflow.title if job.workflow else "—"
    return ScheduledJobResponse(
        id=job.id,
        name=job.name,
        workflow_id=job.workflow_id,
        workflow_title=wf_title,
        user_prompt=job.user_prompt,
        enabled=job.enabled,
        schedule_type=job.schedule_type,
        cron_expression=job.cron_expression,
        one_time_date=job.one_time_date,
        timezone=job.timezone,
        wake_mode=job.wake_mode,
        output_format=job.output_format,
        output_schema=job.output_schema,
        delivery_methods=job.delivery_methods or [],
        concurrency_policy=job.concurrency_policy,
        retry_enabled=job.retry_enabled,
        retry_max_attempts=job.retry_max_attempts,
        retry_delay_seconds=job.retry_delay_seconds,
        retry_backoff=job.retry_backoff,
        auto_disable_after=job.auto_disable_after,
        status=job.status,
        next_run_at=job.next_run_at,
        last_run_at=job.last_run_at,
        last_run_status=job.last_run_status,
        consecutive_failures=job.consecutive_failures,
        jobs_done=job.jobs_done,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def list_jobs(
    db: AsyncSession,
    status: str | None = None,
    search: str | None = None,
) -> ScheduledJobListResponse:
    query = (
        select(ScheduledJob)
        .options(selectinload(ScheduledJob.workflow))
        .order_by(ScheduledJob.created_at.desc())
    )
    if status:
        query = query.where(ScheduledJob.status == status)
    if search:
        query = query.where(ScheduledJob.name.ilike(f"%{search}%"))

    result = await db.execute(query)
    jobs = result.scalars().all()

    for job in jobs:
        nft = sched_engine.get_next_fire_time(job.id)
        if nft:
            job.next_run_at = nft

    return ScheduledJobListResponse(
        items=[_job_to_response(j) for j in jobs],
        total=len(jobs),
    )


async def get_job(db: AsyncSession, job_id: UUID) -> ScheduledJobResponse | None:
    result = await db.execute(
        select(ScheduledJob)
        .options(selectinload(ScheduledJob.workflow))
        .where(ScheduledJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return None

    nft = sched_engine.get_next_fire_time(job.id)
    if nft:
        job.next_run_at = nft

    return _job_to_response(job)


async def create_job(db: AsyncSession, data: ScheduledJobCreate) -> ScheduledJobResponse:
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == data.workflow_id, Workflow.deleted_at.is_(None))
    )
    workflow = wf_result.scalar_one_or_none()
    if not workflow:
        raise ValueError("Workflow not found")

    job = ScheduledJob(
        name=data.name,
        workflow_id=data.workflow_id,
        user_prompt=data.user_prompt,
        enabled=data.enabled,
        schedule_type=data.schedule_type,
        cron_expression=data.cron_expression,
        one_time_date=data.one_time_date,
        timezone=data.timezone,
        wake_mode=data.wake_mode,
        output_format=data.output.expected_output_format,
        output_schema=data.output.output_schema,
        delivery_methods=data.output.delivery_methods,
        concurrency_policy=data.failure.concurrency,
        retry_enabled=data.failure.retry.enabled,
        retry_max_attempts=data.failure.retry.max_attempts,
        retry_delay_seconds=data.failure.retry.delay_seconds,
        retry_backoff=data.failure.retry.backoff,
        auto_disable_after=data.failure.auto_disable_after,
        status="active" if data.enabled else "paused",
    )
    job.workflow = workflow
    db.add(job)
    await db.flush()

    if job.enabled:
        sched_engine.register_job(
            job.id, job.cron_expression, job.one_time_date,
            job.timezone, job.schedule_type,
        )
        nft = sched_engine.get_next_fire_time(job.id)
        if nft:
            job.next_run_at = nft

    return _job_to_response(job)


async def update_job(
    db: AsyncSession, job_id: UUID, data: ScheduledJobUpdate,
) -> ScheduledJobResponse | None:
    result = await db.execute(
        select(ScheduledJob)
        .options(selectinload(ScheduledJob.workflow))
        .where(ScheduledJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return None

    if data.workflow_id is not None:
        wf_result = await db.execute(
            select(Workflow).where(Workflow.id == data.workflow_id, Workflow.deleted_at.is_(None))
        )
        if not wf_result.scalar_one_or_none():
            raise ValueError("Workflow not found")

    schedule_changed = False
    for field in [
        "name", "workflow_id", "user_prompt", "enabled",
        "schedule_type", "cron_expression", "one_time_date",
        "timezone", "wake_mode",
    ]:
        value = getattr(data, field, None)
        if value is not None:
            if field in ("schedule_type", "cron_expression", "one_time_date", "timezone"):
                schedule_changed = True
            setattr(job, field, value)

    if data.output is not None:
        job.output_format = data.output.expected_output_format
        job.output_schema = data.output.output_schema
        job.delivery_methods = data.output.delivery_methods

    if data.failure is not None:
        job.concurrency_policy = data.failure.concurrency
        job.retry_enabled = data.failure.retry.enabled
        job.retry_max_attempts = data.failure.retry.max_attempts
        job.retry_delay_seconds = data.failure.retry.delay_seconds
        job.retry_backoff = data.failure.retry.backoff
        job.auto_disable_after = data.failure.auto_disable_after

    if data.enabled is not None:
        job.status = "active" if data.enabled else "paused"

    if job.enabled and (schedule_changed or data.enabled):
        sched_engine.register_job(
            job.id, job.cron_expression, job.one_time_date,
            job.timezone, job.schedule_type,
        )
        nft = sched_engine.get_next_fire_time(job.id)
        if nft:
            job.next_run_at = nft
    elif not job.enabled:
        sched_engine.unregister_job(job.id)
        job.next_run_at = None

    return _job_to_response(job)


async def toggle_job(db: AsyncSession, job_id: UUID) -> ScheduledJobResponse | None:
    result = await db.execute(
        select(ScheduledJob)
        .options(selectinload(ScheduledJob.workflow))
        .where(ScheduledJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return None

    job.enabled = not job.enabled
    job.status = "active" if job.enabled else "paused"

    if job.enabled:
        sched_engine.register_job(
            job.id, job.cron_expression, job.one_time_date,
            job.timezone, job.schedule_type,
        )
        nft = sched_engine.get_next_fire_time(job.id)
        if nft:
            job.next_run_at = nft
    else:
        sched_engine.unregister_job(job.id)
        job.next_run_at = None

    return _job_to_response(job)


async def delete_job(db: AsyncSession, job_id: UUID) -> bool:
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return False

    sched_engine.unregister_job(job.id)
    await db.delete(job)
    await db.commit()
    return True


async def get_stats(db: AsyncSession) -> ScheduledJobStats:
    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(ScheduledJob.status == "active").label("active"),
            func.count().filter(ScheduledJob.status == "paused").label("paused"),
            func.count().filter(ScheduledJob.status == "running").label("running"),
            func.count().filter(ScheduledJob.status == "failed").label("failed"),
        ).select_from(ScheduledJob)
    )
    row = result.one()
    return ScheduledJobStats(
        total=row.total,
        active=row.active,
        paused=row.paused,
        running=row.running,
        failed=row.failed,
    )


async def get_history(
    db: AsyncSession, job_id: UUID, limit: int = 20,
) -> list[JobHistoryResponse]:
    job_result = await db.execute(
        select(ScheduledJob)
        .options(selectinload(ScheduledJob.workflow).selectinload(Workflow.agent_associations).selectinload(WorkflowAgent.agent))
        .where(ScheduledJob.id == job_id)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        return []

    wf_title = job.workflow.title if job.workflow else "—"
    agent_names = []
    if job.workflow and job.workflow.agent_associations:
        agent_names = [
            assoc.agent.name for assoc in job.workflow.agent_associations
            if assoc.agent
        ]

    result = await db.execute(
        select(JobHistory)
        .where(JobHistory.scheduled_job_id == job_id)
        .order_by(JobHistory.run_date.desc())
        .limit(limit)
    )
    entries = result.scalars().all()

    responses = []
    for entry in entries:
        report_md = entry.report_markdown
        if not report_md and entry.workflow_run_id:
            run_result = await db.execute(
                select(WorkflowRun.report_markdown)
                .where(WorkflowRun.id == entry.workflow_run_id)
            )
            report_md = run_result.scalar_one_or_none()

        responses.append(JobHistoryResponse(
            id=entry.id,
            run_date=entry.run_date,
            status=entry.status,
            duration_seconds=entry.duration_seconds,
            workflow_title=wf_title,
            agents=agent_names,
            description=entry.description or "",
            report_markdown=report_md,
        ))

    return responses


async def execute_scheduled_job(job_id: UUID) -> None:
    """Called by APScheduler when a job fires."""
    start_time = time.monotonic()
    log.info("Executing scheduled job %s", job_id)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScheduledJob)
            .options(selectinload(ScheduledJob.workflow))
            .where(ScheduledJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            log.error("Scheduled job %s not found in DB", job_id)
            return

        if not job.enabled or job.status == "paused":
            log.info("Job %s is disabled/paused, skipping", job_id)
            return

        if job.concurrency_policy == "skip" and job.status == "running":
            log.info("Job %s already running, skipping (concurrency=skip)", job_id)
            return

        if not job.workflow or job.workflow.deleted_at is not None:
            log.warning("Workflow for job %s was deleted, disabling job", job_id)
            job.enabled = False
            job.status = "failed"
            sched_engine.unregister_job(job.id)
            await db.commit()
            return

        job.status = "running"
        await db.commit()

    history_entry = None
    run_id = None
    try:
        async with AsyncSessionLocal() as db:
            from app.services.run_service import start_run

            run_response = await start_run(db, job.workflow_id, job.user_prompt or "")
            run_id = run_response.run_id

            history_entry = JobHistory(
                scheduled_job_id=job_id,
                workflow_run_id=run_id,
                status="running",
                description=f"Executing workflow: {job.workflow.title}",
            )
            db.add(history_entry)
            await db.commit()
            history_id = history_entry.id

        await _monitor_run_completion(job_id, run_id, history_id, start_time)

    except Exception as exc:
        log.exception("Scheduled job %s failed during execution", job_id)
        await _handle_job_failure(job_id, history_entry, start_time, str(exc))


async def _monitor_run_completion(
    job_id: UUID, run_id: UUID, history_id: UUID, start_time: float,
) -> None:
    """Poll the run status until completion, then update the scheduled job."""
    poll_interval = 2.0
    max_wait = 1800

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed > max_wait:
            log.warning("Job %s run %s exceeded max wait, marking timed out", job_id, run_id)
            await _finalize_run(job_id, history_id, "failed", start_time, "Execution timed out")
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(WorkflowRun).where(WorkflowRun.id == run_id)
            )
            run = result.scalar_one_or_none()

            if not run:
                await _finalize_run(job_id, history_id, "failed", start_time, "Run record not found")
                return

            if run.status in ("completed", "failed"):
                await _finalize_run(
                    job_id, history_id,
                    "Completed" if run.status == "completed" else "Failed",
                    start_time,
                    f"Workflow finished with status: {run.status}",
                    run.report_markdown,
                )
                return

        await asyncio.sleep(poll_interval)
        poll_interval = min(poll_interval * 1.5, 10.0)


async def _finalize_run(
    job_id: UUID,
    history_id: UUID,
    status: str,
    start_time: float,
    description: str,
    report_markdown: str | None = None,
) -> None:
    duration = round(time.monotonic() - start_time, 2)
    is_failure = status.lower() == "failed"

    async with AsyncSessionLocal() as db:
        h_result = await db.execute(
            select(JobHistory).where(JobHistory.id == history_id)
        )
        history = h_result.scalar_one_or_none()
        if history:
            history.status = status
            history.duration_seconds = duration
            history.description = description
            if report_markdown:
                history.report_markdown = report_markdown

        j_result = await db.execute(
            select(ScheduledJob).where(ScheduledJob.id == job_id)
        )
        job = j_result.scalar_one_or_none()
        if job:
            job.last_run_at = datetime.now(timezone.utc)
            job.last_run_status = status.lower()
            job.jobs_done += 1

            if is_failure:
                job.consecutive_failures += 1
                if (
                    job.auto_disable_after > 0
                    and job.consecutive_failures >= job.auto_disable_after
                ):
                    job.enabled = False
                    job.status = "failed"
                    sched_engine.unregister_job(job.id)
                    log.warning(
                        "Job %s auto-disabled after %d consecutive failures",
                        job_id, job.consecutive_failures,
                    )
                else:
                    job.status = "active"

                if job.retry_enabled and job.consecutive_failures <= job.retry_max_attempts:
                    delay = job.retry_delay_seconds
                    log.info("Scheduling retry for job %s (attempt %d) in %ds", job_id, job.consecutive_failures, delay)
                    loop = asyncio.get_running_loop()
                    loop.call_later(
                        delay,
                        lambda jid=job_id: asyncio.ensure_future(execute_scheduled_job(jid)),
                    )
            else:
                job.consecutive_failures = 0
                if job.schedule_type == "one-time":
                    job.enabled = False
                    job.status = "paused"
                    sched_engine.unregister_job(job.id)
                else:
                    job.status = "active"

            nft = sched_engine.get_next_fire_time(job.id)
            if nft:
                job.next_run_at = nft

        await db.commit()

    log.info("Finalized job %s: status=%s, duration=%.1fs", job_id, status, duration)


async def _handle_job_failure(
    job_id: UUID,
    history_entry: JobHistory | None,
    start_time: float,
    error_msg: str,
) -> None:
    duration = round(time.monotonic() - start_time, 2)

    async with AsyncSessionLocal() as db:
        if history_entry and history_entry.id:
            h_result = await db.execute(
                select(JobHistory).where(JobHistory.id == history_entry.id)
            )
            h = h_result.scalar_one_or_none()
            if h:
                h.status = "Failed"
                h.duration_seconds = duration
                h.description = f"Error: {error_msg[:500]}"
        else:
            h = JobHistory(
                scheduled_job_id=job_id,
                status="Failed",
                duration_seconds=duration,
                description=f"Error: {error_msg[:500]}",
            )
            db.add(h)

        j_result = await db.execute(
            select(ScheduledJob).where(ScheduledJob.id == job_id)
        )
        job = j_result.scalar_one_or_none()
        if job:
            job.last_run_at = datetime.now(timezone.utc)
            job.last_run_status = "failed"
            job.consecutive_failures += 1
            job.jobs_done += 1

            if (
                job.auto_disable_after > 0
                and job.consecutive_failures >= job.auto_disable_after
            ):
                job.enabled = False
                job.status = "failed"
                sched_engine.unregister_job(job.id)
            else:
                job.status = "active"

        await db.commit()
