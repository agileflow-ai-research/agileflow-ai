"""Authoritative project-level implementation readiness routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.implementation.api.dependencies import get_trusted_readiness_service
from app.modules.agents.implementation.api.errors import _error
from app.modules.agents.implementation.inputs.upload.service import WrongAgentProjectTypeError
from app.modules.agents.implementation.preparation.consolidation.service import ConsolidationNotFoundError
from app.modules.agents.implementation.preparation.consolidation.storage import ConsolidationStorageError
from app.modules.agents.implementation.preparation.readiness.trusted.schemas import (
    TrustedReadinessEvaluationRequest,
    TrustedReadinessSnapshot,
)
from app.modules.agents.implementation.preparation.readiness.trusted.service import (
    StaleStackAdaptationError,
    TrustedReadinessNotFoundError,
    TrustedReadinessService,
)
from app.modules.agents.implementation.preparation.readiness.trusted.storage import TrustedReadinessStorageError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (AgentProjectNotFoundError,
                                            ArchivedAgentProjectError,
                                            StandaloneServiceError)


router = APIRouter()


def _service_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the project before evaluating readiness")
    if isinstance(exc, WrongAgentProjectTypeError):
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    if isinstance(exc, TrustedReadinessNotFoundError):
        return _error(404, "Trusted readiness not found", "trusted_readiness", "No trusted readiness evaluation exists")
    if isinstance(exc, StaleStackAdaptationError):
        return _error(409, "Stack adaptation is stale", "stack_adaptation", str(exc))
    return _error(503, "Trusted readiness unavailable", "trusted_readiness", "Trusted readiness storage is unavailable")


SERVICE_ERRORS = (
    AgentProjectNotFoundError, ArchivedAgentProjectError,
    WrongAgentProjectTypeError, StandaloneServiceError,
    ConsolidationNotFoundError, ConsolidationStorageError,
    TrustedReadinessStorageError, TrustedReadinessNotFoundError,
    StaleStackAdaptationError,
)


@router.post(
    "/{agent_project_id}/trusted-readiness/evaluate",
    response_model=SuccessResponse[TrustedReadinessSnapshot],
)
def evaluate_trusted_readiness(
    agent_project_id: str,
    request: TrustedReadinessEvaluationRequest,
    service: Annotated[TrustedReadinessService, Depends(get_trusted_readiness_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[TrustedReadinessSnapshot] | JSONResponse:
    try:
        result = service.evaluate(agent_project_id, request, current_user)
    except SERVICE_ERRORS as exc:
        return _service_error(exc)
    return SuccessResponse(message="Trusted implementation readiness evaluated", data=result)


@router.get(
    "/{agent_project_id}/trusted-readiness",
    response_model=SuccessResponse[TrustedReadinessSnapshot],
)
def get_trusted_readiness(
    agent_project_id: str,
    service: Annotated[TrustedReadinessService, Depends(get_trusted_readiness_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[TrustedReadinessSnapshot] | JSONResponse:
    try:
        result = service.get(agent_project_id, current_user)
    except SERVICE_ERRORS as exc:
        return _service_error(exc)
    return SuccessResponse(message="Trusted implementation readiness retrieved", data=result)
