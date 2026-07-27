from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.comment_repository import CommentRepository
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.comment_service import CommentService
from app.services.label_service import LabelService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService


# Repository Dependencies
def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> UserRepository:
    return UserRepository(session)


def get_workspace_repository(
    session: AsyncSession = Depends(get_db),
) -> WorkspaceRepository:
    return WorkspaceRepository(session)


def get_project_repository(
    session: AsyncSession = Depends(get_db),
) -> ProjectRepository:
    return ProjectRepository(session)


def get_task_repository(
    session: AsyncSession = Depends(get_db),
) -> TaskRepository:
    return TaskRepository(session)


def get_label_repository(
    session: AsyncSession = Depends(get_db),
) -> LabelRepository:
    return LabelRepository(session)


def get_comment_repository(
    session: AsyncSession = Depends(get_db),
) -> CommentRepository:
    return CommentRepository(session)


# Service Dependencies
def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repo)


def get_workspace_service(
    repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> WorkspaceService:
    return WorkspaceService(repo)


def get_project_service(
    repo: ProjectRepository = Depends(get_project_repository),
) -> ProjectService:
    return ProjectService(repo)


def get_task_service(
    repo: TaskRepository = Depends(get_task_repository),
) -> TaskService:
    return TaskService(repo)


def get_label_service(
    repo: LabelRepository = Depends(get_label_repository),
) -> LabelService:
    return LabelService(repo)


def get_comment_service(
    repo: CommentRepository = Depends(get_comment_repository),
) -> CommentService:
    return CommentService(repo)
