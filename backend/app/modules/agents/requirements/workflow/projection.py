"""Pure projection from persisted workflow state to its public contract."""

from app.modules.agents.requirements.workflow.contracts.n1 import RequirementN1State
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.contracts.responses import (
    RequirementWorkflowResponse,
)


def confirmation_is_current(record: RequirementWorkflowRecord) -> bool:
    confirmation = record.n1_confirmation
    return bool(
        confirmation
        and confirmation.source_set_digest == record.source_set_digest
        and confirmation.selection_digest == record.selection_digest
    )


def build_workflow_response(
    record: RequirementWorkflowRecord, source_count: int
) -> RequirementWorkflowResponse:
    current = confirmation_is_current(record)
    if source_count == 0 or not record.selected_outputs:
        state = RequirementN1State.NOT_STARTED
    elif current:
        state = RequirementN1State.COMPLETE
    else:
        state = RequirementN1State.WAITING_FOR_HUMAN
    confirmation = record.n1_confirmation
    execution = next(
        (
            item
            for item in reversed(record.n2_executions)
            if item.execution_id == record.current_n2_execution_id
        ),
        None,
    )
    n2_is_current = bool(
        current
        and execution
        and confirmation
        and execution.confirmed_source_set_digest == confirmation.source_set_digest
        and execution.confirmed_selection_digest == confirmation.selection_digest
    )
    return RequirementWorkflowResponse(
        schema_version=record.schema_version,
        workflow_version=record.workflow_version,
        agent_project_id=record.agent_project_id,
        selected_outputs=record.selected_outputs,
        selection_revision=record.selection_revision,
        selection_digest=record.selection_digest,
        source_set_digest=record.source_set_digest,
        source_count=source_count,
        n1_state=state,
        n1_confirmation_current=current,
        confirmed_source_set_digest=(
            confirmation.source_set_digest if confirmation else None
        ),
        confirmed_selection_digest=(
            confirmation.selection_digest if confirmation else None
        ),
        confirmed_at=confirmation.confirmed_at if confirmation else None,
        n2_execution=execution,
        n2_is_current=n2_is_current,
        n2_execution_count=len(record.n2_executions),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
