from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Comment content must not be blank")
        return normalized


class CommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    author_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
