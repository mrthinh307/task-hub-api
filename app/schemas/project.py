from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import ProjectStatus


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name must not be blank")
        return normalized


class ProjectResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
