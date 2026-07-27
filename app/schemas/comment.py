from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CommentBase(BaseModel):
    content: str


class CommentCreate(CommentBase):
    task_id: UUID
    author_id: UUID


class CommentUpdate(BaseModel):
    content: str


class CommentResponse(CommentBase):
    id: UUID
    task_id: UUID
    author_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
