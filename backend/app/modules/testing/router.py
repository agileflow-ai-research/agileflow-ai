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
from app.modules.testing.engine import Agent4Engine
from app.modules.testing.schemas import Agent4RunRequest, Agent4RunResult
from app.modules.testing.service import Agent4Service, WrongAgentProjectTypeError


router = APIRouter(prefix="/agents/testing-validation", tags=["testing-validation-agent"])


def get_agent4_engine() -> Agent4Engine:
    return Agent4Engine(build_model_provider(settings))


def get_agent4_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    engine: Annotated[Agent4Engine, Depends(get_agent4_engine)],
) -> Agent4Service:
    return Agent4Service(standalone_service, engine)


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=[ErrorDetail(field=field, message=detail)])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


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
