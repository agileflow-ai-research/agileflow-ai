from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.common.id_generator import validate_id


class User(BaseModel):
    """Internal persisted User model; password_hash is never an API response."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    name: str
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return validate_id(value, "USR")
