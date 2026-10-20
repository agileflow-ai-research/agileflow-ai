from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.requirements.processing.schemas import (
    DocumentProcessingStatus,
)


AudioProcessingStatus = DocumentProcessingStatus


class AudioProcessingErrorCode(StrEnum):
    TRANSCRIPTION_PROVIDER_NOT_CONFIGURED = "TRANSCRIPTION_PROVIDER_NOT_CONFIGURED"
    AUDIO_UNREADABLE = "AUDIO_UNREADABLE"
    AUDIO_TRANSCRIPTION_FAILED = "AUDIO_TRANSCRIPTION_FAILED"
    NO_USABLE_TRANSCRIPT = "NO_USABLE_TRANSCRIPT"
    SOURCE_CHECKSUM_MISMATCH = "SOURCE_CHECKSUM_MISMATCH"


class AudioProcessingError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: AudioProcessingErrorCode
    message: str = Field(min_length=1, max_length=500)


class TranscriptionConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=100)
    provider_version: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    device: str = Field(min_length=1, max_length=100)
    compute_type: str = Field(min_length=1, max_length=100)
    language: str | None = Field(default=None, min_length=1, max_length=50)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str

    @model_validator(mode="after")
    def validate_timestamps(self) -> "TranscriptSegment":
        if self.end_seconds < self.start_seconds:
            raise ValueError("Segment end must not precede its start")
        return self


class AudioProcessingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^AUD-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    processor_version: str = Field(pattern=r"^\d+$")
    transcription: TranscriptionConfiguration
    status: AudioProcessingStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: AudioProcessingError | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "AudioProcessingRecord":
        if self.status is AudioProcessingStatus.READY:
            if self.started_at is not None or self.completed_at is not None or self.error:
                raise ValueError("READY processing cannot contain execution data")
        elif self.status is AudioProcessingStatus.PROCESSING:
            if self.started_at is None or self.completed_at is not None or self.error:
                raise ValueError("PROCESSING requires only started_at")
        elif self.status is AudioProcessingStatus.COMPLETED:
            if self.started_at is None or self.completed_at is None or self.error:
                raise ValueError("COMPLETED requires timestamps and no error")
        elif self.started_at is None or self.completed_at is None or self.error is None:
            raise ValueError("FAILED requires timestamps and an error")
        return self


class AudioProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^AUD-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    processor_version: str = Field(pattern=r"^\d+$")
    transcription: TranscriptionConfiguration
    transcript: str = Field(min_length=1)
    segments: list[TranscriptSegment]
    detected_language: str | None = Field(default=None, min_length=1, max_length=50)
    language_probability: float | None = Field(default=None, ge=0, le=1)
    processed_at: datetime
