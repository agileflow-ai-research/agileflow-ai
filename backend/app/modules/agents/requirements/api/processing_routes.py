from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.requirements.api.dependencies import (
    get_requirement_processing_service,
)
from app.modules.agents.requirements.api.errors import (
    requirement_error,
    requirement_project_error,
)
from app.modules.agents.requirements.infrastructure.storage import (
    SourceNotFoundError,
    SourceStorageError,
)
from app.modules.agents.requirements.processing.schemas import (
    DocumentProcessingRecord,
    DocumentProcessingResult,
)
from app.modules.agents.requirements.processing.audio.schemas import (
    AudioProcessingRecord,
    AudioProcessingResult,
)
from app.modules.agents.requirements.processing.audio.service import (
    AudioProcessingNotFoundError,
    AudioProcessingStorageError,
    UnsupportedAudioSourceError,
)
from app.modules.agents.requirements.processing.facade import (
    RequirementProcessingService,
    UnsupportedProcessingSourceError,
)
from app.modules.agents.requirements.processing.service import (
    DocumentProcessingNotFoundError,
    DocumentProcessingStorageError,
    UnsupportedDocumentSourceError,
)
from app.modules.agents.requirements.service import WrongAgentProjectTypeError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
)


router = APIRouter()


def _processing_error(
    status_code: int, message: str, detail: str
) -> JSONResponse:
    return requirement_error(status_code, message, "processing", detail)


@router.post(
    "/{agent_project_id}/sources/{source_id}/processing",
    response_model=SuccessResponse[DocumentProcessingRecord | AudioProcessingRecord],
)
def process_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        RequirementProcessingService, Depends(get_requirement_processing_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentProcessingRecord | AudioProcessingRecord] | JSONResponse:
    try:
        record = service.process(
            agent_project_id, source_id, current_user, force=force
        )
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return requirement_project_error(exc, "processing sources")
    except SourceNotFoundError:
        return _processing_error(
            404, "Requirement source not found", "Requirement source not found"
        )
    except (
        UnsupportedDocumentSourceError,
        UnsupportedAudioSourceError,
        UnsupportedProcessingSourceError,
    ) as exc:
        return _processing_error(422, "Source processing unavailable", str(exc))
    except (
        StandaloneServiceError,
        SourceStorageError,
        DocumentProcessingStorageError,
        AudioProcessingStorageError,
    ):
        return _processing_error(
            503,
            "Source processing unavailable",
            "Source processing storage is unavailable",
        )
    return SuccessResponse(message="Source processing finished", data=record)


@router.get(
    "/{agent_project_id}/sources/{source_id}/processing/status",
    response_model=SuccessResponse[DocumentProcessingRecord | AudioProcessingRecord],
)
def get_processing_status(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        RequirementProcessingService, Depends(get_requirement_processing_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentProcessingRecord | AudioProcessingRecord] | JSONResponse:
    try:
        record = service.get_status(agent_project_id, source_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return requirement_project_error(exc, "reading source processing status")
    except SourceNotFoundError:
        return _processing_error(
            404, "Requirement source not found", "Requirement source not found"
        )
    except (
        UnsupportedDocumentSourceError,
        UnsupportedAudioSourceError,
        UnsupportedProcessingSourceError,
    ) as exc:
        return _processing_error(422, "Source processing unavailable", str(exc))
    except (StandaloneServiceError, SourceStorageError):
        return _processing_error(
            503,
            "Source processing unavailable",
            "Source processing storage is unavailable",
        )
    return SuccessResponse(message="Source processing status retrieved", data=record)


@router.get(
    "/{agent_project_id}/sources/{source_id}/processing/result",
    response_model=SuccessResponse[DocumentProcessingResult | AudioProcessingResult],
)
def get_processing_result(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        RequirementProcessingService, Depends(get_requirement_processing_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentProcessingResult | AudioProcessingResult] | JSONResponse:
    try:
        result = service.get_result(agent_project_id, source_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return requirement_project_error(exc, "reading source processing results")
    except SourceNotFoundError:
        return _processing_error(
            404, "Requirement source not found", "Requirement source not found"
        )
    except (DocumentProcessingNotFoundError, AudioProcessingNotFoundError):
        return _processing_error(
            404,
            "Source processing result not found",
            "No current completed processing result exists for this source",
        )
    except (
        UnsupportedDocumentSourceError,
        UnsupportedAudioSourceError,
        UnsupportedProcessingSourceError,
    ) as exc:
        return _processing_error(422, "Source processing unavailable", str(exc))
    except (StandaloneServiceError, SourceStorageError):
        return _processing_error(
            503,
            "Source processing unavailable",
            "Source processing storage is unavailable",
        )
    return SuccessResponse(message="Source processing result retrieved", data=result)
