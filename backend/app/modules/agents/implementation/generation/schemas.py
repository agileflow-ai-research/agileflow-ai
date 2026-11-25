from datetime import datetime
from enum import StrEnum
import hashlib
import re
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

from app.common.status import AgentRunStatus
from app.modules.agents.implementation.contracts.enums import (
    ImplementationOutputCode,
)
from app.modules.agents.implementation.preparation.consolidation.schemas import (
    ProjectSpecificationItem,
    TrustedProjectSpecification,
)
from app.modules.agents.implementation.preparation.readiness.trusted.schemas import (
    TrustedReadinessSnapshot,
    TrustedStackAdaptation,
)
from app.modules.agents.implementation.runs.schemas import (
    DeliverySnapshot,
    FinalApprovalSnapshot,
)

from .validation import validate_relative_output_path


class FrozenStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ApprovedImplementationStack(FrozenStrictModel):
    """Frozen schema-v1 effective stack copied from trusted readiness."""

    frontend: str
    styling: str
    backend: str
    database: str
    language: str
    api_style: str


class ApprovedGenerationContext(FrozenStrictModel):
    """Detached, read-only view of one immutable approved run snapshot."""

    run_id: str
    agent_project_id: str
    owner_user_id: str
    created_at: datetime
    operational_status: AgentRunStatus
    snapshot_schema_version: str

    trusted_project_specification: TrustedProjectSpecification
    trusted_readiness: TrustedReadinessSnapshot
    selected_outputs: tuple[ImplementationOutputCode, ...]
    effective_implementation_stack: ApprovedImplementationStack
    requested_stack_items: tuple[ProjectSpecificationItem, ...] = ()
    stack_adaptation_decision: TrustedStackAdaptation | None = None

    approval: FinalApprovalSnapshot
    delivery_snapshot: DeliverySnapshot
    traceability_root_refs: tuple[str, ...]

    project_specification_source_set_digest: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    project_specification_decision_digest: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    readiness_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class RelativeOutputPath(RootModel[str]):
    """Canonical POSIX-style path relative to a server-owned run workspace."""

    model_config = ConfigDict(frozen=True)

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        return validate_relative_output_path(value)


class GenerationStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GenerationPlanStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class PlannedFileCategory(StrEnum):
    PROJECT_STRUCTURE = "PROJECT_STRUCTURE"
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    DATABASE = "DATABASE"
    API = "API"
    CONFIGURATION = "CONFIGURATION"
    CONTAINER = "CONTAINER"


class PlanningEvidenceKind(StrEnum):
    STRUCTURAL = "STRUCTURAL"
    TRUSTED_SPECIFICATION = "TRUSTED_SPECIFICATION"


