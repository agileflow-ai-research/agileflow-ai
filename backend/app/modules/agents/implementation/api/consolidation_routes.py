"""Project-level trusted specification consolidation routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.implementation.api.dependencies import (
    get_project_consolidation_service,
)
from app.modules.agents.implementation.api.errors import _error
from app.modules.agents.implementation.infrastructure.storage import (
    UploadStorageError,
)
from app.modules.agents.implementation.inputs.upload.service import (
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.preparation.consolidation.schemas import (
    ConflictDecisionRequest,
    ProjectConflict,
    ProjectConsolidationStatusResponse,
    TrustedProjectSpecification,
)
from app.modules.agents.implementation.preparation.consolidation.service import (
    ConflictNotFoundError,
    ConsolidationNotFoundError,
    InvalidConflictDecisionError,
    ProjectConsolidationService,
    StaleConflictDecisionError,
)
from app.modules.agents.implementation.preparation.consolidation.storage import (
    ConsolidationStorageError,
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

SERVICE_ERRORS = (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    WrongAgentProjectTypeError,
    StandaloneServiceError,
    UploadStorageError,
    ProjectPreparationStorageError,
    ConsolidationStorageError,
)


def _common_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(404, "Agent project not found", "agent_project_id",
                      "Agent project not found")
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(409, "Agent project is archived", "agent_project_id",
                      "Reactivate the project before consolidation")
    if isinstance(exc, WrongAgentProjectTypeError):
        return _error(422, "Wrong agent project type", "agent_project_id",
                      str(exc))
    if isinstance(exc, ConsolidationNotFoundError):
        return _error(404, "Project specification not found",
                      "project_specification",
                      "No current trusted project specification exists")
    return _error(503, "Project consolidation unavailable", "consolidation",
                  "Project consolidation storage is unavailable")


@router.post(
    "/{agent_project_id}/project-specification/start",
    response_model=SuccessResponse[ProjectConsolidationStatusResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def start_project_consolidation(
    agent_project_id: str,
    service: Annotated[
        ProjectConsolidationService,
        Depends(get_project_consolidation_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        result = service.start(agent_project_id, current_user)
    except SERVICE_ERRORS as exc:
        return _common_error(exc)
    return SuccessResponse(message="Project consolidation completed", data=result)


@router.get(
    "/{agent_project_id}/project-specification/status",
    response_model=SuccessResponse[ProjectConsolidationStatusResponse],
)
def get_project_consolidation_status(
    agent_project_id: str,
    service: Annotated[
        ProjectConsolidationService,
        Depends(get_project_consolidation_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        result = service.get_status(agent_project_id, current_user)
    except SERVICE_ERRORS as exc:
        return _common_error(exc)
    return SuccessResponse(message="Project consolidation status retrieved",
                           data=result)


@router.get(
    "/{agent_project_id}/project-specification/conflicts",
    response_model=SuccessResponse[list[ProjectConflict]],
)
def get_project_conflicts(
    agent_project_id: str,
    service: Annotated[
        ProjectConsolidationService,
        Depends(get_project_consolidation_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        result = service.get_conflicts(agent_project_id, current_user)
    except (*SERVICE_ERRORS, ConsolidationNotFoundError) as exc:
        return _common_error(exc)
    return SuccessResponse(message="Project conflicts retrieved", data=result)


@router.put(
    "/{agent_project_id}/project-specification/conflicts/{conflict_id}",
    response_model=SuccessResponse[ProjectConflict],
)
def save_project_conflict_decision(
    agent_project_id: str,
    conflict_id: str,
    request: ConflictDecisionRequest,
    service: Annotated[
        ProjectConsolidationService,
        Depends(get_project_consolidation_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        result = service.decide(
            agent_project_id, conflict_id, request, current_user
        )
    except ConflictNotFoundError:
        return _error(404, "Conflict not found", "conflict_id",
                      "Current project conflict not found")
    except StaleConflictDecisionError as exc:
        return _error(409, "Project conflict is stale", "conflict",
                      str(exc))
    except InvalidConflictDecisionError as exc:
        return _error(422, "Invalid conflict decision", "action", str(exc))
    except SERVICE_ERRORS as exc:
        return _common_error(exc)
    return SuccessResponse(message="Project conflict decision saved",
                           data=result)


@router.get(
    "/{agent_project_id}/project-specification",
    response_model=SuccessResponse[TrustedProjectSpecification],
)
def get_trusted_project_specification(
    agent_project_id: str,
    service: Annotated[
        ProjectConsolidationService,
        Depends(get_project_consolidation_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        result = service.get_final(agent_project_id, current_user)
    except (*SERVICE_ERRORS, ConsolidationNotFoundError) as exc:
        return _common_error(exc)
    return SuccessResponse(message="Trusted project specification retrieved",
                           data=result)
