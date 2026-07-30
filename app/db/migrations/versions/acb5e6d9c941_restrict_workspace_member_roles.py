"""restrict workspace member roles

Revision ID: acb5e6d9c941
Revises: 4aca36ab8c7f
Create Date: 2026-07-31 00:04:54.801388

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "acb5e6d9c941"
down_revision: str | None = "4aca36ab8c7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAME = "workspacememberrole"
TEMP_ENUM_NAME = "workspacememberrole_new"


def _replace_workspace_member_role_enum(
    current_values: tuple[str, ...],
    new_values: tuple[str, ...],
) -> None:
    bind = op.get_bind()
    current_enum = postgresql.ENUM(
        *current_values,
        name=ENUM_NAME,
        create_type=False,
    )
    replacement_enum = postgresql.ENUM(
        *new_values,
        name=TEMP_ENUM_NAME,
    )
    replacement_enum.create(bind, checkfirst=False)
    op.alter_column(
        "workspace_members",
        "role",
        existing_type=current_enum,
        type_=replacement_enum,
        existing_nullable=False,
        postgresql_using=f"role::text::{TEMP_ENUM_NAME}",
    )
    current_enum.drop(bind, checkfirst=False)
    op.execute(sa.text(f'ALTER TYPE "{TEMP_ENUM_NAME}" RENAME TO "{ENUM_NAME}"'))


def upgrade() -> None:
    owner_members = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM workspace_members WHERE role::text = 'OWNER'")
        )
        .scalar_one()
    )
    if owner_members:
        raise RuntimeError(
            "Cannot remove OWNER from workspace member roles while "
            "workspace_members rows still use it"
        )

    _replace_workspace_member_role_enum(
        ("OWNER", "EDITOR", "VIEWER"),
        ("EDITOR", "VIEWER"),
    )


def downgrade() -> None:
    _replace_workspace_member_role_enum(
        ("EDITOR", "VIEWER"),
        ("OWNER", "EDITOR", "VIEWER"),
    )
