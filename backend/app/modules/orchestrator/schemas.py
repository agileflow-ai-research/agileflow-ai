from pydantic import BaseModel, ConfigDict

from app.common.status import ApprovalGate, WorkflowStage


class WorkflowTransitionResult(BaseModel):
    """Source-supported details of a completed workflow transition."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    stage_before: WorkflowStage
    stage_after: WorkflowStage


class WorkflowSnapshot(BaseModel):
    """Read-only view of structural and currently executable workflow state."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    current_stage: WorkflowStage
    current_stage_owner: str
    next_stage: WorkflowStage | None
    next_stage_owner: str | None
    next_transition_available: bool
    approval_gate: ApprovalGate | None = None
