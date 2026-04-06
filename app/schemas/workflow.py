from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# --- Request schemas ---

class WorkflowCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    topic: str = Field(..., min_length=1, max_length=100)
    status: str = Field(default="Draft")
    source_selection_mode: str = Field(default="topic")  # topic, both, individual, prompt_only
    selected_topics: list[str] = Field(default_factory=list)
    data_source_ids: list[UUID] = Field(default_factory=list)
    agent_ids: list[UUID] = Field(default_factory=list)
    is_public: bool = False


class WorkflowUpdate(BaseModel):
    title: str | None = None
    topic: str | None = None
    status: str | None = None
    source_selection_mode: str | None = None
    selected_topics: list[str] | None = None
    data_source_ids: list[UUID] | None = None
    agent_ids: list[UUID] | None = None
    is_public: bool | None = None


# --- Response schemas ---

class WorkflowDataSourceResponse(BaseModel):
    id: UUID
    title: str
    topic: str

    model_config = {"from_attributes": True}


class WorkflowAgentResponse(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: UUID
    title: str
    topic: str
    status: str
    source_selection_mode: str
    selected_topics: list[str]
    is_public: bool = False
    created_at: datetime
    updated_at: datetime
    data_sources: list[WorkflowDataSourceResponse] = Field(default_factory=list)
    agents: list[WorkflowAgentResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int


class WorkflowStats(BaseModel):
    total: int
    agents_used: int
