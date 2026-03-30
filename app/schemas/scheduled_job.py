from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ScheduledJobCreate(BaseModel):
    name: str = Field(..., max_length=500)
    user_prompt: str = ""
    workflow_id: UUID
    enabled: bool = True
    schedule_type: str = "recurring"
    cron_expression: str = "0 * * * *"
    one_time_date: str | None = None
    timezone: str = "UTC"
    wake_mode: str = "next-heartbeat"
    output_format: str = "markdown"
    output_schema: str = ""
    delivery_methods: list[str] = Field(default_factory=lambda: ["internal-log"])
    concurrency_policy: str = "skip"
    retry_enabled: bool = False
    retry_max_attempts: int = 3
    retry_delay_seconds: int = 60
    retry_backoff: str = "fixed"
    auto_disable_after: int = 0


class ScheduledJobUpdate(ScheduledJobCreate):
    pass


class ScheduledJobResponse(BaseModel):
    id: UUID
    job_name: str
    type: str
    workflow_id: UUID
    workflow_title: str
    schedule_time: str
    next_run: str
    last_run: str
    status: str
    notify: bool = False
    enabled: bool
    jobs_done: int
    user_prompt: str | None = None
    cron_expression: str | None = None
    timezone: str = "UTC"
    wake_mode: str = "next-heartbeat"
    output_format: str = "markdown"
    output_schema: str | None = None
    delivery_methods: list[str] = Field(default_factory=lambda: ["internal-log"])
    failure_behavior: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class JobHistoryResponse(BaseModel):
    id: UUID
    run_date: str
    status: str
    duration: str
    workflow: str
    agents: list[str] = Field(default_factory=list)
    description: str
    report_markdown: str | None = None

    model_config = {"from_attributes": True}


class JobCountsResponse(BaseModel):
    active: int = 0
    running: int = 0
    failed: int = 0
    paused: int = 0


class RecentRunResponse(BaseModel):
    id: UUID
    job_name: str
    run_date: str
    workflow: str
    status: str
    report_markdown: str | None = None

    model_config = {"from_attributes": True}
