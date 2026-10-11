from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from app.modules.auth.repository import UserRepository, UserRepositoryError
from app.modules.auth.schemas import UserPublicResponse
from app.modules.auth.security import (
    AccessTokenError,
    TokenConfigurationError,
    decode_access_token,
)
from app.schemas.user import User


class AuthenticationError(RuntimeError):
    """Raised for every safe public Bearer-authentication failure."""


class AuthenticationServiceError(RuntimeError):
    """Raised when authentication persistence is unavailable."""


bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserPublicResponse:
    """Validate a Bearer token and return its active public User."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication failed")

    try:
        payload = decode_access_token(credentials.credentials)
        document = repository.find_user_by_id(payload["sub"])
        if document is None:
            raise AuthenticationError("Authentication failed")
        user = User.model_validate(document)
        if not user.is_active:
            raise AuthenticationError("Authentication failed")
        return UserPublicResponse.from_user(user)
    except AuthenticationError:
        raise
    except UserRepositoryError as exc:
        raise AuthenticationServiceError(
            "Authentication service is unavailable"
        ) from exc
    except TokenConfigurationError as exc:
        raise AuthenticationServiceError(
            "Authentication service is unavailable"
        ) from exc
    except (
        AccessTokenError,
        ValidationError,
        KeyError,
    ) as exc:
        raise AuthenticationError("Authentication failed") from exc
