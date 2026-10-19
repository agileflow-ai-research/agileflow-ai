"""HTTP routes for Agent 4 DOCUMENT extraction. They sit under the source resource so the mode is explicit."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.agents.testing_validation.extraction.schemas import TestGenerationExtractionResult
from app.modules.agents.testing_validation.extraction.service import (
    TestGenerationExtractionService,
    UnsupportedExtractionSourceError,
    WrongAgentProjectTypeError,
)
from app.modules.agents.testing_validation.inputs.router import get_agent4_input_storage
from app.modules.agents.testing_validation.inputs.storage import (
    InputNotFoundError,
    InputStorageError,
    TestGenerationInputStorage,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)


router = APIRouter(prefix="/{agent_project_id}/test-generation/sources", tags=["testing-validation-extraction"])


def get_agent4_extraction_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    storage: Annotated[TestGenerationInputStorage, Depends(get_agent4_input_storage)],
) -> TestGenerationExtractionService:
    return TestGenerationExtractionService(standalone_service, storage)


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=[ErrorDetail(field=field, message=detail)])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _domain_error(exc: Exception, *, action: str) -> JSONResponse | None:
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", f"Reactivate the agent project before {action}")
    if isinstance(exc, WrongAgentProjectTypeError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wrong agent project type", "agent_project_id", str(exc))
    if isinstance(exc, InputNotFoundError):
        return _error(status.HTTP_404_NOT_FOUND, "Extraction not found", "source_id", "No valid extraction exists for this source")
    if isinstance(exc, UnsupportedExtractionSourceError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Document extraction unavailable", "source_id", str(exc))
    if isinstance(exc, (StandaloneServiceError, InputStorageError)):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Document extraction unavailable", "storage", "Document extraction storage is unavailable")
    return None


@router.post("/{source_id}/extract", response_model=SuccessResponse[TestGenerationExtractionResult])
def extract_test_generation_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[TestGenerationExtractionService, Depends(get_agent4_extraction_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[TestGenerationExtractionResult] | JSONResponse:
    try:
        result = service.extract(agent_project_id, source_id, current_user, force=force)
    except Exception as exc:
        response = _domain_error(exc, action="extracting documents")
        if response is None:
            raise
        return response
    return SuccessResponse(message="Document extraction completed", data=result)


@router.get("/{source_id}/extraction", response_model=SuccessResponse[TestGenerationExtractionResult])
def get_test_generation_extraction(
    agent_project_id: str,
    source_id: str,
    service: Annotated[TestGenerationExtractionService, Depends(get_agent4_extraction_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[TestGenerationExtractionResult] | JSONResponse:
    try:
        result = service.get_existing(agent_project_id, source_id, current_user)
    except Exception as exc:
        response = _domain_error(exc, action="reading extraction")
        if response is None:
            raise
        return response
    return SuccessResponse(message="Document extraction retrieved", data=result)
