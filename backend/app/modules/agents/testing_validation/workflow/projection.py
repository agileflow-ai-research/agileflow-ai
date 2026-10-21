from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2ExecutionSummary,
    Agent4N3ExecutionSummary,
    Agent4N4ExecutionSummary,
    Agent4TestGenerationWorkflowRecord,
    Agent4TestGenerationWorkflowResponse,
)


def build_agent4_workflow_response(
    record: Agent4TestGenerationWorkflowRecord,
) -> Agent4TestGenerationWorkflowResponse:
    """Project the persisted record without ownership or storage details."""
    payload = record.model_dump(
        exclude={
            "owner_user_id", "n2_executions", "current_n2_execution_id",
            "n3_executions", "current_n3_execution_id", "n3_review_history",
            "n4_executions", "current_n4_execution_id", "n4_acknowledgement_history",
        }
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
        n3_execution=next(
            (
                execution.model_copy(deep=True)
                for execution in reversed(record.n3_executions)
                if execution.execution_id == record.current_n3_execution_id
            ),
            None,
        ),
        n3_execution_count=len(record.n3_executions),
        n3_history=[
            Agent4N3ExecutionSummary(
                execution_id=item.execution_id,
                attempt_number=item.attempt_number,
                trigger=item.trigger,
                status=item.status,
                created_at=item.created_at,
                waiting_at=item.waiting_at,
                completed_at=item.completed_at,
                failed_at=item.failed_at,
                interrupted_at=item.interrupted_at,
            )
            for item in record.n3_executions
        ],
        reviewed_item_count=sum(
            len(event.resolutions) for event in record.n3_review_history
        ),
        n4_execution=next(
            (
                execution.model_copy(deep=True)
                for execution in reversed(record.n4_executions)
                if execution.execution_id == record.current_n4_execution_id
            ),
            None,
        ),
        n4_execution_count=len(record.n4_executions),
        n4_history=[
            Agent4N4ExecutionSummary(
                execution_id=item.execution_id,
                attempt_number=item.attempt_number,
                trigger=item.trigger,
                status=item.status,
                queued_at=item.queued_at,
                waiting_at=item.waiting_at,
                completed_at=item.completed_at,
                blocked_at=item.blocked_at,
                failed_at=item.failed_at,
                interrupted_at=item.interrupted_at,
            )
            for item in record.n4_executions
        ],
        n4_acknowledgement_count=len(record.n4_acknowledgement_history),
    )
    return Agent4TestGenerationWorkflowResponse.model_validate(payload)
