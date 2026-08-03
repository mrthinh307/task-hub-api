from functools import partial
from uuid import UUID

from app.cache.task_list_cache import TaskListCache
from app.core.enums import ProjectStatus, WorkspaceAccessRole
from app.core.exceptions import (
    ArchivedTaskUpdateError,
    EntityNotFoundError,
    PermissionDeniedError,
    TaskLabelProjectMismatchError,
)
from app.db.post_commit import PostCommitActions
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_label_repository import TaskLabelRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.workspace_repository import WorkspaceAccess, WorkspaceRepository


class TaskLabelService:
    """Application service orchestrating Task-Label assignments."""

    def __init__(
        self,
        task_label_repo: TaskLabelRepository,
        task_repo: TaskRepository,
        label_repo: LabelRepository,
        project_repo: ProjectRepository,
        workspace_repo: WorkspaceRepository,
        task_cache: TaskListCache,
        post_commit: PostCommitActions,
    ) -> None:
        self.task_label_repo = task_label_repo
        self.task_repo = task_repo
        self.label_repo = label_repo
        self.project_repo = project_repo
        self.workspace_repo = workspace_repo
        self.task_cache = task_cache
        self.post_commit = post_commit

    async def _get_task_access(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> tuple[Task, Project, WorkspaceAccess]:
        task = await self.task_repo.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError("Task", task_id)

        project = await self.project_repo.get_by_id(task.project_id)
        if project is None:
            raise EntityNotFoundError("Task", task_id)

        access = await self.workspace_repo.get_accessible_by_id(
            project.workspace_id,
            user_id,
        )
        if access is None:
            raise EntityNotFoundError("Task", task_id)
        return task, project, access

    @staticmethod
    def _require_task_writer(
        access: WorkspaceAccess,
        project_id: UUID,
    ) -> None:
        if access.role in {
            WorkspaceAccessRole.OWNER,
            WorkspaceAccessRole.EDITOR,
        }:
            return
        raise PermissionDeniedError(
            message="Viewer role cannot update labels on tasks in this project",
            details={
                "project_id": str(project_id),
                "required_roles": [
                    WorkspaceAccessRole.OWNER,
                    WorkspaceAccessRole.EDITOR,
                ],
            },
        )

    async def _validate_assignment(
        self,
        task_id: UUID,
        label_id: UUID,
        current_user: User,
    ) -> tuple[Task, Project]:
        task, project, access = await self._get_task_access(
            task_id,
            current_user.id,
        )
        self._require_task_writer(access, project.id)
        if project.status is ProjectStatus.ARCHIVED:
            raise ArchivedTaskUpdateError(project.id, task_id)

        label = await self.label_repo.get_by_id(label_id)
        if label is None:
            raise EntityNotFoundError("Label", label_id)
        if label.project_id != task.project_id:
            raise TaskLabelProjectMismatchError(
                task.id,
                label.id,
                task.project_id,
                label.project_id,
            )
        return task, project

    async def assign_label(
        self,
        task_id: UUID,
        label_id: UUID,
        current_user: User,
    ) -> None:
        _, project = await self._validate_assignment(
            task_id,
            label_id,
            current_user,
        )
        await self.task_label_repo.add(task_id, label_id)
        self.post_commit.add(partial(self.task_cache.invalidate_project, project.id))

    async def remove_label(
        self,
        task_id: UUID,
        label_id: UUID,
        current_user: User,
    ) -> None:
        _, project = await self._validate_assignment(
            task_id,
            label_id,
            current_user,
        )
        await self.task_label_repo.remove(task_id, label_id)
        self.post_commit.add(partial(self.task_cache.invalidate_project, project.id))