class PlanningFindingSeverity(StrEnum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"


class GenerationPlanIdentity(FrozenStrictModel):
    generation_plan_id: str = Field(pattern=r"^GPL-[0-9a-f]{32}$")
    agent_project_id: str
    run_id: str


class GenerationWorkspaceIdentity(FrozenStrictModel):
    """Project/run isolation key below a server-controlled workspace root."""

    agent_project_id: str
    run_id: str


class SelectedOutputMapping(FrozenStrictModel):
    selected_output: ImplementationOutputCode
    planned_file_ids: tuple[str, ...] = ()


class PlannedFileEntry(FrozenStrictModel):
    planned_file_id: str = Field(pattern=r"^GPF-[0-9a-f]{32}$")
    relative_output_path: RelativeOutputPath
    responsibility: str = Field(min_length=1, max_length=500)
    output_codes: tuple[ImplementationOutputCode, ...] = Field(min_length=1)
    dependency_file_ids: tuple[str, ...] = ()
    supporting_specification_item_ids: tuple[str, ...] = ()
    file_category: PlannedFileCategory
    evidence_kind: PlanningEvidenceKind
    generation_order: int = Field(ge=1)
    status: GenerationStatus = GenerationStatus.NOT_STARTED

    @field_validator("responsibility")
    @classmethod
    def responsibility_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("responsibility must not be blank")
        return value

    @model_validator(mode="after")
    def collections_must_be_unique(self):
        for field_name in (
            "output_codes",
            "dependency_file_ids",
            "supporting_specification_item_ids",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        if (
            self.evidence_kind is PlanningEvidenceKind.TRUSTED_SPECIFICATION
            and not self.supporting_specification_item_ids
        ):
            raise ValueError(
                "trusted-specification files require specification item references"
            )
        return self


class PlannedNonFileDeliverable(FrozenStrictModel):
    deliverable_id: str = Field(pattern=r"^GPD-[0-9a-f]{32}$")
    output_code: ImplementationOutputCode
    responsibility: str = Field(min_length=1, max_length=500)
    supporting_specification_item_ids: tuple[str, ...] = ()
    status: GenerationStatus = GenerationStatus.NOT_STARTED


class GenerationPlanningFinding(FrozenStrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,100}$")
    severity: PlanningFindingSeverity
    message: str = Field(min_length=1, max_length=500)
    output_code: ImplementationOutputCode | None = None
    planned_file_id: str | None = None


class GenerationTraceabilityCoverage(FrozenStrictModel):
    approved_outputs: tuple[ImplementationOutputCode, ...]
    represented_outputs: tuple[ImplementationOutputCode, ...]
    referenced_specification_item_ids: tuple[str, ...]
    unmapped_specification_item_ids: tuple[str, ...]
    structural_file_ids: tuple[str, ...]
    domain_file_ids: tuple[str, ...]
    planning_blocker_codes: tuple[str, ...]
    planning_warning_codes: tuple[str, ...]


class GenerationPlan(FrozenStrictModel):
    identity: GenerationPlanIdentity
    plan_policy_version: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{2,50}$")
    approved_output_codes: tuple[ImplementationOutputCode, ...] = Field(
        min_length=1
    )
    effective_stack: ApprovedImplementationStack
    planned_files: tuple[PlannedFileEntry, ...]
    non_file_deliverables: tuple[PlannedNonFileDeliverable, ...]
    generation_order: tuple[str, ...]
    traceability_coverage: GenerationTraceabilityCoverage
    validation_findings: tuple[GenerationPlanningFinding, ...]
    source_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: GenerationPlanStatus


class GenerationValidationError(FrozenStrictModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    planned_file_id: str | None = None
    relative_output_path: RelativeOutputPath | None = None


class GenerationValidationResult(FrozenStrictModel):
    valid: bool
    errors: tuple[GenerationValidationError, ...] = ()

    @model_validator(mode="after")
    def validity_matches_errors(self):
        if self.valid == bool(self.errors):
            raise ValueError("valid must be true exactly when errors is empty")
        return self


class CodeGenerationErrorCode(StrEnum):
    LOCAL_INFERENCE_DISABLED = "LOCAL_INFERENCE_DISABLED"
    INVALID_GENERATION_PLAN = "INVALID_GENERATION_PLAN"
    OLLAMA_UNAVAILABLE = "OLLAMA_UNAVAILABLE"
    MODEL_NOT_INSTALLED = "MODEL_NOT_INSTALLED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    INVALID_MODEL_RESPONSE = "INVALID_MODEL_RESPONSE"
    INVALID_RESPONSE_SCHEMA = "INVALID_RESPONSE_SCHEMA"
    EMPTY_GENERATION = "EMPTY_GENERATION"
    CONTEXT_LIMIT_EXCEEDED = "CONTEXT_LIMIT_EXCEEDED"
    MISSING_DEPENDENCY_CONTEXT = "MISSING_DEPENDENCY_CONTEXT"
    MISSING_REQUIRED_INFORMATION = "MISSING_REQUIRED_INFORMATION"
    UNSUPPORTED_CONTENT = "UNSUPPORTED_CONTENT"
    UNSAFE_GENERATED_CONTENT = "UNSAFE_GENERATED_CONTENT"
    GENERATION_INTERRUPTED = "GENERATION_INTERRUPTED"


class FileContentType(StrEnum):
    JAVASCRIPT = "JAVASCRIPT"
    JSX = "JSX"
    JSON = "JSON"
    SQL = "SQL"
    HTML = "HTML"
    CSS = "CSS"
    MARKDOWN = "MARKDOWN"
    YAML = "YAML"
    ENV = "ENV"
    TEXT = "TEXT"


class SyntaxValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


class GeneratedCandidateStatus(StrEnum):
    VALIDATED = "VALIDATED"
    MISSING_INFORMATION = "MISSING_INFORMATION"


class FileTrustedSpecificationItem(FrozenStrictModel):
    project_item_id: str = Field(pattern=r"^PSI-[0-9A-F]{24}$")
    artifact_type: str
    identity_key: str
    trusted_data_json: str = Field(min_length=2)
    source_artifact_ids: tuple[str, ...] = ()


class DependencyFingerprint(FrozenStrictModel):
    planned_file_id: str = Field(pattern=r"^GPF-[0-9a-f]{32}$")
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FileDependencyContext(FrozenStrictModel):
    planned_file_id: str = Field(pattern=r"^GPF-[0-9a-f]{32}$")
    relative_output_path: RelativeOutputPath
    responsibility: str = Field(min_length=1, max_length=500)
    validated_content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FileGenerationContext(FrozenStrictModel):
    agent_project_id: str
    run_id: str
    generation_plan_id: str = Field(pattern=r"^GPL-[0-9a-f]{32}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    planned_file_id: str = Field(pattern=r"^GPF-[0-9a-f]{32}$")
    relative_output_path: RelativeOutputPath
    responsibility: str = Field(min_length=1, max_length=500)
    content_type: FileContentType
    authorized_output_codes: tuple[ImplementationOutputCode, ...] = Field(
        min_length=1
    )
    effective_stack: ApprovedImplementationStack
    trusted_specification_items: tuple[FileTrustedSpecificationItem, ...] = ()
    dependencies: tuple[FileDependencyContext, ...] = ()
    missing_information_constraints: tuple[str, ...] = Field(min_length=1)
    traceability_root_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def context_collections_are_unique(self):
        collections = (
            self.authorized_output_codes,
            tuple(item.project_item_id for item in self.trusted_specification_items),
            tuple(item.planned_file_id for item in self.dependencies),
        )
        if any(len(values) != len(set(values)) for values in collections):
            raise ValueError("generation context collections must be unique")
        return self


class ModelFileResponse(FrozenStrictModel):
    content: str
    missing_information: tuple[str, ...] = ()
    bounded_assumptions: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @field_validator(
        "missing_information", "bounded_assumptions", "diagnostics"
    )
    @classmethod
    def bounded_diagnostic_lists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) > 20 or any(
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 500
            for value in values
        ):
            raise ValueError("model diagnostics exceed the bounded contract")
        return values


class ProviderGenerationRequest(FrozenStrictModel):
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    response_schema: dict[str, Any]
    prompt_template_version: str
    generation_policy_version: str
    context_tokens: int = Field(ge=1024)
    max_output_tokens: int = Field(ge=1)
    correction_retry: bool = False


class OllamaRuntimeMetadata(FrozenStrictModel):
    provider_type: str = "ollama"
    requested_model: str
    resolved_model: str
    model_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_source: str | None = None
    model_license: str | None = None
    quantization_level: str | None = None
    parameter_size: str | None = None
    ollama_version: str | None = None
    done: bool
    done_reason: str | None = None
    prompt_token_count: int | None = Field(default=None, ge=0)
    generated_token_count: int | None = Field(default=None, ge=0)
    load_duration_ms: float | None = Field(default=None, ge=0)
    generation_duration_ms: float | None = Field(default=None, ge=0)
    total_duration_ms: float | None = Field(default=None, ge=0)
    context_tokens: int = Field(ge=1024)
    max_output_tokens: int = Field(ge=1)
    temperature: float
    keep_alive: str


class ProviderGenerationResponse(FrozenStrictModel):
    result: ModelFileResponse
    metadata: OllamaRuntimeMetadata


class ContentValidationFinding(FrozenStrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,100}$")
    message: str = Field(min_length=1, max_length=500)


class GeneratedContentCandidate(FrozenStrictModel):
    agent_project_id: str
    run_id: str
    generation_plan_id: str = Field(pattern=r"^GPL-[0-9a-f]{32}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    planned_file_id: str = Field(pattern=r"^GPF-[0-9a-f]{32}$")
    relative_output_path: RelativeOutputPath
    authorized_output_codes: tuple[ImplementationOutputCode, ...] = Field(
        min_length=1
    )
    relevant_specification_item_ids: tuple[str, ...] = ()
    dependency_fingerprints: tuple[DependencyFingerprint, ...] = ()
    provider_type: str
    requested_model: str
    resolved_model: str
    model_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_source: str | None = None
    model_license: str | None = None
    quantization_level: str | None = None
    parameter_size: str | None = None
    ollama_version: str | None = None
    prompt_template_version: str
    generation_policy_version: str
    context_tokens: int = Field(ge=1024)
    max_output_tokens: int = Field(ge=1)
    temperature: float
    keep_alive: str
    generated_content: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    validation_status: GeneratedCandidateStatus
    syntax_validation_status: SyntaxValidationStatus
    validation_findings: tuple[ContentValidationFinding, ...] = ()
    missing_information: tuple[str, ...] = ()
    bounded_assumptions: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    attempts: int = Field(ge=1, le=2)
    inference_duration_ms: float | None = Field(default=None, ge=0)
    prompt_token_count: int | None = Field(default=None, ge=0)
    generated_token_count: int | None = Field(default=None, ge=0)
    safe_failure_code: CodeGenerationErrorCode | None = None

    @field_validator("relevant_specification_item_ids")
    @classmethod
    def candidate_references_are_valid(cls, values: tuple[str, ...]):
        if len(values) != len(set(values)) or any(
            re.fullmatch(r"PSI-[0-9A-F]{24}", value) is None for value in values
        ):
            raise ValueError("candidate specification references are invalid")
        return values

    @model_validator(mode="after")
    def successful_candidate_has_content_and_hash(self):
        if len(self.authorized_output_codes) != len(set(self.authorized_output_codes)):
            raise ValueError("candidate outputs must be unique")
        dependency_ids = tuple(
            item.planned_file_id for item in self.dependency_fingerprints
        )
        if len(dependency_ids) != len(set(dependency_ids)):
            raise ValueError("candidate dependencies must be unique")
        if self.validation_status is GeneratedCandidateStatus.VALIDATED:
            if not self.generated_content or not self.content_sha256:
                raise ValueError("validated candidates require content and a hash")
            if (
                hashlib.sha256(self.generated_content.encode("utf-8")).hexdigest()
                != self.content_sha256
            ):
                raise ValueError("candidate content hash is inconsistent")
            if self.safe_failure_code is not None or self.missing_information:
                raise ValueError("validated candidates cannot contain failure state")
        elif self.safe_failure_code is None or not self.missing_information:
            raise ValueError("missing-information candidates require safe findings")
        return self

