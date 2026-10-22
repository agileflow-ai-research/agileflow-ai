from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.requirements.api.dependencies import (
    get_quality_result_service, get_requirement_n4_orchestration_service,
)
from app.modules.agents.requirements.api.errors import requirement_error, requirement_project_error
from app.modules.agents.requirements.contracts.errors import WrongAgentProjectTypeError
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.quality.api import QualityExecutionArtifacts, QualityResultError
from app.modules.agents.requirements.quality.n4_service import RequirementN4OrchestrationError
from app.modules.agents.requirements.quality.storage import QualityStorageError
from app.modules.agents.requirements.workflow.contracts.n4 import RequirementN4Execution, RequirementN4Status
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorageError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import AgentProjectNotFoundError, ArchivedAgentProjectError, StandaloneService

router = APIRouter()
PROJECT_ERRORS = (AgentProjectNotFoundError, ArchivedAgentProjectError, WrongAgentProjectTypeError)


@router.get("/{agent_project_id}/quality/{execution_id}", response_model=SuccessResponse[QualityExecutionArtifacts])
def get_quality_execution(agent_project_id: str, execution_id: str,
    service: Annotated[object, Depends(get_quality_result_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)]):
    try:
        result = service.get(agent_project_id, execution_id, current_user)
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "loading requirement quality results")
    except QualityResultError as exc:
        return requirement_error(404, "Quality results unavailable", "quality", str(exc))
    except (QualityStorageError, RequirementWorkflowStorageError):
        return requirement_error(503, "Quality storage failed", "quality", "Persisted quality results could not be loaded")
    return SuccessResponse(message="Quality execution retrieved", data=result)


@router.post("/{agent_project_id}/workflow/n4/retry", response_model=SuccessResponse[RequirementN4Execution])
def retry_quality_execution(agent_project_id: str,
    service: Annotated[object, Depends(get_requirement_n4_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    standalone: Annotated[StandaloneService, Depends(get_standalone_service)]):
    try:
        require_requirements_project(standalone, agent_project_id, current_user)
        current = service.reconcile(agent_project_id, current_user.user_id)
        if current is None or current.status is not RequirementN4Status.FAILED or not current.retryable:
            raise RequirementN4OrchestrationError("Only the current retryable FAILED N4 execution can be retried")
        execution = service.retry(agent_project_id, current_user.user_id)
    except PROJECT_ERRORS as exc:
        return requirement_project_error(exc, "retrying requirement quality analysis")
    except RequirementN4OrchestrationError as exc:
        return requirement_error(409, "N4 cannot be retried", "quality", str(exc))
    except RequirementWorkflowStorageError:
        return requirement_error(503, "Quality storage failed", "quality", "N4 retry could not be started")
    return SuccessResponse(message="N4 retry accepted", data=execution)
