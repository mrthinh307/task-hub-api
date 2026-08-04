import redis.asyncio as aioredis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.task_list_cache import RedisTaskListCache
from app.core.background import BackgroundTaskDispatcher
from app.core.config import settings
from app.core.enums import TokenType
from app.core.exceptions import InactiveUserError, InvalidTokenError
from app.core.security import decode_token
from app.db.post_commit import PostCommitActions, get_post_commit_actions
from app.db.session import get_db, get_redis
from app.models.user import User
from app.notifications import (
    AssignmentNotifier,
    GmailAssignmentNotifier,
    NoOpAssignmentNotifier,
)
from app.repositories.auth_repository import AuthRepository
from app.repositories.comment_repository import CommentRepository
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.refresh_session_repository import RefreshSessionRepository
from app.repositories.task_label_repository import TaskLabelRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_member_repository import WorkspaceMemberRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.auth_service import AuthService
from app.services.comment_service import CommentService
from app.services.label_service import LabelService
from app.services.project_service import ProjectService
from app.services.task_label_service import TaskLabelService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workspace_membership_service import WorkspaceMembershipService
from app.services.workspace_service import WorkspaceService


def get_auth_repository(
    session: AsyncSession = Depends(get_db),
) -> AuthRepository:
    return AuthRepository(session)


def get_refresh_session_repository(
    session: AsyncSession = Depends(get_db),
) -> RefreshSessionRepository:
    return RefreshSessionRepository(session)


def get_auth_service(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    refresh_session_repo: RefreshSessionRepository = Depends(
        get_refresh_session_repository
    ),
) -> AuthService:
    return AuthService(auth_repo, refresh_session_repo)


def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> UserRepository:
    return UserRepository(session)


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(user_repo)


def get_workspace_repository(
    session: AsyncSession = Depends(get_db),
) -> WorkspaceRepository:
    return WorkspaceRepository(session)


def get_project_repository(
    session: AsyncSession = Depends(get_db),
) -> ProjectRepository:
    return ProjectRepository(session)


def get_label_repository(
    session: AsyncSession = Depends(get_db),
) -> LabelRepository:
    return LabelRepository(session)


def get_task_repository(
    session: AsyncSession = Depends(get_db),
) -> TaskRepository:
    return TaskRepository(session)


def get_comment_repository(
    session: AsyncSession = Depends(get_db),
) -> CommentRepository:
    return CommentRepository(session)


def get_task_label_repository(
    session: AsyncSession = Depends(get_db),
) -> TaskLabelRepository:
    return TaskLabelRepository(session)


def get_task_list_cache(
    redis: aioredis.Redis = Depends(get_redis),
) -> RedisTaskListCache:
    return RedisTaskListCache(
        redis,
        ttl_seconds=settings.TASK_LIST_CACHE_TTL_SECONDS,
    )


def get_assignment_notifier() -> AssignmentNotifier:
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return NoOpAssignmentNotifier()

    username = settings.GMAIL_SMTP_USERNAME
    app_password = settings.GMAIL_SMTP_APP_PASSWORD
    if username is None or app_password is None:
        raise RuntimeError("Gmail SMTP settings are incomplete")
    return GmailAssignmentNotifier(
        username=str(username),
        app_password=app_password.get_secret_value(),
        from_name=settings.EMAIL_FROM_NAME,
        timeout_seconds=settings.EMAIL_SMTP_TIMEOUT_SECONDS,
    )


def get_background_task_dispatcher(request: Request) -> BackgroundTaskDispatcher:
    return request.app.state.background_dispatcher


def get_project_service(
    project_repo: ProjectRepository = Depends(get_project_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> ProjectService:
    return ProjectService(project_repo, workspace_repo)


def get_label_service(
    label_repo: LabelRepository = Depends(get_label_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> LabelService:
    return LabelService(label_repo, project_repo, workspace_repo)


def get_task_service(
    task_repo: TaskRepository = Depends(get_task_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    task_cache: RedisTaskListCache = Depends(get_task_list_cache),
    post_commit: PostCommitActions = Depends(get_post_commit_actions),
    assignment_notifier: AssignmentNotifier = Depends(get_assignment_notifier),
    background_dispatcher: BackgroundTaskDispatcher = Depends(
        get_background_task_dispatcher
    ),
) -> TaskService:
    return TaskService(
        task_repo,
        project_repo,
        workspace_repo,
        user_repo,
        task_cache,
        post_commit,
        assignment_notifier,
        background_dispatcher,
    )


def get_comment_service(
    comment_repo: CommentRepository = Depends(get_comment_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> CommentService:
    return CommentService(
        comment_repo,
        task_repo,
        project_repo,
        workspace_repo,
    )


def get_task_label_service(
    task_label_repo: TaskLabelRepository = Depends(get_task_label_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    label_repo: LabelRepository = Depends(get_label_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    task_cache: RedisTaskListCache = Depends(get_task_list_cache),
    post_commit: PostCommitActions = Depends(get_post_commit_actions),
) -> TaskLabelService:
    return TaskLabelService(
        task_label_repo,
        task_repo,
        label_repo,
        project_repo,
        workspace_repo,
        task_cache,
        post_commit,
    )


def get_workspace_service(
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> WorkspaceService:
    return WorkspaceService(workspace_repo)


def get_workspace_member_repository(
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMemberRepository:
    return WorkspaceMemberRepository(session)


def get_workspace_membership_service(
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    member_repo: WorkspaceMemberRepository = Depends(
        get_workspace_member_repository
    ),
    user_repo: UserRepository = Depends(get_user_repository),
) -> WorkspaceMembershipService:
    return WorkspaceMembershipService(workspace_repo, member_repo, user_repo)


async def get_current_user(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    access_token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not access_token:
        raise InvalidTokenError

    decoded = decode_token(access_token, TokenType.ACCESS)
    user = await user_repo.get_by_id(decoded.user_id)
    if user is None:
        raise InvalidTokenError
    if not user.is_active:
        raise InactiveUserError
    return user
