from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2ExecutionSummary,
    Agent4TestGenerationWorkflowRecord,
    Agent4TestGenerationWorkflowResponse,
)


def build_agent4_workflow_response(
    record: Agent4TestGenerationWorkflowRecord,
) -> Agent4TestGenerationWorkflowResponse:
    """Project the persisted record without ownership or storage details."""
    payload = record.model_dump(
        exclude={"owner_user_id", "n2_executions", "current_n2_execution_id"}
    )
    if payload["n1_confirmation"] is not None:
        payload["n1_confirmation"].pop("confirmed_by_user_id", None)
    current = next(
        (
            execution
            for execution in reversed(record.n2_executions)
            if execution.execution_id == record.current_n2_execution_id
        ),
        None,
    )
    payload.update(
        n2_execution=current,
        n2_execution_count=len(record.n2_executions),
        n2_history=[
            Agent4N2ExecutionSummary(
                execution_id=item.execution_id,
                attempt_number=item.attempt_number,
                trigger=item.trigger,
                status=item.status,
                created_at=item.created_at,
                completed_at=item.completed_at,
                failed_at=item.failed_at,
            )
            for item in record.n2_executions
        ],
    )
    return Agent4TestGenerationWorkflowResponse.model_validate(payload)
