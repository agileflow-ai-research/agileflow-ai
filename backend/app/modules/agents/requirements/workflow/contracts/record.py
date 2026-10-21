from datetime import datetime

from pydantic import Field

from app.modules.agents.requirements.workflow.contracts.common import (
    StrictWorkflowContract,
)
from app.modules.agents.requirements.workflow.contracts.n1 import (
    RequirementN1Confirmation,
    RequirementOutputCode,
)
from app.modules.agents.requirements.workflow.contracts.n2 import RequirementN2Execution
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Execution
from app.modules.agents.requirements.workflow.contracts.n4 import RequirementN4Execution


class RequirementWorkflowRecord(StrictWorkflowContract):
    schema_version: str
    workflow_version: str
    agent_project_id: str
    owner_user_id: str
    selected_outputs: list[RequirementOutputCode]
    selection_revision: int = Field(ge=0)
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    n1_confirmation: RequirementN1Confirmation | None = None
    n2_executions: list[RequirementN2Execution] = Field(default_factory=list)
    current_n2_execution_id: str | None = None
    n3_executions: list[RequirementN3Execution] = Field(default_factory=list)
    current_n3_execution_id: str | None = None
    n4_executions: list[RequirementN4Execution] = Field(
        default_factory=list, exclude_if=lambda value: not value
    )
    current_n4_execution_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    created_at: datetime
    updated_at: datetime
