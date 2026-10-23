from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.status import AgentStage
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode


class StrictAgent4WorkflowContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Agent4TestGenerationNodeId(StrEnum):
    INPUT_OUTPUT_SETUP = "INPUT_OUTPUT_SETUP"
    INPUT_PREPARATION = "INPUT_PREPARATION"
    TESTING_INTELLIGENCE = "TESTING_INTELLIGENCE"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    TESTING_FACT_EXTRACTION = "TESTING_FACT_EXTRACTION"
    CONTEXT_TESTABILITY = "CONTEXT_TESTABILITY"
    TEST_PLANNING_REVIEW = "TEST_PLANNING_REVIEW"
    TEST_GENERATION_RESULTS = "TEST_GENERATION_RESULTS"


AGENT4_TEST_GENERATION_NODE_ORDER = tuple(Agent4TestGenerationNodeId)


class Agent4WorkflowNodeStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    LOCKED = "LOCKED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class Agent4PipelineStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class Agent4WorkflowNodeState(StrictAgent4WorkflowContract):
    node_id: Agent4TestGenerationNodeId
    status: Agent4WorkflowNodeStatus
    updated_at: datetime


TEST_GENERATION_OUTPUT_ORDER = tuple(TestGenerationOutputCode)
_TEST_GENERATION_OUTPUT_INDEX = {
    output: index for index, output in enumerate(TEST_GENERATION_OUTPUT_ORDER)
}


def canonical_test_generation_outputs(
    outputs: list[TestGenerationOutputCode],
) -> list[TestGenerationOutputCode]:
    return sorted(outputs, key=_TEST_GENERATION_OUTPUT_INDEX.__getitem__)


class TestGenerationOutputSelectionUpdate(StrictAgent4WorkflowContract):
    selected_outputs: list[TestGenerationOutputCode]

    @field_validator("selected_outputs")
    @classmethod
    def reject_duplicates(
        cls, outputs: list[TestGenerationOutputCode]
    ) -> list[TestGenerationOutputCode]:
        if len(outputs) != len(set(outputs)):
            raise ValueError("selected_outputs must not contain duplicates")
        return outputs


class Agent4N1ConfirmationRecord(StrictAgent4WorkflowContract):
    confirmation_id: str = Field(pattern=r"^A4N1C-[0-9a-f]{32}$")
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_revision: int = Field(ge=1)
    source_ids: list[str]
    selected_outputs: list[TestGenerationOutputCode]
    source_count: int = Field(gt=0)
    selected_output_count: int = Field(gt=0)
    confirmed_at: datetime
    confirmed_by_user_id: str

    @model_validator(mode="after")
    def validate_snapshot(self) -> "Agent4N1ConfirmationRecord":
        if self.source_ids != sorted(self.source_ids):
            raise ValueError("confirmation source_ids must use canonical order")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("confirmation source_ids must be unique")
        if self.source_count != len(self.source_ids):
            raise ValueError("confirmation source_count is inconsistent")
        if self.selected_outputs != canonical_test_generation_outputs(
            self.selected_outputs
        ):
            raise ValueError("confirmation selected_outputs must be canonical")
        if self.selected_output_count != len(self.selected_outputs):
            raise ValueError("confirmation selected_output_count is inconsistent")
        return self


class Agent4N1ConfirmationProjection(StrictAgent4WorkflowContract):
    confirmation_id: str
    source_set_digest: str
    selection_digest: str
    selection_revision: int
    source_ids: list[str]
    selected_outputs: list[TestGenerationOutputCode]
    source_count: int
    selected_output_count: int
    confirmed_at: datetime


class Agent4N2ExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class Agent4N2SourceStatus(StrEnum):
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    NORMALIZING = "NORMALIZING"
    CHUNKING = "CHUNKING"
    COMPLETE = "COMPLETE"
    PENDING_ANALYSIS = "PENDING_ANALYSIS"
    FAILED = "FAILED"


class Agent4N2Message(StrictAgent4WorkflowContract):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class Agent4N2SourceExecution(StrictAgent4WorkflowContract):
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    artifact_type: TestGenerationInputArtifactType
    source_type: TestGenerationInputSourceType
    label: str | None = None
    original_filename: str | None = None
    status: Agent4N2SourceStatus
    extraction_status: str | None = None
    normalization_status: str | None = None
    chunk_count: int = Field(default=0, ge=0)
    warnings: list[Agent4N2Message] = Field(default_factory=list)
    error: Agent4N2Message | None = None
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None


