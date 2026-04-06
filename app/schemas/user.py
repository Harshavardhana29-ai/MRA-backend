from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
from typing import Optional
from uuid import UUID


class UserResponse(BaseModel):
    id: UUID
    sso_id: str
    ntid: Optional[str] = None
    email: str
    display_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    admin_id: Optional[UUID] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "admin_id")
    def serialize_uuid(self, v: UUID | None) -> str | None:
        return str(v) if v else None

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


# ─── User Management Schemas (Super Admin / Admin) ───────────

class UserCreateRequest(BaseModel):
    ntid: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=255)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = Field(..., pattern=r"^(admin|assistant)$")
    admin_id: Optional[UUID] = None


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern=r"^(super_admin|admin|assistant|user)$")
    admin_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
