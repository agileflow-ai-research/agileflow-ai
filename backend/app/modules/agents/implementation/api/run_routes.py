"""Final pre-code approval and immutable Agent 3 run routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.implementation.api.dependencies import get_implementation_run_service
from app.modules.agents.implementation.api.errors import _error
from app.modules.agents.implementation.inputs.upload.service import WrongAgentProjectTypeError
from app.modules.agents.implementation.preparation.consolidation.service import (
    ConsolidationNotFoundError,
)
from app.modules.agents.implementation.preparation.consolidation.storage import (
    ConsolidationStorageError,
)
from app.modules.agents.implementation.preparation.readiness.trusted.service import (
    TrustedReadinessNotFoundError,
)
from app.modules.agents.implementation.preparation.readiness.trusted.storage import (
    TrustedReadinessStorageError,
)
from app.modules.agents.implementation.runs.schemas import (
    ImplementationRunCreateRequest,
    ImplementationRunListItem,
    ImplementationRunResponse,
)
from app.modules.agents.implementation.runs.service import (
    ImplementationRunApprovalError,
    ImplementationRunNotFoundError,
    ImplementationRunService,
    ImplementationRunStorageError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
)


router = APIRouter()


def _service_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    if isinstance(exc, ImplementationRunNotFoundError):
        return _error(
            404,
            "Implementation run not found",
            "run_id",
            "Implementation run not found",
        )
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the project before approving implementation")
    if isinstance(exc, WrongAgentProjectTypeError):
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    if isinstance(exc, ImplementationRunApprovalError):
        return _error(409, "Implementation approval rejected", "approval", f"{exc.code}: {exc}")
    return _error(503, "Implementation runs unavailable", "agent_run", "Implementation run storage is unavailable")


SERVICE_ERRORS = (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    WrongAgentProjectTypeError,
    StandaloneServiceError,
    ImplementationRunApprovalError,
    ImplementationRunNotFoundError,
    ImplementationRunStorageError,
    ConsolidationNotFoundError,
    ConsolidationStorageError,
    TrustedReadinessNotFoundError,
    TrustedReadinessStorageError,
)


@router.post(
    "/{agent_project_id}/runs",
    response_model=SuccessResponse[ImplementationRunResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_implementation_run(
    agent_project_id: str,
    request: ImplementationRunCreateRequest,
    service: Annotated[ImplementationRunService, Depends(get_implementation_run_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[ImplementationRunResponse] | JSONResponse:
    try:
        result, replayed = service.create(agent_project_id, request, current_user)
    except SERVICE_ERRORS as exc:
        return _service_error(exc)
    return SuccessResponse(
        message="Existing approved implementation run returned" if replayed else "Implementation approved and immutable AgentRun created",
        data=result,
    )


@router.get(
    "/{agent_project_id}/runs",
    response_model=SuccessResponse[list[ImplementationRunListItem]],
)
def list_implementation_runs(
    agent_project_id: str,
    service: Annotated[ImplementationRunService, Depends(get_implementation_run_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[list[ImplementationRunListItem]] | JSONResponse:
    try:
        result = service.list(agent_project_id, current_user)
    except SERVICE_ERRORS as exc:
        return _service_error(exc)
    return SuccessResponse(message="Implementation runs retrieved", data=result)


@router.get(
    "/{agent_project_id}/runs/{run_id}",
    response_model=SuccessResponse[ImplementationRunResponse],
)
def get_implementation_run(
    agent_project_id: str,
    run_id: str,
    service: Annotated[ImplementationRunService, Depends(get_implementation_run_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[ImplementationRunResponse] | JSONResponse:
    try:
        result = service.get(agent_project_id, run_id, current_user)
    except SERVICE_ERRORS as exc:
        return _service_error(exc)
    return SuccessResponse(message="Implementation run retrieved", data=result)
