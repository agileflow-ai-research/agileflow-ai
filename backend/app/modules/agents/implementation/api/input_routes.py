"""Agent 3 HTTP routes grouped by responsibility."""

from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.agents.implementation.inputs.extraction.schemas import (
    DocumentExtractionResult,
)
from app.modules.agents.implementation.inputs.extraction.service import (
    DocumentExtractionService,
    ExtractionNotFoundError,
    ExtractionStorageError,
    UnsupportedExtractionSourceError,
)
from app.modules.agents.implementation.contracts.schemas import (
    GitHubConnectionStatus,
    GitHubConnectResponse,
    GitHubRepositoryCreateRequest,
    GitHubRepositoryStatus,
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)
from app.modules.agents.implementation.inputs.upload.service import (
    ImplementationInputService,
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.infrastructure.storage import (
    ImplementationUploadStorage,
    UploadNotFoundError,
    UploadStorageError,
    UploadValidationError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)
from app.modules.agents.implementation.api.dependencies import (
    get_document_extraction_service,
    get_implementation_input_service,
)
from app.modules.agents.implementation.api.errors import (
    _error,
)


router = APIRouter()


@router.post(
    "/{agent_project_id}/input-files",
    response_model=SuccessResponse[UploadedFileMetadata],
    status_code=status.HTTP_201_CREATED,
)
async def upload_implementation_input_file(
    agent_project_id: str,
    source_type: Annotated[ImplementationInputSourceType, Form()],
    artifact_type: Annotated[ImplementationArtifactType, Form()],
    file: Annotated[UploadFile, File()],
    service: Annotated[
        ImplementationInputService,
        Depends(get_implementation_input_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    label: Annotated[str | None, Form(max_length=200)] = None,
) -> SuccessResponse[UploadedFileMetadata] | JSONResponse:
    try:
        metadata = await service.upload(
            agent_project_id,
            current_user,
            source_type,
            artifact_type,
            label,
            file,
        )
    except AgentProjectNotFoundError:
        return _error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before uploading files",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except (ValueError, UploadValidationError) as exc:
        return _error(422, "Upload validation failed", "file", str(exc))
    except (StandaloneServiceError, UploadStorageError):
        return _error(
            503,
            "Upload storage failed",
            "storage",
            "The staged upload could not be stored",
        )
    finally:
        await file.close()
    return SuccessResponse(
        message="Implementation input file uploaded", data=metadata
    )


@router.delete(
    "/{agent_project_id}/input-files/{upload_id}",
    response_model=SuccessResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
)
def delete_implementation_input_file(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        ImplementationInputService,
        Depends(get_implementation_input_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[dict[str, str]] | JSONResponse:
    try:
        service.delete(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before deleting files",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except UploadNotFoundError:
        return _error(
            404, "Upload not found", "upload_id", "Staged upload not found"
        )
    except (StandaloneServiceError, UploadStorageError):
        return _error(
            503,
            "Upload storage failed",
            "storage",
            "The staged upload could not be deleted",
        )
    return SuccessResponse(
        message="Implementation input file deleted",
        data={"upload_id": upload_id},
    )


def _extraction_error(
    status_code: int, message: str, detail: str
) -> JSONResponse:
    return _error(status_code, message, "extraction", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/extract",
    response_model=SuccessResponse[DocumentExtractionResult],
)
def extract_implementation_document(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        DocumentExtractionService, Depends(get_document_extraction_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentExtractionResult] | JSONResponse:
    try:
        extraction = service.extract(
            agent_project_id,
            upload_id,
            current_user,
            force=force,
        )
    except AgentProjectNotFoundError:
        return _error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before extracting documents",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except UploadNotFoundError:
        return _extraction_error(404, "Upload not found", "Staged upload not found")
    except UnsupportedExtractionSourceError as exc:
        return _extraction_error(
            422, "Document extraction unavailable", str(exc)
        )
    except (StandaloneServiceError, UploadStorageError, ExtractionStorageError):
        return _extraction_error(
            503,
            "Document extraction unavailable",
            "Document extraction storage is unavailable",
        )
    return SuccessResponse(message="Document extraction completed", data=extraction)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/extraction",
    response_model=SuccessResponse[DocumentExtractionResult],
)
def get_implementation_document_extraction(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        DocumentExtractionService, Depends(get_document_extraction_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentExtractionResult] | JSONResponse:
    try:
        extraction = service.get_existing(
            agent_project_id, upload_id, current_user
        )
    except AgentProjectNotFoundError:
        return _error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before reviewing extraction",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except (UploadNotFoundError, ExtractionNotFoundError):
        return _extraction_error(
            404,
            "Extraction not found",
            "No valid extraction exists for this upload",
        )
    except UnsupportedExtractionSourceError as exc:
        return _extraction_error(
            422, "Document extraction unavailable", str(exc)
        )
    except (StandaloneServiceError, UploadStorageError):
        return _extraction_error(
            503,
            "Document extraction unavailable",
            "Document extraction storage is unavailable",
        )
    return SuccessResponse(message="Document extraction retrieved", data=extraction)


