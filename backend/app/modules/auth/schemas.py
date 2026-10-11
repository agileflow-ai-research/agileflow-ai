from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.user import User


class UserRegisterRequest(BaseModel):
    """Client-controlled registration fields."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def require_email_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Email must be provided")
        return value


class UserPublicResponse(BaseModel):
    """Safe public User representation without password or MongoDB identity."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    name: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserPublicResponse":
        return cls(
            user_id=user.user_id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class UserLoginRequest(BaseModel):
    """Credentials accepted by the login endpoint."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def require_email_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Email must be provided")
        return value


class AccessTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
