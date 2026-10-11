from pydantic import BaseModel, ConfigDict

from app.common.status import WorkflowStage


class WorkflowTransitionResult(BaseModel):
    """Source-supported details of a completed workflow transition."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    stage_before: WorkflowStage
    stage_after: WorkflowStage
