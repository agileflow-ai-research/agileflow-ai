from collections.abc import Callable
from datetime import datetime, timezone

from argon2.exceptions import HashingError
from pydantic import ValidationError

from app.common.id_generator import generate_id
from app.modules.auth.repository import UserRepository, UserRepositoryError
from app.modules.auth.schemas import (
    AccessTokenResponse,
    UserLoginRequest,
    UserPublicResponse,
    UserRegisterRequest,
)
from app.modules.auth.security import (
    TokenConfigurationError,
    create_access_token,
    hash_password,
    verify_password,
)
from app.schemas.user import User


class DuplicateEmailError(ValueError):
    """Raised when a normalized email already belongs to a User."""


class UserServiceError(RuntimeError):
    """Raised when registration cannot be completed safely."""


class InvalidCredentialsError(ValueError):
    """Raised for every public login authentication failure."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserService:
    """Business rules for User registration and login."""

    def __init__(
        self,
        repository: UserRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def register_user(self, request: UserRegisterRequest) -> UserPublicResponse:
        email = normalize_email(request.email)
        try:
            if self._repository.find_user_by_email(email) is not None:
                raise DuplicateEmailError(email)

            now = self._clock()
            user = User(
                user_id=generate_id(
                    "USR",
                    self._repository.next_user_sequence(),
                ),
                name=request.name,
                email=email,
                password_hash=hash_password(request.password),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            persisted_user = User.model_validate(
                self._repository.create_user(user)
            )
            return UserPublicResponse.from_user(persisted_user)
        except DuplicateEmailError:
            raise
        except (UserRepositoryError, ValidationError, HashingError) as exc:
            raise UserServiceError("User registration failed") from exc

    def login_user(self, request: UserLoginRequest) -> AccessTokenResponse:
        email = normalize_email(request.email)
        try:
            document = self._repository.find_user_by_email(email)
            if document is None:
                raise InvalidCredentialsError("Invalid credentials")

            user = User.model_validate(document)
            if not user.is_active or not verify_password(
                request.password,
                user.password_hash,
            ):
                raise InvalidCredentialsError("Invalid credentials")

            return AccessTokenResponse(
                access_token=create_access_token(user.user_id),
            )
        except InvalidCredentialsError:
            raise
        except (
            UserRepositoryError,
            ValidationError,
            TokenConfigurationError,
        ) as exc:
            raise UserServiceError("User login failed") from exc
