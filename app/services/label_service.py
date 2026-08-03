from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.enums import ProjectStatus, WorkspaceAccessRole
from app.core.exceptions import (
    ArchivedLabelMutationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.models.label import Label
from app.models.project import Project
from app.models.user import User
from app.repositories.label_repository import (
    LabelCreateData,
    LabelRepository,
    LabelUpdateData,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.workspace_repository import WorkspaceAccess, WorkspaceRepository
from app.schemas.label import LabelCreate, LabelUpdate


def _is_unique_violation(exc: IntegrityError) -> bool:
    """Return whether PostgreSQL reported a unique-constraint violation."""
    return getattr(exc.orig, "sqlstate", None) == "23505"


class LabelService:
    def __init__(
        self,
        label_repo: LabelRepository,
        project_repo: ProjectRepository,
        workspace_repo: WorkspaceRepository,
    ) -> None:
        self.label_repo = label_repo
        self.project_repo = project_repo
        self.workspace_repo = workspace_repo

    async def _get_project_access(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> tuple[Project, WorkspaceAccess]:
        project = await self.project_repo.get_by_id(project_id)
        if project is None:
            raise EntityNotFoundError("Project", project_id)

        access = await self.workspace_repo.get_accessible_by_id(
            project.workspace_id,
            user_id,
        )
        if access is None:
            raise EntityNotFoundError("Project", project_id)
        return project, access

    async def _get_label_access(
        self,
        label_id: UUID,
        user_id: UUID,
    ) -> tuple[Label, Project, WorkspaceAccess]:
        label = await self.label_repo.get_by_id(label_id)
        if label is None:
            raise EntityNotFoundError("Label", label_id)

        try:
            project, access = await self._get_project_access(
                label.project_id,
                user_id,
            )
        except EntityNotFoundError:
            raise EntityNotFoundError("Label", label_id) from None
        return label, project, access

    @staticmethod
    def _require_writer(
        access: WorkspaceAccess,
        project_id: UUID,
        action: str,
    ) -> None:
        if access.role in {
            WorkspaceAccessRole.OWNER,
            WorkspaceAccessRole.EDITOR,
        }:
            return
        raise PermissionDeniedError(
            message=f"Viewer role cannot {action} labels in this project",
            details={
                "project_id": str(project_id),
                "required_roles": [
                    WorkspaceAccessRole.OWNER,
                    WorkspaceAccessRole.EDITOR,
                ],
            },
        )

    @staticmethod
    def _require_active_project(project: Project, action: str) -> None:
        if project.status is ProjectStatus.ARCHIVED:
            raise ArchivedLabelMutationError(project.id, action)

    @staticmethod
    def _duplicate_name_error(name: str) -> EntityAlreadyExistsError:
        return EntityAlreadyExistsError("Label", "name", name)

    async def create_label(
        self,
        project_id: UUID,
        current_user: User,
        payload: LabelCreate,
    ) -> Label:
        project, access = await self._get_project_access(
            project_id,
            current_user.id,
        )
        self._require_writer(access, project_id, "create")
        self._require_active_project(project, "created")

        existing = await self.label_repo.get_by_project_and_name(
            project_id,
            payload.name,
        )
        if existing is not None:
            raise self._duplicate_name_error(payload.name)

        try:
            return await self.label_repo.create(
                LabelCreateData(
                    project_id=project_id,
                    name=payload.name,
                    color=payload.color,
                )
            )
        except IntegrityError as exc:
            if not _is_unique_violation(exc):
                raise
            raise self._duplicate_name_error(payload.name) from exc

    async def list_labels(
        self,
        project_id: UUID,
        current_user: User,
    ) -> Sequence[Label]:
        await self._get_project_access(project_id, current_user.id)
        return await self.label_repo.list_by_project(project_id)

    async def get_label(
        self,
        label_id: UUID,
        current_user: User,
    ) -> Label:
        label, _, _ = await self._get_label_access(label_id, current_user.id)
        return label

    async def update_label(
        self,
        label_id: UUID,
        current_user: User,
        payload: LabelUpdate,
    ) -> Label:
        label, project, access = await self._get_label_access(
            label_id,
            current_user.id,
        )
        self._require_writer(access, project.id, "update")
        self._require_active_project(project, "updated")

        update_data = payload.model_dump(exclude_unset=True)
        name = update_data.get("name")
        if isinstance(name, str) and name != label.name:
            existing = await self.label_repo.get_by_project_and_name(
                project.id,
                name,
            )
            if existing is not None and existing.id != label.id:
                raise self._duplicate_name_error(name)

        try:
            return await self.label_repo.update(
                label,
                LabelUpdateData(**update_data),
            )
        except IntegrityError as exc:
            if not _is_unique_violation(exc):
                raise
            assert isinstance(name, str)
            raise self._duplicate_name_error(name) from exc

    async def delete_label(
        self,
        label_id: UUID,
        current_user: User,
    ) -> None:
        label, project, access = await self._get_label_access(
            label_id,
            current_user.id,
        )
        self._require_writer(access, project.id, "delete")
        self._require_active_project(project, "deleted")

        deleted = await self.label_repo.delete(label.id)
        if not deleted:
            raise EntityNotFoundError("Label", label_id)
