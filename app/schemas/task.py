from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assignee_id: UUID | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Task title must not be blank")
        return normalized

    @field_validator("due_date")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Task due date must include a timezone")
        return value


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    assignee_id: UUID | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Task title must not be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Task title must not be blank")
        return normalized

    @field_validator("status")
    @classmethod
    def reject_null_status(cls, value: TaskStatus | None) -> TaskStatus:
        if value is None:
            raise ValueError("Task status must not be null")
        return value

    @field_validator("priority")
    @classmethod
    def reject_null_priority(cls, value: TaskPriority | None) -> TaskPriority:
        if value is None:
            raise ValueError("Task priority must not be null")
        return value

    @field_validator("due_date")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Task due date must include a timezone")
        return value

    @model_validator(mode="after")
    def require_update_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one task field must be provided")
        return self


class TaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    assignee_id: UUID | None
    created_by: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskPageResponse(BaseModel):
    items: list[TaskResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class TaskFilters(BaseModel):
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: UUID | None = None
    unassigned: bool = False
    created_by: UUID | None = None
    due_from: datetime | None = None
    due_to: datetime | None = None

    @field_validator("due_from", "due_to")
    @classmethod
    def require_filter_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Task due-date filters must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_filter_combinations(self) -> Self:
        if self.assignee_id is not None and self.unassigned:
            raise ValueError(
                "assignee_id and unassigned=true cannot be used together"
            )
        if (
            self.due_from is not None
            and self.due_to is not None
            and self.due_from > self.due_to
        ):
            raise ValueError("due_from must be earlier than or equal to due_to")
        return self
