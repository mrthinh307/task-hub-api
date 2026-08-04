from functools import partial
from uuid import UUID

from app.cache.task_list_cache import TaskListCache
from app.core.background import BackgroundTaskDispatcher
from app.core.enums import ProjectStatus, TaskStatus, WorkspaceAccessRole
from app.core.exceptions import (
    ArchivedProjectError,
    ArchivedTaskDeleteError,
    ArchivedTaskUpdateError,
    EntityNotFoundError,
    InactiveTaskAssigneeError,
    PermissionDeniedError,
    TaskAssigneeNotWorkspaceMemberError,
)
from app.db.post_commit import PostCommitActions
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.notifications import AssignmentNotifier, TaskAssignmentNotification
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import (
    TaskCreateData,
    TaskFilterData,
    TaskRepository,
    TaskUpdateData,
)
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceAccess, WorkspaceRepository
from app.schemas.task import (
    TaskCreate,
    TaskFilters,
    TaskPageResponse,
    TaskResponse,
    TaskUpdate,
)


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        project_repo: ProjectRepository,
        workspace_repo: WorkspaceRepository,
        user_repo: UserRepository,
        task_cache: TaskListCache,
        post_commit: PostCommitActions,
        assignment_notifier: AssignmentNotifier,
        background_dispatcher: BackgroundTaskDispatcher,
    ) -> None:
        self.task_repo = task_repo
        self.project_repo = project_repo
        self.workspace_repo = workspace_repo
        self.user_repo = user_repo
        self.task_cache = task_cache
        self.post_commit = post_commit
        self.assignment_notifier = assignment_notifier
        self.background_dispatcher = background_dispatcher

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

    async def _get_task_access(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> tuple[Task, Project, WorkspaceAccess]:
        task = await self.task_repo.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError("Task", task_id)

        try:
            project, access = await self._get_project_access(
                task.project_id,
                user_id,
            )
        except EntityNotFoundError:
            raise EntityNotFoundError("Task", task_id) from None
        return task, project, access

    async def _validate_assignee(
        self,
        project: Project,
        current_user: User,
        assignee_id: UUID | None,
    ) -> User | None:
        if assignee_id is None:
            return None
        if assignee_id == current_user.id:
            return current_user

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
                project.id,
                project.workspace_id,
                assignee_id,
            )
        return assignee

    async def _dispatch_assignment_notification(
        self,
        notification: TaskAssignmentNotification,
    ) -> None:
        self.background_dispatcher.submit(
            partial(
                self.assignment_notifier.notify_task_assigned,
                notification,
            )
        )

    def _register_assignment_notification(
        self,
        *,
        task: Task,
        project: Project,
        assignee: User | None,
        assigned_by: User,
    ) -> None:
        if assignee is None or assignee.id == assigned_by.id:
            return

        notification = TaskAssignmentNotification(
            task_id=task.id,
            task_title=task.title,
            project_name=project.name,
            assignee_email=assignee.email,
            assignee_name=assignee.full_name,
            assigned_by_name=assigned_by.full_name,
            due_date=task.due_date,
        )
        self.post_commit.add(
            partial(self._dispatch_assignment_notification, notification)
        )

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
        assignee = await self._validate_assignee(
            project,
            current_user,
            assignee_id,
        )

        task = await self.task_repo.create(
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
        self.post_commit.add(partial(self.task_cache.invalidate_project, project_id))
        self._register_assignment_notification(
            task=task,
            project=project,
            assignee=assignee,
            assigned_by=current_user,
        )
        return task

    async def update_task(
        self,
        task_id: UUID,
        current_user: User,
        payload: TaskUpdate,
    ) -> Task:
        task, project, access = await self._get_task_access(
            task_id,
            current_user.id,
        )
        if access.role not in {
            WorkspaceAccessRole.OWNER,
            WorkspaceAccessRole.EDITOR,
        }:
            raise PermissionDeniedError(
                message="Viewer role cannot update tasks in this project",
                details={
                    "project_id": str(project.id),
                    "required_roles": [
                        WorkspaceAccessRole.OWNER,
                        WorkspaceAccessRole.EDITOR,
                    ],
                },
            )
        if project.status is ProjectStatus.ARCHIVED:
            raise ArchivedTaskUpdateError(project.id, task_id)

        update_data = payload.model_dump(exclude_unset=True)
        previous_assignee_id = task.assignee_id
        assignee: User | None = None
        if "assignee_id" in update_data:
            assignee = await self._validate_assignee(
                project,
                current_user,
                payload.assignee_id,
            )

        updated_task = await self.task_repo.update(
            task,
            TaskUpdateData(**update_data),
        )
        self.post_commit.add(partial(self.task_cache.invalidate_project, project.id))
        if updated_task.assignee_id != previous_assignee_id:
            self._register_assignment_notification(
                task=updated_task,
                project=project,
                assignee=assignee,
                assigned_by=current_user,
            )
        return updated_task

    async def delete_task(
        self,
        task_id: UUID,
        current_user: User,
    ) -> None:
        _, project, access = await self._get_task_access(
            task_id,
            current_user.id,
        )
        if access.role not in {
            WorkspaceAccessRole.OWNER,
            WorkspaceAccessRole.EDITOR,
        }:
            raise PermissionDeniedError(
                message="Viewer role cannot delete tasks in this project",
                details={
                    "project_id": str(project.id),
                    "required_roles": [
                        WorkspaceAccessRole.OWNER,
                        WorkspaceAccessRole.EDITOR,
                    ],
                },
            )
        if project.status is ProjectStatus.ARCHIVED:
            raise ArchivedTaskDeleteError(project.id, task_id)

        deleted = await self.task_repo.delete(task_id)
        if not deleted:
            raise EntityNotFoundError("Task", task_id)
        self.post_commit.add(partial(self.task_cache.invalidate_project, project.id))

    async def list_tasks(
        self,
        project_id: UUID,
        current_user: User,
        *,
        page: int,
        page_size: int,
        filters: TaskFilters,
    ) -> TaskPageResponse:
        await self._get_project_access(project_id, current_user.id)

        cache_lookup = await self.task_cache.get(
            project_id,
            page=page,
            page_size=page_size,
            filters=filters,
        )
        if cache_lookup is not None and cache_lookup.response is not None:
            return cache_lookup.response

        result = await self.task_repo.list_by_project(
            project_id,
            filters=TaskFilterData(
                status=filters.status,
                priority=filters.priority,
                assignee_id=filters.assignee_id,
                unassigned=filters.unassigned,
                created_by=filters.created_by,
                due_from=filters.due_from,
                due_to=filters.due_to,
            ),
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        response = TaskPageResponse(
            items=[TaskResponse.model_validate(task) for task in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
            total_pages=(result.total + page_size - 1) // page_size,
        )
        if cache_lookup is not None:
            await self.task_cache.set(
                project_id,
                page=page,
                page_size=page_size,
                filters=filters,
                version=cache_lookup.version,
                response=response,
            )
        return response
