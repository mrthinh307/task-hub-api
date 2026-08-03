from uuid import UUID

from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.comment import Comment
from app.models.task import Task
from app.models.user import User
from app.repositories.comment_repository import CommentCreateData, CommentRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.comment import CommentCreate


class CommentService:
    """Application service orchestrating task comment mutations."""

    def __init__(
        self,
        comment_repo: CommentRepository,
        task_repo: TaskRepository,
        project_repo: ProjectRepository,
        workspace_repo: WorkspaceRepository,
    ) -> None:
        self.comment_repo = comment_repo
        self.task_repo = task_repo
        self.project_repo = project_repo
        self.workspace_repo = workspace_repo

    async def _get_accessible_task(
        self,
        task_id: UUID,
        user_id: UUID,
        *,
        hidden_entity: str = "Task",
        hidden_entity_id: UUID | None = None,
    ) -> Task:
        task = await self.task_repo.get_by_id(task_id)
        entity_id = hidden_entity_id or task_id
        if task is None:
            raise EntityNotFoundError(hidden_entity, entity_id)

        project = await self.project_repo.get_by_id(task.project_id)
        if project is None:
            raise EntityNotFoundError(hidden_entity, entity_id)

        access = await self.workspace_repo.get_accessible_by_id(
            project.workspace_id,
            user_id,
        )
        if access is None:
            raise EntityNotFoundError(hidden_entity, entity_id)
        return task

    async def add_comment(
        self,
        task_id: UUID,
        current_user: User,
        payload: CommentCreate,
    ) -> Comment:
        await self._get_accessible_task(task_id, current_user.id)
        return await self.comment_repo.create(
            CommentCreateData(
                task_id=task_id,
                author_id=current_user.id,
                content=payload.content,
            )
        )

    async def delete_comment(
        self,
        comment_id: UUID,
        current_user: User,
    ) -> None:
        comment = await self.comment_repo.get_by_id(comment_id)
        if comment is None:
            raise EntityNotFoundError("Comment", comment_id)

        await self._get_accessible_task(
            comment.task_id,
            current_user.id,
            hidden_entity="Comment",
            hidden_entity_id=comment_id,
        )
        if comment.author_id != current_user.id:
            raise PermissionDeniedError(
                message="Only the comment author can delete this comment",
                details={"comment_id": str(comment_id)},
            )

        deleted = await self.comment_repo.delete(comment_id)
        if not deleted:
            raise EntityNotFoundError("Comment", comment_id)
