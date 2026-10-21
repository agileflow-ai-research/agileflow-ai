from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4TestGenerationWorkflowRecord,
    Agent4TestGenerationWorkflowResponse,
)


def build_agent4_workflow_response(
    record: Agent4TestGenerationWorkflowRecord,
) -> Agent4TestGenerationWorkflowResponse:
    """Project the persisted record without ownership or storage details."""
    payload = record.model_dump(exclude={"owner_user_id"})
    if payload["n1_confirmation"] is not None:
        payload["n1_confirmation"].pop("confirmed_by_user_id", None)
    return Agent4TestGenerationWorkflowResponse.model_validate(
        payload
    )
