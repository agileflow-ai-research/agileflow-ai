from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.requirements.api.dependencies import (
    get_discovery_result_service,
    get_requirement_n3_orchestration_service,
)
from app.modules.agents.requirements.api.errors import requirement_error, requirement_project_error
from app.modules.agents.requirements.contracts.errors import WrongAgentProjectTypeError
from app.modules.agents.requirements.discovery.contracts import DiscoveryExecutionArtifacts
from app.modules.agents.requirements.discovery.service import (
    DiscoveryResultError,
    DiscoveryResultService,
)
from app.modules.agents.requirements.discovery.storage import DiscoveryStorageError
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Execution
from app.modules.agents.requirements.workflow.orchestration.n3_service import (
    RequirementN3OrchestrationError,
    RequirementN3OrchestrationService,
)
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorageError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
    StandaloneService,
)
from app.modules.standalone.router import get_standalone_service


router = APIRouter()
PROJECT_ERRORS = (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    WrongAgentProjectTypeError,
)


@router.get(
    "/{agent_project_id}/discovery/{execution_id}",
    response_model=SuccessResponse[DiscoveryExecutionArtifacts],
)
def get_discovery_results(
    agent_project_id: str,
    execution_id: str,
    service: Annotated[DiscoveryResultService, Depends(get_discovery_result_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DiscoveryExecutionArtifacts] | JSONResponse:
    try:
        result = service.get(agent_project_id, execution_id, current_user)
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "loading requirement discovery results")
    except DiscoveryResultError as exc:
        return requirement_error(404, "Discovery results unavailable", "discovery", str(exc))
    except (DiscoveryStorageError, RequirementWorkflowStorageError, StandaloneServiceError):
        return requirement_error(
            503, "Discovery storage failed", "discovery", "Discovery results could not be loaded"
        )
    return SuccessResponse(message="Discovery results retrieved", data=result)


@router.post(
    "/{agent_project_id}/workflow/n3/retry",
    response_model=SuccessResponse[RequirementN3Execution],
)
def retry_requirement_n3(
    agent_project_id: str,
    service: Annotated[
        RequirementN3OrchestrationService,
        Depends(get_requirement_n3_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    standalone: Annotated[StandaloneService, Depends(get_standalone_service)],
) -> SuccessResponse[RequirementN3Execution] | JSONResponse:
    try:
        require_requirements_project(standalone, agent_project_id, current_user)
        execution = service.retry(agent_project_id, current_user.user_id)
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "retrying requirement discovery")
    except RequirementN3OrchestrationError as exc:
        return requirement_error(409, "N3 cannot be retried", "discovery", str(exc))
    except (DiscoveryStorageError, RequirementWorkflowStorageError):
        return requirement_error(
            503, "Discovery storage failed", "discovery", "N3 retry could not be started"
        )
    return SuccessResponse(message="N3 retry accepted", data=execution)
