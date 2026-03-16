from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# --- Request schemas ---

class RunWorkflowRequest(BaseModel):
    user_prompt: str = Field(default="", max_length=5000)


# --- Response schemas ---

class RunLogResponse(BaseModel):
    time: str
    message: str
    type: str  # info, success, error, warning

    model_config = {"from_attributes": True}


class WorkflowRunResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    user_prompt: str | None = None
    status: str
    progress: float
    report_markdown: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    logs: list[RunLogResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RunStartResponse(BaseModel):
    run_id: UUID
    status: str


class RunStatusResponse(BaseModel):
    id: UUID
    status: str
    progress: float
    log_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
