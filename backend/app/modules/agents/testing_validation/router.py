from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.model_provider import build_model_provider
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)
from app.modules.agents.testing_validation.engine import Agent4Engine
from app.modules.agents.testing_validation.schemas import Agent4RunRequest, Agent4RunResult
from app.modules.agents.testing_validation.service import Agent4Service, WrongAgentProjectTypeError
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4TestGenerationWorkflowResponse,
)
from app.modules.agents.testing_validation.workflow.service import (
    Agent4WorkflowService,
    Agent4WorkflowStageError,
    WrongAgent4WorkflowProjectError,
)
from app.modules.agents.testing_validation.workflow.storage import (
    Agent4WorkflowStorage,
    Agent4WorkflowStorageError,
)


router = APIRouter(prefix="/agents/testing-validation", tags=["testing-validation-agent"])


def get_agent4_engine() -> Agent4Engine:
    return Agent4Engine(build_model_provider(settings))


def get_agent4_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    engine: Annotated[Agent4Engine, Depends(get_agent4_engine)],
) -> Agent4Service:
    return Agent4Service(standalone_service, engine)


def get_agent4_workflow_storage() -> Agent4WorkflowStorage:
    return Agent4WorkflowStorage(settings.agent4_storage_root)


def get_agent4_workflow_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    workflow_storage: Annotated[
        Agent4WorkflowStorage, Depends(get_agent4_workflow_storage)
    ],
) -> Agent4WorkflowService:
    return Agent4WorkflowService(standalone_service, workflow_storage)


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=[ErrorDetail(field=field, message=detail)])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


@router.get(
    "/{agent_project_id}/test-generation/workflow",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def get_test_generation_workflow(
    agent_project_id: str,
    service: Annotated[
        Agent4WorkflowService, Depends(get_agent4_workflow_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4TestGenerationWorkflowResponse] | JSONResponse:
    try:
        workflow = service.get(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before loading its workflow",
        )
    except WrongAgent4WorkflowProjectError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except Agent4WorkflowStageError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project stage is unavailable",
            "agent_stage",
            str(exc),
        )
    except Agent4WorkflowStorageError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Workflow storage failed",
            "workflow",
            "The Agent 4 workflow could not be loaded",
        )
    except ValueError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project storage failed",
            "database",
            "The Agent 4 project could not be loaded",
        )
    return SuccessResponse(
        message="Agent 4 Test Generation workflow retrieved", data=workflow
    )


@router.post("/{agent_project_id}/run", response_model=SuccessResponse[Agent4RunResult])
def run_testing_validation_agent(
    agent_project_id: str,
    request: Agent4RunRequest,
    service: Annotated[Agent4Service, Depends(get_agent4_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4RunResult] | JSONResponse:
    try:
        result = service.run(agent_project_id, request, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before running it")
    except WrongAgentProjectTypeError as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wrong agent project type", "agent_project_id", str(exc))
    except ValueError as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Validation failed", "agent_project_id", str(exc))
    except StandaloneServiceError:
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Agent run persistence failed", "database", "Standalone run storage is unavailable")
    return SuccessResponse(message="Testing and validation agent run finished", data=result)
