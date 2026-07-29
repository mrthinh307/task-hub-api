from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.cookies import delete_auth_cookies
from app.core.exceptions import (
    ApplicationError,
    AuthenticationError,
    ConflictError,
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.core.logging import logger
from app.schemas.errors import ErrorContent, ErrorResponse, ValidationErrorDetail

ERROR_STATUS_MAP: tuple[tuple[type[ApplicationError], int], ...] = (
    (ResourceNotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (AuthenticationError, status.HTTP_401_UNAUTHORIZED),
    (PermissionDeniedError, status.HTTP_403_FORBIDDEN),
)


def _error_response(
    *,
    status_code: int,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorContent(code=status_code, message=message, details=details)
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


def _status_for_application_error(exc: ApplicationError) -> int:
    for error_type, status_code in ERROR_STATUS_MAP:
        if isinstance(exc, error_type):
            return status_code
    return status.HTTP_500_INTERNAL_SERVER_ERROR


async def application_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    status_code = _status_for_application_error(exc)
    return _error_response(
        status_code=status_code,
        message=exc.message,
        details=exc.details,
    )


async def auth_session_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, (InvalidTokenError, InactiveUserError))
    response = await application_error_handler(request, exc)
    delete_auth_cookies(response)
    return response


async def request_validation_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        ValidationErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            message=error["msg"],
            type=error["type"],
        )
        for error in exc.errors()
    ]
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message="Request validation failed",
        details=details,
    )


async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    try:
        http_status = HTTPStatus(exc.status_code)
        default_message = http_status.phrase
    except ValueError:
        default_message = "HTTP request failed"

    if isinstance(exc.detail, str):
        message = exc.detail
        details = None
    else:
        message = default_message
        details = exc.detail

    return _error_response(
        status_code=exc.status_code,
        message=message,
        details=details,
        headers=exc.headers,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled exception while processing %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(InvalidTokenError, auth_session_error_handler)
    app.add_exception_handler(InactiveUserError, auth_session_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
