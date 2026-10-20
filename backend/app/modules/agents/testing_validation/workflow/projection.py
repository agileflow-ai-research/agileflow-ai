from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4TestGenerationWorkflowRecord,
    Agent4TestGenerationWorkflowResponse,
)


def build_agent4_workflow_response(
    record: Agent4TestGenerationWorkflowRecord,
) -> Agent4TestGenerationWorkflowResponse:
    """Project the persisted record without ownership or storage details."""
    return Agent4TestGenerationWorkflowResponse.model_validate(
        record.model_dump(exclude={"owner_user_id"})
    )
