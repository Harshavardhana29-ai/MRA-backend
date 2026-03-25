from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class OutputConfig(BaseModel):
    expected_output_format: str = "markdown"
    output_schema: str | None = None
    delivery_methods: list[str] = Field(default_factory=lambda: ["internal-log"])


class RetryConfig(BaseModel):
    enabled: bool = False
    max_attempts: int = 3
    delay_seconds: int = 60
    backoff: str = "fixed"


class FailureConfig(BaseModel):
    concurrency: str = "skip"
    retry: RetryConfig = Field(default_factory=RetryConfig)
    auto_disable_after: int = 0


class ScheduledJobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    workflow_id: UUID
    user_prompt: str | None = None
    enabled: bool = True
    schedule_type: str = "recurring"
    cron_expression: str | None = None
    one_time_date: datetime | None = None
    timezone: str = "UTC"
    wake_mode: str = "next-heartbeat"
    output: OutputConfig = Field(default_factory=OutputConfig)
    failure: FailureConfig = Field(default_factory=FailureConfig)


class ScheduledJobUpdate(BaseModel):
    name: str | None = None
    workflow_id: UUID | None = None
    user_prompt: str | None = None
    enabled: bool | None = None
    schedule_type: str | None = None
    cron_expression: str | None = None
    one_time_date: datetime | None = None
    timezone: str | None = None
    wake_mode: str | None = None
    output: OutputConfig | None = None
    failure: FailureConfig | None = None


class ScheduledJobResponse(BaseModel):
    id: UUID
    name: str
    workflow_id: UUID
    workflow_title: str
    user_prompt: str | None = None
    enabled: bool
    schedule_type: str
    cron_expression: str | None = None
    one_time_date: datetime | None = None
    timezone: str
    wake_mode: str
    output_format: str
    output_schema: str | None = None
    delivery_methods: list[str]
    concurrency_policy: str
    retry_enabled: bool
    retry_max_attempts: int
    retry_delay_seconds: int
    retry_backoff: str
    auto_disable_after: int
    status: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    consecutive_failures: int
    jobs_done: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduledJobListResponse(BaseModel):
    items: list[ScheduledJobResponse]
    total: int


class ScheduledJobStats(BaseModel):
    total: int
    active: int
    paused: int
    running: int
    failed: int


class JobHistoryResponse(BaseModel):
    id: UUID
    run_date: datetime
    status: str
    duration_seconds: float | None = None
    workflow_title: str
    agents: list[str]
    description: str
    report_markdown: str | None = None