class Agent4N2Execution(StrictAgent4WorkflowContract):
    execution_id: str = Field(pattern=r"^A4N2E-[0-9a-f]{32}$")
    attempt_number: int = Field(ge=1)
    trigger: Literal["N1_CONFIRMATION", "LEGACY_START", "SOURCE_RETRY"]
    retry_source_id: str | None = Field(
        default=None, pattern=r"^A4SRC-[0-9a-f]{32}$"
    )
    status: Agent4N2ExecutionStatus
    confirmation_id: str = Field(pattern=r"^A4N1C-[0-9a-f]{32}$")
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_source_ids: list[str] = Field(min_length=1)
    sources: list[Agent4N2SourceExecution] = Field(min_length=1)
    created_at: datetime
    queued_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    total_chunks: int = Field(default=0, ge=0)
    warnings: list[Agent4N2Message] = Field(default_factory=list)
    error: Agent4N2Message | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def validate_sources(self) -> "Agent4N2Execution":
        ids = [source.source_id for source in self.sources]
        if ids != self.confirmed_source_ids:
            raise ValueError("N2 execution sources must match the confirmed snapshot")
        if len(ids) != len(set(ids)):
            raise ValueError("N2 execution sources must be unique")
        return self


class Agent4N2ExecutionSummary(StrictAgent4WorkflowContract):
    execution_id: str
    attempt_number: int
    trigger: str
    status: Agent4N2ExecutionStatus
    created_at: datetime
    completed_at: datetime | None
    failed_at: datetime | None


class Agent4N3ExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class Agent4N3SourceStatus(StrEnum):
    QUEUED = "QUEUED"
    RULE_CLASSIFICATION = "RULE_CLASSIFICATION"
    ZERO_SHOT_CLASSIFICATION = "ZERO_SHOT_CLASSIFICATION"
    HYBRID_DECISION = "HYBRID_DECISION"
    SEMANTIC_EXTRACTION = "SEMANTIC_EXTRACTION"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETE = "COMPLETE"
    PENDING_ANALYSIS = "PENDING_ANALYSIS"
    FAILED = "FAILED"


class Agent4N3SubStageName(StrEnum):
    RULE_ANALYSIS = "TI_RULE_ANALYSIS"
    AI_CLASSIFICATION = "TI_AI_CLASSIFICATION"
    HYBRID_DECISION = "TI_HYBRID_DECISION"
    HUMAN_REVIEW = "TI_HUMAN_REVIEW"
    EFFECTIVE_CLASSIFICATION = "TI_EFFECTIVE_CLASSIFICATION"
    FACT_EXTRACTION = "TI_FACT_EXTRACTION"


class Agent4N3SubStageStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Agent4N3ChunkDisposition(StrEnum):
    SUCCESS = "SUCCESS"
    SUCCESS_WITH_WARNINGS = "SUCCESS_WITH_WARNINGS"
    EMPTY = "EMPTY"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FAILED = "FAILED"


class Agent4N3SubStageProgress(StrictAgent4WorkflowContract):
    stage: Agent4N3SubStageName
    status: Agent4N3SubStageStatus = Agent4N3SubStageStatus.NOT_STARTED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    attempt_count: int = Field(default=0, ge=0)
    artifact_reference: str | None = Field(default=None, max_length=255)
    summary: dict[str, int | str | bool] = Field(default_factory=dict)
    safe_error: Agent4N2Message | None = None
    retryable: bool = False


class Agent4N3ChunkProgress(StrictAgent4WorkflowContract):
    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    status: Agent4N3ChunkDisposition
    fact_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    safe_error: Agent4N2Message | None = None


