from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.requirements.api.dependencies import (
    get_requirement_n2_orchestration_service,
    get_requirement_workflow_service,
)
from app.modules.agents.requirements.api.errors import requirement_error, requirement_project_error
from app.modules.agents.requirements.infrastructure.storage import SourceStorageError
from app.modules.agents.requirements.service import WrongAgentProjectTypeError
from app.modules.agents.requirements.workflow.schemas import (
    RequirementOutputSelectionUpdate,
    RequirementWorkflowResponse,
)
from app.modules.agents.requirements.workflow.orchestration import (
    RequirementN2OrchestrationService,
)
from app.modules.agents.requirements.workflow.service import (
    RequirementWorkflowGateError,
    RequirementWorkflowService,
)
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorageError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
)


router = APIRouter()
PROJECT_ERRORS = (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    WrongAgentProjectTypeError,
)
STORAGE_ERRORS = (
    StandaloneServiceError,
    SourceStorageError,
    RequirementWorkflowStorageError,
)


@router.get(
    "/{agent_project_id}/workflow",
    response_model=SuccessResponse[RequirementWorkflowResponse],
)
def get_requirement_workflow(
    agent_project_id: str,
    service: Annotated[
        RequirementN2OrchestrationService,
        Depends(get_requirement_n2_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[RequirementWorkflowResponse] | JSONResponse:
    try:
        workflow = service.get_workflow(agent_project_id, current_user)
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "loading the requirements workflow")
    except STORAGE_ERRORS:
        return requirement_error(
            503, "Workflow storage failed", "workflow", "The requirements workflow could not be loaded"
        )
    return SuccessResponse(message="Requirements workflow retrieved", data=workflow)


@router.put(
    "/{agent_project_id}/workflow/outputs",
    response_model=SuccessResponse[RequirementWorkflowResponse],
)
def update_requirement_outputs(
    agent_project_id: str,
    request: RequirementOutputSelectionUpdate,
    service: Annotated[RequirementWorkflowService, Depends(get_requirement_workflow_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[RequirementWorkflowResponse] | JSONResponse:
    try:
        workflow = service.update_outputs(
            agent_project_id, current_user, request.selected_outputs
        )
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "updating requested outputs")
    except STORAGE_ERRORS:
        return requirement_error(
            503, "Workflow storage failed", "workflow", "Requested outputs could not be persisted"
        )
    return SuccessResponse(message="Requested outputs updated", data=workflow)


@router.post(
    "/{agent_project_id}/workflow/n1/continue",
    response_model=SuccessResponse[RequirementWorkflowResponse],
)
def continue_requirement_n1(
    agent_project_id: str,
    service: Annotated[
        RequirementN2OrchestrationService,
        Depends(get_requirement_n2_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[RequirementWorkflowResponse] | JSONResponse:
    try:
        workflow = service.continue_n1_and_start(agent_project_id, current_user)
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "continuing the requirements workflow")
    except RequirementWorkflowGateError as exc:
        return requirement_error(409, "N1 is not ready", "workflow", str(exc))
    except STORAGE_ERRORS:
        return requirement_error(
            503, "Workflow storage failed", "workflow", "N1 confirmation could not be persisted"
        )
    return SuccessResponse(message="N1 input confirmed", data=workflow)


@router.post(
    "/{agent_project_id}/workflow/n2/retry",
    response_model=SuccessResponse[RequirementWorkflowResponse],
)
def retry_requirement_n2(
    agent_project_id: str,
    service: Annotated[
        RequirementN2OrchestrationService,
        Depends(get_requirement_n2_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[RequirementWorkflowResponse] | JSONResponse:
    try:
        workflow = service.retry(agent_project_id, current_user)
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "retrying evidence processing")
    except RequirementWorkflowGateError as exc:
        return requirement_error(409, "N2 cannot be retried", "workflow", str(exc))
    except STORAGE_ERRORS:
        return requirement_error(
            503,
            "Workflow storage failed",
            "workflow",
            "N2 retry state could not be persisted",
        )
    return SuccessResponse(message="N2 retry accepted", data=workflow)
