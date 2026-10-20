from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.requirements.api.dependencies import (
    get_document_processing_service,
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
from app.modules.agents.requirements.processing.service import (
    DocumentProcessingNotFoundError,
    DocumentProcessingService,
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
    response_model=SuccessResponse[DocumentProcessingRecord],
)
def process_document_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        DocumentProcessingService, Depends(get_document_processing_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentProcessingRecord] | JSONResponse:
    try:
        record = service.process(
            agent_project_id, source_id, current_user, force=force
        )
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return requirement_project_error(exc, "processing documents")
    except SourceNotFoundError:
        return _processing_error(
            404, "Requirement source not found", "Requirement source not found"
        )
    except UnsupportedDocumentSourceError as exc:
        return _processing_error(422, "Document processing unavailable", str(exc))
    except (
        StandaloneServiceError,
        SourceStorageError,
        DocumentProcessingStorageError,
    ):
        return _processing_error(
            503,
            "Document processing unavailable",
            "Document processing storage is unavailable",
        )
    return SuccessResponse(message="Document processing finished", data=record)


@router.get(
    "/{agent_project_id}/sources/{source_id}/processing/status",
    response_model=SuccessResponse[DocumentProcessingRecord],
)
def get_document_processing_status(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        DocumentProcessingService, Depends(get_document_processing_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentProcessingRecord] | JSONResponse:
    try:
        record = service.get_status(agent_project_id, source_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return requirement_project_error(exc, "reading document processing status")
    except SourceNotFoundError:
        return _processing_error(
            404, "Requirement source not found", "Requirement source not found"
        )
    except UnsupportedDocumentSourceError as exc:
        return _processing_error(422, "Document processing unavailable", str(exc))
    except (StandaloneServiceError, SourceStorageError):
        return _processing_error(
            503,
            "Document processing unavailable",
            "Document processing storage is unavailable",
        )
    return SuccessResponse(message="Document processing status retrieved", data=record)


@router.get(
    "/{agent_project_id}/sources/{source_id}/processing/result",
    response_model=SuccessResponse[DocumentProcessingResult],
)
def get_document_processing_result(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        DocumentProcessingService, Depends(get_document_processing_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentProcessingResult] | JSONResponse:
    try:
        result = service.get_result(agent_project_id, source_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
    ) as exc:
        return requirement_project_error(exc, "reading document processing results")
    except SourceNotFoundError:
        return _processing_error(
            404, "Requirement source not found", "Requirement source not found"
        )
    except (DocumentProcessingNotFoundError,):
        return _processing_error(
            404,
            "Document processing result not found",
            "No current completed processing result exists for this source",
        )
    except UnsupportedDocumentSourceError as exc:
        return _processing_error(422, "Document processing unavailable", str(exc))
    except (StandaloneServiceError, SourceStorageError):
        return _processing_error(
            503,
            "Document processing unavailable",
            "Document processing storage is unavailable",
        )
    return SuccessResponse(message="Document processing result retrieved", data=result)