class Agent4N3SourceExecution(StrictAgent4WorkflowContract):
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    artifact_type: TestGenerationInputArtifactType
    source_type: TestGenerationInputSourceType
    label: str | None = None
    original_filename: str | None = None
    status: Agent4N3SourceStatus
    chunk_count: int = Field(default=0, ge=0)
    rules_complete: bool = False
    zero_shot_complete: bool = False
    hybrid_complete: bool = False
    effective_complete: bool = False
    semantic_complete: bool = False
    pending_review_items: int = Field(default=0, ge=0)
    accepted_label_count: int = Field(default=0, ge=0)
    semantic_fact_count: int = Field(default=0, ge=0)
    sub_stages: list[Agent4N3SubStageProgress] = Field(default_factory=list)
    fact_extraction_chunks: list[Agent4N3ChunkProgress] = Field(default_factory=list)
    current_sub_stage: Agent4N3SubStageName | None = None
    last_completed_sub_stage: Agent4N3SubStageName | None = None
    failed_stage: str | None = Field(default=None, max_length=80)
    warnings: list[Agent4N2Message] = Field(default_factory=list)
    error: Agent4N2Message | None = None
    retryable: bool = False
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None


class Agent4N3Execution(StrictAgent4WorkflowContract):
    execution_id: str = Field(pattern=r"^A4N3E-[0-9a-f]{32}$")
    attempt_number: int = Field(ge=1)
    trigger: Literal[
        "N2_COMPLETION", "LEGACY_START", "SOURCE_RETRY", "HUMAN_REVIEW_RESUME",
        "RESTART_RECOVERY",
    ]
    retry_source_id: str | None = Field(
        default=None, pattern=r"^A4SRC-[0-9a-f]{32}$"
    )
    status: Agent4N3ExecutionStatus
    confirmation_id: str = Field(pattern=r"^A4N1C-[0-9a-f]{32}$")
    n2_execution_id: str = Field(pattern=r"^A4N2E-[0-9a-f]{32}$")
    chunk_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sources: list[Agent4N3SourceExecution] = Field(min_length=1)
    sub_stages: list[Agent4N3SubStageProgress] = Field(default_factory=list)
    review_snapshot_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    review_id: str | None = Field(default=None, pattern=r"^A4N3R-[0-9a-f]{32}$")
    created_at: datetime
    queued_at: datetime
    started_at: datetime | None = None
    waiting_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    interrupted_at: datetime | None = None
    warnings: list[Agent4N2Message] = Field(default_factory=list)
    error: Agent4N2Message | None = None
    retryable: bool = False


class Agent4N3ExecutionSummary(StrictAgent4WorkflowContract):
    execution_id: str
    attempt_number: int
    trigger: str
    status: Agent4N3ExecutionStatus
    created_at: datetime
    waiting_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    interrupted_at: datetime | None
    sub_stages: list[Agent4N3SubStageProgress] = Field(default_factory=list)


class Agent4N4ExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class Agent4N4StageName(StrEnum):
    TRACEABILITY = "TRACEABILITY"
    TESTABILITY = "TESTABILITY"
    FEASIBILITY = "FEASIBILITY"
    CONTEXT_DECISION = "CONTEXT_DECISION"


class Agent4N4StageStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class Agent4N4StageProgress(StrictAgent4WorkflowContract):
    stage: Agent4N4StageName
    status: Agent4N4StageStatus
    artifact_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    summary: dict[str, int | str] = Field(default_factory=dict)
    error: Agent4N2Message | None = None
    updated_at: datetime


class Agent4N4Execution(StrictAgent4WorkflowContract):
    execution_id: str = Field(pattern=r"^A4N4E-[0-9a-f]{32}$")
    attempt_number: int = Field(ge=1)
    trigger: Literal["N3_COMPLETION", "LEGACY_START", "RETRY"]
    status: Agent4N4ExecutionStatus
    n3_execution_id: str = Field(pattern=r"^A4N3E-[0-9a-f]{32}$")
    stages: list[Agent4N4StageProgress]
    overall_testability: str | None = None
    overall_feasibility: str | None = None
    overall_decision: str | None = None
    selected_output_count: int = Field(ge=0)
    planning_allowed_count: int = Field(default=0, ge=0)
    blocked_output_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    executable_output_count: int = Field(default=0, ge=0)
    specification_output_count: int = Field(default=0, ge=0)
    structured_artifact_count: int = Field(default=0, ge=0)
    warning_snapshot_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    acknowledgement_id: str | None = Field(default=None, pattern=r"^A4N4A-[0-9a-f]{32}$")
    queued_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    waiting_at: datetime | None = None
    completed_at: datetime | None = None
    blocked_at: datetime | None = None
    failed_at: datetime | None = None
    interrupted_at: datetime | None = None
    warnings: list[Agent4N2Message] = Field(default_factory=list)
    error: Agent4N2Message | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def validate_stages(self):
        if [item.stage for item in self.stages] != list(Agent4N4StageName):
            raise ValueError("N4 stages must use canonical order")
        return self


