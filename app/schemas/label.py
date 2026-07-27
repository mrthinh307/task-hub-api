from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LabelBase(BaseModel):
    name: str
    color: str = "#6B7280"


class LabelCreate(LabelBase):
    project_id: UUID


class LabelUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class LabelResponse(LabelBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
