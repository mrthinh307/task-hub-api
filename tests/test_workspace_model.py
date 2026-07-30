from typing import cast

from sqlalchemy import Table, UniqueConstraint

from app.core.enums import WorkspaceAccessRole, WorkspaceMemberRole
from app.models.workspace import WorkspaceMember


def test_workspace_member_is_unique_per_workspace_and_user() -> None:
    table = cast(Table, WorkspaceMember.__table__)
    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert unique_constraints["uq_workspace_members_workspace_user"] == (
        "workspace_id",
        "user_id",
    )


def test_workspace_member_and_access_roles_are_separated() -> None:
    assert set(WorkspaceMemberRole) == {
        WorkspaceMemberRole.EDITOR,
        WorkspaceMemberRole.VIEWER,
    }
    assert set(WorkspaceAccessRole) == {
        WorkspaceAccessRole.OWNER,
        WorkspaceAccessRole.EDITOR,
        WorkspaceAccessRole.VIEWER,
    }
