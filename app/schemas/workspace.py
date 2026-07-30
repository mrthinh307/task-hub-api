from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import WorkspaceAccessRole, WorkspaceMemberRole


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Workspace name must not be blank")
        return normalized


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceDetailResponse(WorkspaceResponse):
    role: WorkspaceAccessRole


class WorkspaceMemberCreate(BaseModel):
    email: EmailStr
    role: WorkspaceMemberRole

    model_config = ConfigDict(extra="forbid")


class WorkspaceMemberUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    user: WorkspaceMemberUserResponse
    role: WorkspaceMemberRole
    created_at: datetime
    updated_at: datetime
