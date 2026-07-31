"""add task project pagination index

Revision ID: 1e23b067add5
Revises: acb5e6d9c941
Create Date: 2026-07-31 04:21:56.028245

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1e23b067add5"
down_revision: str | None = "acb5e6d9c941"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tasks_project_created_at_id",
        "tasks",
        ["project_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_project_created_at_id", table_name="tasks")
