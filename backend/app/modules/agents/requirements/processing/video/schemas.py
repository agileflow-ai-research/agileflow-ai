from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.requirements.processing.audio.schemas import (
    TranscriptSegment,
    TranscriptionConfiguration,
)
from app.modules.agents.requirements.processing.schemas import (
    DocumentProcessingStatus,
)


VideoProcessingStatus = DocumentProcessingStatus


class VideoProcessingErrorCode(StrEnum):
    VIDEO_UNSUPPORTED_FORMAT = "VIDEO_UNSUPPORTED_FORMAT"
    VIDEO_EMPTY = "VIDEO_EMPTY"
    VIDEO_FILE_MISSING = "VIDEO_FILE_MISSING"
    VIDEO_CHECKSUM_MISMATCH = "VIDEO_CHECKSUM_MISMATCH"
    VIDEO_UNREADABLE = "VIDEO_UNREADABLE"
    VIDEO_AUDIO_EXTRACTION_FAILED = "VIDEO_AUDIO_EXTRACTION_FAILED"
    VIDEO_NO_AUDIO_TRACK = "VIDEO_NO_AUDIO_TRACK"
    VIDEO_TRANSCRIPTION_FAILED = "VIDEO_TRANSCRIPTION_FAILED"
    VIDEO_PROCESSING_FAILED = "VIDEO_PROCESSING_FAILED"


class VideoProcessingError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: VideoProcessingErrorCode
    message: str = Field(min_length=1, max_length=500)


class VideoExtractionConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=100)
    provider_version: str = Field(min_length=1, max_length=100)
    executable: str = Field(min_length=1, max_length=255)
    timeout_seconds: float = Field(gt=0)
    sample_rate_hz: int = Field(gt=0)
    channels: int = Field(gt=0)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class VideoProcessingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^VID-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    processor_version: str = Field(pattern=r"^\d+$")
    extraction: VideoExtractionConfiguration
    transcription: TranscriptionConfiguration
    status: VideoProcessingStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: VideoProcessingError | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "VideoProcessingRecord":
        if self.status is VideoProcessingStatus.READY:
            if self.started_at is not None or self.completed_at is not None or self.error:
                raise ValueError("READY processing cannot contain execution data")
        elif self.status is VideoProcessingStatus.PROCESSING:
            if self.started_at is None or self.completed_at is not None or self.error:
                raise ValueError("PROCESSING requires only started_at")
        elif self.status is VideoProcessingStatus.COMPLETED:
            if self.started_at is None or self.completed_at is None or self.error:
                raise ValueError("COMPLETED requires timestamps and no error")
        elif self.started_at is None or self.completed_at is None or self.error is None:
            raise ValueError("FAILED requires timestamps and an error")
        return self


class VideoProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^VID-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=255)
    processor_version: str = Field(pattern=r"^\d+$")
    extraction: VideoExtractionConfiguration
    transcription: TranscriptionConfiguration
    transcript: str = Field(min_length=1)
    segments: list[TranscriptSegment]
    detected_language: str | None = Field(default=None, min_length=1, max_length=50)
    language_probability: float | None = Field(default=None, ge=0, le=1)
    processed_at: datetime
