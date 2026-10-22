"""Project-level automation routes over Agent 3 file primitives."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.implementation.api.dependencies import (
    get_project_preparation_service,
)
from app.modules.agents.implementation.api.errors import _error
from app.modules.agents.implementation.infrastructure.storage import (
    UploadStorageError,
)
from app.modules.agents.implementation.inputs.upload.service import (
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.preparation.orchestration.schemas import (
    ProjectPreparationStartRequest,
    ProjectPreparationStatusResponse,
)
from app.modules.agents.implementation.preparation.orchestration.service import (
    ProjectPreparationService,
)
from app.modules.agents.implementation.preparation.orchestration.storage import (
    ProjectPreparationStorageError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
)


router = APIRouter()


def _handle_preparation_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before analyzing its inputs",
        )
    if isinstance(exc, WrongAgentProjectTypeError):
        return _error(
            422,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    return _error(
        503,
        "Project input analysis unavailable",
        "preparation",
        "Project preparation state is temporarily unavailable",
    )


@router.post(
    "/{agent_project_id}/preparation/start",
    response_model=SuccessResponse[ProjectPreparationStatusResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def start_project_preparation(
    agent_project_id: str,
    request: ProjectPreparationStartRequest,
    service: Annotated[
        ProjectPreparationService, Depends(get_project_preparation_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[ProjectPreparationStatusResponse] | JSONResponse:
    try:
        result = service.start(agent_project_id, request, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
        StandaloneServiceError,
        UploadStorageError,
        ProjectPreparationStorageError,
    ) as exc:
        return _handle_preparation_error(exc)
    return SuccessResponse(message="Project input analysis started", data=result)


@router.get(
    "/{agent_project_id}/preparation/status",
    response_model=SuccessResponse[ProjectPreparationStatusResponse],
)
def get_project_preparation_status(
    agent_project_id: str,
    service: Annotated[
        ProjectPreparationService, Depends(get_project_preparation_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[ProjectPreparationStatusResponse] | JSONResponse:
    try:
        result = service.get_status(agent_project_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
        StandaloneServiceError,
        UploadStorageError,
        ProjectPreparationStorageError,
    ) as exc:
        return _handle_preparation_error(exc)
    return SuccessResponse(message="Project input analysis status retrieved", data=result)