class Agent4N4ExecutionSummary(StrictAgent4WorkflowContract):
    execution_id: str
    attempt_number: int
    trigger: str
    status: Agent4N4ExecutionStatus
    queued_at: datetime
    waiting_at: datetime | None
    completed_at: datetime | None
    blocked_at: datetime | None
    failed_at: datetime | None
    interrupted_at: datetime | None


class Agent4N4WarningAcknowledgementRequest(StrictAgent4WorkflowContract):
    warning_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    optional_note: str | None = Field(default=None, max_length=1000)

    @field_validator("optional_note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        if value is None or not isinstance(value, str):
            return value
        normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return None
        if any(not char.isprintable() and char not in "\n\t" for char in normalized):
            raise ValueError("acknowledgement note must contain plain printable text")
        return normalized


class Agent4N4WarningAcknowledgement(StrictAgent4WorkflowContract):
    acknowledgement_id: str = Field(pattern=r"^A4N4A-[0-9a-f]{32}$")
    n4_execution_id: str = Field(pattern=r"^A4N4E-[0-9a-f]{32}$")
    context_decision_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    warning_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    warning_ids: list[str]
    optional_note: str | None = Field(default=None, max_length=1000)
    acknowledged_at: datetime
    reviewer_user_id: str


class Agent4N4ResultFinding(StrictAgent4WorkflowContract):
    finding_id: str
    reason_code: str
    message: str


class Agent4N4OutputResult(StrictAgent4WorkflowContract):
    output_code: TestGenerationOutputCode
    testability_status: str
    feasibility_status: str
    recommended_representation: str | None
    decision: str
    planning_allowed: bool
    blockers: list[Agent4N4ResultFinding]
    warnings: list[Agent4N4ResultFinding]
    evidence_node_count: int = Field(ge=0)
    evidence_link_count: int = Field(ge=0)
    semantic_fact_count: int = Field(ge=0)
    execution_status: Literal["NOT_EXECUTED"] | None = None


class Agent4N4ResultProjection(StrictAgent4WorkflowContract):
    execution_id: str
    overall_testability: str
    overall_feasibility: str
    overall_decision: str
    warning_snapshot_fingerprint: str | None = None
    outputs: list[Agent4N4OutputResult]
    planning_allowed_count: int = Field(ge=0)
    blocked_output_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    executable_output_count: int = Field(ge=0)
    specification_output_count: int = Field(ge=0)
    structured_artifact_count: int = Field(ge=0)


class Agent4N3ReviewDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class Agent4N3ReviewResolutionRequest(StrictAgent4WorkflowContract):
    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    label: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,79}$")
    decision: Agent4N3ReviewDecision
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        if value is None or not isinstance(value, str):
            return value
        normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return None
        if any(not char.isprintable() and char not in "\n\t" for char in normalized):
            raise ValueError("review notes must contain plain printable text")
        return normalized


class Agent4N3ReviewSubmission(StrictAgent4WorkflowContract):
    review_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolutions: list[Agent4N3ReviewResolutionRequest] = Field(min_length=1)


class Agent4N3ReviewResolution(StrictAgent4WorkflowContract):
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    label: str
    decision: Agent4N3ReviewDecision
    note: str | None = None
    hybrid_result_id: str = Field(pattern=r"^A4HYB-[0-9a-f]{32}$")
    hybrid_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class Agent4N3ReviewEvent(StrictAgent4WorkflowContract):
    review_id: str = Field(pattern=r"^A4N3R-[0-9a-f]{32}$")
    execution_id: str = Field(pattern=r"^A4N3E-[0-9a-f]{32}$")
    review_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolutions: list[Agent4N3ReviewResolution] = Field(min_length=1)
    reviewed_at: datetime
    reviewer_user_id: str


class Agent4N3ReviewItem(StrictAgent4WorkflowContract):
    source_id: str
    source_label: str | None = None
    artifact_type: TestGenerationInputArtifactType
    chunk_id: str
    chunk_context: str = Field(min_length=1, max_length=4000)
    label: str
    label_description: str
    relationship: str
    reason_codes: list[str]
    explanation: str | None = None
    model_score: float | None = Field(default=None, ge=0, le=1)
    rule_detected: bool
    rule_evidence_quotes: list[str]
    hybrid_result_id: str
    hybrid_manifest_fingerprint: str
    auto_accepted_labels: list[str]


