from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.agents.implementation.extraction.schemas import (
    DocumentType,
    ExtractionStatus,
)
from app.modules.agents.implementation.schemas import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
    ImplementationOutputCode,
)


UploadId = Annotated[str, Field(pattern=r"^A3UP-[0-9a-f]{32}$")]


class ReadinessStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


class FindingSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class HumanResolutionDecision(StrEnum):
    ADAPT_TO_SUPPORTED_STACK = "ADAPT_TO_SUPPORTED_STACK"


class ReadinessTextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_id: str = Field(pattern=r"^LOCAL-[A-Za-z0-9_-]{1,80}$")
    artifact_type: ImplementationArtifactType
    label: str | None = Field(default=None, max_length=200)
    content: str = Field(max_length=200_000)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must be non-empty")
        return normalized


class HumanResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(pattern=r"^RF-[0-9a-f]{16}$")
    decision: HumanResolutionDecision
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ReadinessEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_outputs: list[ImplementationOutputCode] = Field(max_length=8)
    text_inputs: list[ReadinessTextInput] = Field(default_factory=list, max_length=50)
    document_upload_ids: list[UploadId] = Field(default_factory=list, max_length=100)
    image_upload_ids: list[UploadId] = Field(default_factory=list, max_length=100)
    human_resolutions: list[HumanResolutionRequest] = Field(
        default_factory=list, max_length=100
    )
    input_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    @field_validator("document_upload_ids", "image_upload_ids")
    @classmethod
    def validate_upload_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("upload IDs must be unique")
        return values

    @model_validator(mode="after")
    def validate_request_limits(self) -> "ReadinessEvaluationRequest":
        if len(self.selected_outputs) != len(set(self.selected_outputs)):
            raise ValueError("selected_outputs must not contain duplicates")
        if len({item.input_id for item in self.text_inputs}) != len(self.text_inputs):
            raise ValueError("text input IDs must be unique")
        if sum(len(item.content) for item in self.text_inputs) > 1_000_000:
            raise ValueError("manual text input exceeds the total size limit")
        if set(self.document_upload_ids) & set(self.image_upload_ids):
            raise ValueError("an upload cannot be both DOCUMENT and IMAGE")
        if len(self.document_upload_ids) + len(self.image_upload_ids) > 100:
            raise ValueError("no more than 100 upload references are allowed")
        if self.human_resolutions and self.input_fingerprint is None:
            raise ValueError("input_fingerprint is required with human resolutions")
        return self


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: ImplementationInputSourceType
    artifact_type: ImplementationArtifactType
    label: str | None = None
    original_filename: str | None = None


class NormalizedBlockProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_index: int = Field(ge=1)
    block_type: Literal["HEADING", "PARAGRAPH", "TABLE"]
    heading_level: int | None = Field(default=None, ge=1, le=9)


class NormalizedProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str | None = None
    original_filename: str | None = None
    source_sha256: str | None = None
    document_type: DocumentType | None = None
    page_numbers: list[int] = Field(default_factory=list)
    blocks: list[NormalizedBlockProvenance] = Field(default_factory=list)


class NormalizedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: Literal[
        ImplementationInputSourceType.TEXT,
        ImplementationInputSourceType.DOCUMENT,
    ]
    artifact_type: ImplementationArtifactType
    label: str | None = None
    text_content: str
    structured_content: Any = None
    extraction_status: ExtractionStatus | None = None
    extraction_version: str | None = None
    provenance: NormalizedProvenance


class ArtifactManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: Literal["REQUIREMENTS", "DESIGN", "IMPLEMENTATION", "TESTS", "VISUAL"]
    source_id: str
    source_type: ImplementationInputSourceType
    artifact_type: ImplementationArtifactType
    label: str | None = None
    availability: Literal["AVAILABLE", "PARTIAL", "FAILED", "NOT_EXTRACTED", "PENDING_ANALYSIS"]


class ReadinessFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(pattern=r"^RF-[0-9a-f]{16}$")
    code: str
    severity: FindingSeverity
    title: str
    message: str
    affected_outputs: list[ImplementationOutputCode] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    requires_human_decision: bool = False
    allowed_resolutions: list[HumanResolutionDecision] = Field(default_factory=list)
    category: str | None = None
    provided_value: str | None = None
    supported_value: str | None = None
    resolved: bool = False
    resolution: HumanResolutionRequest | None = None


class ReadinessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    errors: int = Field(ge=0)
    warnings: int = Field(ge=0)
    info: int = Field(ge=0)


class ReadinessCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: bool
    design: bool
    implementation: bool
    tests: bool
    visual_context_pending: bool


class OutputReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: ImplementationOutputCode
    ready: bool
    findings: list[str]


class EffectivePrototypeStack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontend: Literal["React + Vite"] = "React + Vite"
    styling: Literal["Plain CSS"] = "Plain CSS"
    backend: Literal["Node.js + Express.js"] = "Node.js + Express.js"
    database: Literal["MySQL"] = "MySQL"
    language: Literal["JavaScript"] = "JavaScript"
    api_style: Literal["REST"] = "REST"


class ReadinessEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReadinessStatus
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary: ReadinessSummary
    coverage: ReadinessCoverage
    selected_outputs: list[ImplementationOutputCode]
    output_readiness: list[OutputReadiness]
    effective_stack: EffectivePrototypeStack
    artifact_manifest: list[ArtifactManifestEntry]
    findings: list[ReadinessFinding]
    human_resolutions: list[HumanResolutionRequest]
    evaluated_at: datetime
