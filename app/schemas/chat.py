from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# ─── Request schemas ─────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    title: str = Field(default="New Research", max_length=500)


class ChatSessionUpdate(BaseModel):
    title: str = Field(max_length=500)


class SendMessageRequest(BaseModel):
    content: str = Field(max_length=10000)
    workflow_id: str | None = None


# ─── Response schemas ────────────────────────────────────────────

class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    message_type: str
    workflow_id: UUID | None = None
    run_id: UUID | None = None
    workflow_title: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    id: UUID
    title: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: str | None = None

    model_config = {"from_attributes": True}


class ChatSessionDetailResponse(BaseModel):
    id: UUID
    title: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
