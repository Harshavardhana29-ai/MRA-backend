from pydantic import BaseModel, field_serializer
from datetime import datetime
from typing import Optional
from uuid import UUID


class UserResponse(BaseModel):
    id: UUID
    sso_id: str
    email: str
    display_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("id")
    def serialize_id(self, v: UUID) -> str:
        return str(v)

    model_config = {"from_attributes": True}


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class SessionInfo(BaseModel):
    user: UserResponse
    session_id: str
    expires_at: datetime
