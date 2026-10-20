from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.requirements.api.dependencies import (
    get_evidence_preparation_service,
)
from app.modules.agents.requirements.api.errors import (
    requirement_error,
    requirement_project_error,
)
from app.modules.agents.requirements.infrastructure.storage import (
    SourceNotFoundError,
    SourceStorageError,
)
from app.modules.agents.requirements.processing.preparation.schemas import (
    EvidenceChunkResult,
    EvidencePreparationRecord,
    NormalizedEvidenceResult,
)
from app.modules.agents.requirements.processing.preparation.service import (
    EvidencePreparationNotFoundError,
    EvidencePreparationService,
    EvidencePreparationStorageError,
)
from app.modules.agents.requirements.contracts.errors import WrongAgentProjectTypeError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
)


router = APIRouter()


def _error(status_code: int, message: str, detail: str) -> JSONResponse:
    return requirement_error(status_code, message, "preparation", detail)


def _project_error(exc, action):
    return requirement_project_error(exc, action)


@router.post(
    "/{agent_project_id}/sources/{source_id}/preparation",
    response_model=SuccessResponse[EvidencePreparationRecord],
)
def prepare_evidence(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        EvidencePreparationService, Depends(get_evidence_preparation_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[EvidencePreparationRecord] | JSONResponse:
    try:
        record = service.prepare(
            agent_project_id, source_id, current_user, force=force
        )
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return _project_error(exc, "preparing source evidence")
    except SourceNotFoundError:
        return _error(404, "Requirement source not found", "Requirement source not found")
    except (
        StandaloneServiceError,
        SourceStorageError,
        EvidencePreparationStorageError,
    ):
        return _error(
            503,
            "Evidence preparation unavailable",
            "Evidence preparation storage is unavailable",
        )
    return SuccessResponse(message="Source evidence preparation finished", data=record)


@router.get(
    "/{agent_project_id}/sources/{source_id}/preparation/status",
    response_model=SuccessResponse[EvidencePreparationRecord],
)
def get_preparation_status(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        EvidencePreparationService, Depends(get_evidence_preparation_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[EvidencePreparationRecord] | JSONResponse:
    try:
        record = service.get_status(agent_project_id, source_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return _project_error(exc, "reading evidence preparation status")
    except SourceNotFoundError:
        return _error(404, "Requirement source not found", "Requirement source not found")
    except (StandaloneServiceError, SourceStorageError, EvidencePreparationStorageError):
        return _error(
            503,
            "Evidence preparation unavailable",
            "Evidence preparation storage is unavailable",
        )
    return SuccessResponse(message="Evidence preparation status retrieved", data=record)


def _prepared_result(action, loader, agent_project_id, source_id, current_user):
    try:
        value = loader(agent_project_id, source_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return _project_error(exc, action)
    except (SourceNotFoundError, EvidencePreparationNotFoundError):
        return _error(
            404,
            "Prepared evidence not found",
            "Prepare this source before requesting its evidence artifacts",
        )
    except (StandaloneServiceError, SourceStorageError, EvidencePreparationStorageError):
        return _error(
            503,
            "Evidence preparation unavailable",
            "Evidence preparation storage is unavailable",
        )
    return value


@router.get(
    "/{agent_project_id}/sources/{source_id}/preparation/normalized",
    response_model=SuccessResponse[NormalizedEvidenceResult],
)
def get_normalized_evidence(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        EvidencePreparationService, Depends(get_evidence_preparation_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[NormalizedEvidenceResult] | JSONResponse:
    result = _prepared_result(
        "reading normalized evidence",
        service.get_normalized,
        agent_project_id,
        source_id,
        current_user,
    )
    if isinstance(result, JSONResponse):
        return result
    return SuccessResponse(message="Normalized evidence retrieved", data=result)


@router.get(
    "/{agent_project_id}/sources/{source_id}/preparation/chunks",
    response_model=SuccessResponse[EvidenceChunkResult],
)
def get_evidence_chunks(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        EvidencePreparationService, Depends(get_evidence_preparation_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[EvidenceChunkResult] | JSONResponse:
    result = _prepared_result(
        "reading evidence chunks",
        service.get_chunks,
        agent_project_id,
        source_id,
        current_user,
    )
    if isinstance(result, JSONResponse):
        return result
    return SuccessResponse(message="Evidence chunks retrieved", data=result)
