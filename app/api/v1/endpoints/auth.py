from fastapi import APIRouter, Depends, Request, Response, status

from app.api.cookies import delete_auth_cookies, set_auth_cookies
from app.api.dependencies import get_auth_service
from app.core.config import settings
from app.core.exceptions import InvalidTokenError
from app.schemas.auth import AuthUserResponse, LoginRequest, RegisterRequest
from app.schemas.errors import ErrorResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=AuthUserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def register(
    payload: RegisterRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    result = await service.register(payload)
    set_auth_cookies(response, result.tokens)
    return result.user


@router.post(
    "/login",
    response_model=AuthUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def login(
    payload: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    result = await service.login(payload)
    set_auth_cookies(response, result.tokens)
    return result.user


@router.post(
    "/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    },
)
async def refresh(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise InvalidTokenError

    tokens = await service.refresh(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_auth_cookies(response, tokens)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    await service.logout(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    delete_auth_cookies(response)
    return response
