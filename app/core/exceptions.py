from typing import Any, ClassVar

type ErrorDetails = dict[str, Any] | list[dict[str, Any]] | None


class ApplicationError(Exception):
    """Base class for expected application-level failures."""

    default_message: ClassVar[str] = "An application error occurred"

    def __init__(
        self,
        *,
        message: str | None = None,
        details: ErrorDetails = None,
    ) -> None:
        self.message = message or type(self).default_message
        self.details = details
        super().__init__(self.message)


class ResourceNotFoundError(ApplicationError):
    default_message = "The requested resource was not found"


class ConflictError(ApplicationError):
    default_message = "The request conflicts with the current resource state"


class AuthenticationError(ApplicationError):
    default_message = "Authentication failed"


class PermissionDeniedError(ApplicationError):
    default_message = "Permission denied"


class EntityNotFoundError(ResourceNotFoundError):
    def __init__(self, entity_name: str, entity_id: Any) -> None:
        super().__init__(
            message=f"{entity_name} with id {entity_id} not found",
            details={"entity": entity_name, "id": str(entity_id)},
        )


class EntityAlreadyExistsError(ConflictError):
    def __init__(self, entity_name: str, field: str, value: str) -> None:
        super().__init__(
            message=f"{entity_name} with {field} '{value}' already exists",
            details={"entity": entity_name, "field": field, "value": value},
        )


class WorkspaceInviteeNotFoundError(ResourceNotFoundError):
    def __init__(self, email: str) -> None:
        super().__init__(
            message=f"User with email '{email}' not found",
            details={"entity": "User", "field": "email", "value": email},
        )


class WorkspaceMemberAlreadyExistsError(ConflictError):
    def __init__(self, workspace_id: Any, user_id: Any) -> None:
        super().__init__(
            message="User is already a member of this workspace",
            details={
                "workspace_id": str(workspace_id),
                "user_id": str(user_id),
            },
        )


class WorkspaceOwnerMembershipError(ConflictError):
    def __init__(self, workspace_id: Any, user_id: Any) -> None:
        super().__init__(
            message="Workspace owner cannot also be added as a member",
            details={
                "workspace_id": str(workspace_id),
                "user_id": str(user_id),
            },
        )


class InactiveWorkspaceMemberError(ConflictError):
    def __init__(self, user_id: Any) -> None:
        super().__init__(
            message="Inactive users cannot be added to a workspace",
            details={"user_id": str(user_id)},
        )


class EmailAlreadyRegisteredError(ConflictError):
    """Raised when registration uses an existing email address."""

    default_message = "Email is already registered"


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials cannot be authenticated."""

    default_message = "Invalid email or password"


class InvalidCurrentPasswordError(AuthenticationError):
    """Raised when profile password confirmation fails."""

    default_message = "Current password is incorrect"


class PasswordUnchangedError(ConflictError):
    """Raised when a password change reuses the current password."""

    default_message = "New password must differ from current password"


class InactiveUserError(PermissionDeniedError):
    """Raised when authentication is attempted for an inactive user."""

    default_message = "User account is inactive"


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT or its persisted refresh session is invalid."""

    default_message = "Invalid or expired authentication token"


class ExpiredTokenError(InvalidTokenError):
    """Raised when a JWT has expired."""