class Agent4N3ReviewProjection(StrictAgent4WorkflowContract):
    review_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_id: str
    auto_accepted_count: int = Field(ge=0)
    auto_rejected_count: int = Field(ge=0)
    pending_review_count: int = Field(ge=0)
    review_relationship_counts: dict[str, int]
    auto_accepted_label_counts: dict[str, int]
    items: list[Agent4N3ReviewItem]


class Agent4TestGenerationWorkflowRecord(StrictAgent4WorkflowContract):
    schema_version: str
    workflow_version: str
    agent_project_id: str
    owner_user_id: str
    agent_stage: Literal[AgentStage.TEST_GENERATION]
    pipeline_status: Agent4PipelineStatus
    current_node_id: Agent4TestGenerationNodeId
    nodes: list[Agent4WorkflowNodeState]
    selected_outputs: list[TestGenerationOutputCode] = Field(default_factory=list)
    selection_revision: int = Field(default=0, ge=0)
    selection_updated_at: datetime | None = None
    n1_confirmation: Agent4N1ConfirmationRecord | None = None
    n2_executions: list[Agent4N2Execution] = Field(default_factory=list)
    current_n2_execution_id: str | None = None
    n3_executions: list[Agent4N3Execution] = Field(default_factory=list)
    current_n3_execution_id: str | None = None
    n3_review_history: list[Agent4N3ReviewEvent] = Field(default_factory=list)
    n4_executions: list[Agent4N4Execution] = Field(default_factory=list)
    current_n4_execution_id: str | None = None
    n4_acknowledgement_history: list[Agent4N4WarningAcknowledgement] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_node_contract(self) -> "Agent4TestGenerationWorkflowRecord":
        if tuple(node.node_id for node in self.nodes) != AGENT4_TEST_GENERATION_NODE_ORDER:
            raise ValueError("nodes must match the Agent 4 Test Generation workflow order")
        if self.selected_outputs != canonical_test_generation_outputs(
            self.selected_outputs
        ):
            raise ValueError("selected_outputs must use canonical product order")
        if len(self.selected_outputs) != len(set(self.selected_outputs)):
            raise ValueError("selected_outputs must not contain duplicates")
        if self.selection_revision == 0 and self.selection_updated_at is not None:
            raise ValueError("initial output selection cannot have an update timestamp")
        if self.selection_revision > 0 and self.selection_updated_at is None:
            raise ValueError("revised output selection requires an update timestamp")
        if self.n1_confirmation is not None:
            confirmation = self.n1_confirmation
            if confirmation.selected_outputs != self.selected_outputs:
                raise ValueError("confirmation outputs must match selected_outputs")
            if confirmation.selection_revision != self.selection_revision:
                raise ValueError("confirmation revision must match selection_revision")
        return self


class Agent4TestGenerationWorkflowResponse(StrictAgent4WorkflowContract):
    schema_version: str
    workflow_version: str
    agent_project_id: str
    agent_stage: Literal[AgentStage.TEST_GENERATION]
    pipeline_status: Agent4PipelineStatus
    current_node_id: Agent4TestGenerationNodeId
    nodes: list[Agent4WorkflowNodeState]
    selected_outputs: list[TestGenerationOutputCode]
    selection_revision: int
    selection_updated_at: datetime | None
    n1_confirmation: Agent4N1ConfirmationProjection | None
    n2_execution: Agent4N2Execution | None = None
    n2_execution_count: int = Field(default=0, ge=0)
    n2_history: list[Agent4N2ExecutionSummary] = Field(default_factory=list)
    n3_execution: Agent4N3Execution | None = None
    n3_execution_count: int = Field(default=0, ge=0)
    n3_history: list[Agent4N3ExecutionSummary] = Field(default_factory=list)
    reviewed_item_count: int = Field(default=0, ge=0)
    n4_execution: Agent4N4Execution | None = None
    n4_execution_count: int = Field(default=0, ge=0)
    n4_history: list[Agent4N4ExecutionSummary] = Field(default_factory=list)
    n4_acknowledgement_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
