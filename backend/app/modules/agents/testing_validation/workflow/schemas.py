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
    created_at: datetime
    updated_at: datetime
