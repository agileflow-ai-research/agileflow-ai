from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RequirementSourceType(StrEnum):
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"


class RequirementSourceStatus(StrEnum):
    READY = "READY"


class RequirementSourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1)
    extension: str = Field(pattern=r"^\.[a-z0-9]+$")
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: RequirementSourceStatus = RequirementSourceStatus.READY
    created_at: datetime

