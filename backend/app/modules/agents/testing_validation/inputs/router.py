"""HTTP routes for TEST_GENERATION input collection.

Routes live under /test-generation/sources so the mode is explicit in the path and
VALIDATION never exposes these endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.agents.testing_validation.contracts.enums import (
    Agent4ArtifactType,
    Agent4InputSourceType,
    InputOriginAgent,
)
from app.modules.agents.testing_validation.inputs.constants import MAX_LABEL_CHARACTERS
from app.modules.agents.testing_validation.inputs.schemas import TestGenerationSource, TextSourceCreateRequest
from app.modules.agents.testing_validation.inputs.service import (
    TestGenerationInputService,
    WrongAgentProjectTypeError,
)
from app.modules.agents.testing_validation.inputs.storage import (
    InputNotFoundError,
    InputStorageError,
    InputValidationError,
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


router = APIRouter(prefix="/{agent_project_id}/test-generation/sources", tags=["testing-validation-inputs"])


def get_agent4_input_storage() -> TestGenerationInputStorage:
    return TestGenerationInputStorage(settings.agent4_upload_root)


def get_agent4_input_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    storage: Annotated[TestGenerationInputStorage, Depends(get_agent4_input_storage)],
) -> TestGenerationInputService:
    return TestGenerationInputService(standalone_service, storage)


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=[ErrorDetail(field=field, message=detail)])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _domain_error(exc: Exception) -> JSONResponse | None:
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before changing its inputs")
    if isinstance(exc, WrongAgentProjectTypeError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wrong agent project type", "agent_project_id", str(exc))
    if isinstance(exc, InputNotFoundError):
        return _error(status.HTTP_404_NOT_FOUND, "Input source not found", "source_id", "Input source not found")
    if isinstance(exc, (ValueError, InputValidationError)):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Input validation failed", "source", str(exc))
    if isinstance(exc, (StandaloneServiceError, InputStorageError)):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Input storage failed", "storage", "The source could not be stored")
    return None


@router.get("", response_model=SuccessResponse[list[TestGenerationSource]])
def list_test_generation_sources(
    agent_project_id: str,
    service: Annotated[TestGenerationInputService, Depends(get_agent4_input_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[list[TestGenerationSource]] | JSONResponse:
    try:
        sources = service.list_sources(agent_project_id, current_user)
    except Exception as exc:
        response = _domain_error(exc)
        if response is None:
            raise
        return response
    return SuccessResponse(message="Test generation inputs retrieved", data=sources)


@router.post("/text", response_model=SuccessResponse[TestGenerationSource], status_code=status.HTTP_201_CREATED)
def add_test_generation_text_source(
    agent_project_id: str,
    request: TextSourceCreateRequest,
    service: Annotated[TestGenerationInputService, Depends(get_agent4_input_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[TestGenerationSource] | JSONResponse:
    try:
        source = service.add_text(agent_project_id, current_user, request)
    except Exception as exc:
        response = _domain_error(exc)
        if response is None:
            raise
        return response
    return SuccessResponse(message="Text source added", data=source)


@router.post("/files", response_model=SuccessResponse[TestGenerationSource], status_code=status.HTTP_201_CREATED)
async def add_test_generation_file_source(
    agent_project_id: str,
    artifact_type: Annotated[Agent4ArtifactType, Form()],
    source_type: Annotated[Agent4InputSourceType, Form()],
    file: Annotated[UploadFile, File()],
    service: Annotated[TestGenerationInputService, Depends(get_agent4_input_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    origin_agent: Annotated[InputOriginAgent | None, Form()] = None,
    label: Annotated[str | None, Form(max_length=MAX_LABEL_CHARACTERS)] = None,
) -> SuccessResponse[TestGenerationSource] | JSONResponse:
    try:
        source = await service.add_file(
            agent_project_id, current_user, artifact_type, source_type, origin_agent, label, file,
        )
    except Exception as exc:
        response = _domain_error(exc)
        if response is None:
            raise
        return response
    finally:
        await file.close()
    return SuccessResponse(message="File source added", data=source)


@router.delete("/{source_id}", response_model=SuccessResponse[dict[str, str]])
def delete_test_generation_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[TestGenerationInputService, Depends(get_agent4_input_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[dict[str, str]] | JSONResponse:
    try:
        service.delete_source(agent_project_id, current_user, source_id)
    except Exception as exc:
        response = _domain_error(exc)
        if response is None:
            raise
        return response
    return SuccessResponse(message="Test generation input removed", data={"source_id": source_id})
