import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.task import Task


class Label(Base):
    __tablename__ = "labels"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(50), default="#6B7280", nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="labels")
    tasks: Mapped[list["Task"]] = relationship(
        "Task", secondary="task_labels", back_populates="labels"
    )
