from datetime import datetime
from enum import StrEnum

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

