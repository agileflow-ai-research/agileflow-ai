from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.auth.dependencies import get_current_user, get_user_repository
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import (
    AccessTokenResponse,
    UserLoginRequest,
    UserPublicResponse,
    UserRegisterRequest,
)
from app.modules.auth.service import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserService,
    UserServiceError,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def get_user_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repository)


UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
CurrentUserDependency = Annotated[UserPublicResponse, Depends(get_current_user)]


def _error_response(
    status_code: int,
    message: str,
    field: str,
    detail: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=detail)],
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


@router.post(
    "/register",
    response_model=SuccessResponse[UserPublicResponse],
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: UserRegisterRequest,
    service: UserServiceDependency,
) -> SuccessResponse[UserPublicResponse] | JSONResponse:
    try:
        user = service.register_user(request)
    except DuplicateEmailError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "Registration failed",
            "email",
            "Email is already registered",
        )
    except UserServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Registration failed",
            "database",
            "User storage is unavailable",
        )
    return SuccessResponse(
        message="User registered successfully",
        data=user,
    )


@router.post(
    "/login",
    response_model=SuccessResponse[AccessTokenResponse],
)
def login_user(
    request: UserLoginRequest,
    service: UserServiceDependency,
) -> SuccessResponse[AccessTokenResponse] | JSONResponse:
    try:
        access_token = service.login_user(request)
    except InvalidCredentialsError:
        return _error_response(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid credentials",
            "credentials",
            "Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UserServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Login failed",
            "authentication",
            "Authentication service is unavailable",
        )
    response = SuccessResponse(
        message="Login successful",
        data=access_token,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/me", response_model=SuccessResponse[UserPublicResponse])
def get_authenticated_user(
    current_user: CurrentUserDependency,
) -> SuccessResponse[UserPublicResponse]:
    return SuccessResponse(
        message="Authenticated user retrieved successfully",
        data=current_user,
    )
