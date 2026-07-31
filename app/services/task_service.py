from uuid import UUID

from app.core.enums import (
    ProjectStatus,
    TaskStatus,
    WorkspaceAccessRole,
)
from app.core.exceptions import (
    ArchivedProjectError,
    EntityNotFoundError,
    InactiveTaskAssigneeError,
    PermissionDeniedError,
    TaskAssigneeNotWorkspaceMemberError,
)
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import (
    TaskCreateData,
    TaskRepository,
)
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceAccess, WorkspaceRepository
from app.schemas.task import TaskCreate, TaskPageResponse, TaskResponse


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        project_repo: ProjectRepository,
        workspace_repo: WorkspaceRepository,
        user_repo: UserRepository,
    ) -> None:
        self.task_repo = task_repo
        self.project_repo = project_repo
        self.workspace_repo = workspace_repo
        self.user_repo = user_repo

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

    async def create_task(
        self,
        project_id: UUID,
        current_user: User,
        payload: TaskCreate,
    ) -> Task:
        project, access = await self._get_project_access(
            project_id,
            current_user.id,
        )
        if access.role not in {
            WorkspaceAccessRole.OWNER,
            WorkspaceAccessRole.EDITOR,
        }:
            raise PermissionDeniedError(
                message="Viewer role cannot create tasks in this project",
                details={
                    "project_id": str(project_id),
                    "required_roles": [
                        WorkspaceAccessRole.OWNER,
                        WorkspaceAccessRole.EDITOR,
                    ],
                },
            )
        if project.status is ProjectStatus.ARCHIVED:
            raise ArchivedProjectError(project_id)

        assignee_id = payload.assignee_id
        if assignee_id is not None and assignee_id != current_user.id:
            assignee = await self.user_repo.get_by_id(assignee_id)
            if assignee is None:
                raise EntityNotFoundError("User", assignee_id)
            if not assignee.is_active:
                raise InactiveTaskAssigneeError(assignee_id)

            assignee_access = await self.workspace_repo.get_accessible_by_id(
                project.workspace_id,
                assignee_id,
            )
            if assignee_access is None:
                raise TaskAssigneeNotWorkspaceMemberError(
                    project_id,
                    project.workspace_id,
                    assignee_id,
                )

        return await self.task_repo.create(
            TaskCreateData(
                project_id=project_id,
                assignee_id=assignee_id,
                created_by=current_user.id,
                title=payload.title,
                description=payload.description,
                status=TaskStatus.TODO,
                priority=payload.priority,
                due_date=payload.due_date,
            )
        )

    async def list_tasks(
        self,
        project_id: UUID,
        current_user: User,
        *,
        page: int,
        page_size: int,
    ) -> TaskPageResponse:
        await self._get_project_access(project_id, current_user.id)

        result = await self.task_repo.list_by_project(
            project_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return TaskPageResponse(
            items=[TaskResponse.model_validate(task) for task in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
            total_pages=(result.total + page_size - 1) // page_size,
        )
