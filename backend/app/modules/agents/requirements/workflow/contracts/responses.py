from datetime import datetime

from app.modules.agents.requirements.workflow.contracts.common import (
    StrictWorkflowContract,
)
from app.modules.agents.requirements.workflow.contracts.n1 import (
    RequirementN1State,
    RequirementOutputCode,
)
from app.modules.agents.requirements.workflow.contracts.n2 import RequirementN2Execution
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Execution


class RequirementWorkflowResponse(StrictWorkflowContract):
    schema_version: str
    workflow_version: str
    agent_project_id: str
    selected_outputs: list[RequirementOutputCode]
    selection_revision: int
    selection_digest: str
    source_set_digest: str
    source_count: int
    n1_state: RequirementN1State
    n1_confirmation_current: bool
    confirmed_source_set_digest: str | None = None
    confirmed_selection_digest: str | None = None
    confirmed_at: datetime | None = None
    n2_execution: RequirementN2Execution | None = None
    n2_is_current: bool = False
    n2_execution_count: int = 0
    n3_execution: RequirementN3Execution | None = None
    n3_execution_count: int = 0
    created_at: datetime
    updated_at: datetime
