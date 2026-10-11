from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, JsonValue


class ClientInputType(str, Enum):
    TEXT = "TEXT"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    LIVE_INTERVIEW = "LIVE_INTERVIEW"


class ClientInputCreateRequest(BaseModel):
    """Client-controlled fields accepted by the ClientInput endpoint."""

    model_config = ConfigDict(extra="forbid")

    input_type: ClientInputType
    content: str
    original_filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, JsonValue] | None = None


class ClientInputResponse(BaseModel):
    """Public ClientInput representation without MongoDB identity."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    input_type: ClientInputType
    content: str
    original_filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, JsonValue] | None = None
    created_at: datetime
