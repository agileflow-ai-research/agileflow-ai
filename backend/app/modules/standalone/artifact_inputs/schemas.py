from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArtifactSourceType(StrEnum):
    """Uploadable standalone source types. TEXT is entered directly and is never uploaded."""

    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"


class ArtifactProcessingStatus(StrEnum):
    # Documents move from PENDING_EXTRACTION to the extraction result status.
    PENDING_EXTRACTION = "PENDING_EXTRACTION"
    # Images have no semantic analysis path in this codebase and remain pending.
    PENDING_ANALYSIS = "PENDING_ANALYSIS"


PENDING_STATUS_BY_SOURCE = {
    ArtifactSourceType.DOCUMENT: ArtifactProcessingStatus.PENDING_EXTRACTION,
    ArtifactSourceType.IMAGE: ArtifactProcessingStatus.PENDING_ANALYSIS,
}


class StoredArtifactUploadMetadata(BaseModel):
    """Server-side upload record. Internal: it carries the sha256 and extension used for integrity checks."""

    model_config = ConfigDict(extra="forbid")

    upload_id: str = Field(pattern=r"^SAUP-[0-9a-f]{32}$")
    source_type: ArtifactSourceType
    artifact_type: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=200)
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1)
    extension: str = Field(pattern=r"^\.[a-z0-9]+$")
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ArtifactUploadResponse(BaseModel):
    """Client-visible upload metadata. Never includes storage paths, extensions, or hashes."""

    model_config = ConfigDict(extra="forbid")

    upload_id: str
    source_type: ArtifactSourceType
    artifact_type: str
    label: str | None
    original_filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    processing_status: ArtifactProcessingStatus


class ArtifactUploadDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str
    deleted: bool


class ArtifactExtractionWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ArtifactExtractionResponse(BaseModel):
    """Trusted extraction result for a DOCUMENT upload.

    extracted_text is produced server-side. The client must use it instead of parsing files.
    status is the shared extraction vocabulary: SUCCESS, PARTIAL, or FAILED.
    usable_as_context is true for SUCCESS or PARTIAL with non-empty text. PARTIAL stays visible
    as partial, so clients must keep the partial-extraction warning.
    """

    model_config = ConfigDict(extra="forbid")

    upload_id: str
    artifact_type: str
    original_filename: str
    document_type: str
    status: str
    usable_as_context: bool
    extracted_text: str
    warnings: list[ArtifactExtractionWarning]
    extractor_version: str
    extracted_at: datetime
