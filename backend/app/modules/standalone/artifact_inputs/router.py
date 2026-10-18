from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.artifact_inputs.schemas import (
    ArtifactExtractionResponse,
    ArtifactUploadDeleteResponse,
    ArtifactUploadResponse,
)
from app.modules.standalone.artifact_inputs.service import (
    ArtifactAgentTypeError,
    ExtractionNotFoundError,
    ExtractionStorageError,
    StandaloneArtifactService,
    UnsupportedExtractionSourceError,
)
from app.modules.standalone.artifact_inputs.storage import (
    ArtifactUploadStorage,
    UploadNotFoundError,
    UploadStorageError,
)
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)


router = APIRouter(prefix="/agent-projects", tags=["standalone-artifact-uploads"])


def get_artifact_upload_storage() -> ArtifactUploadStorage:
    return ArtifactUploadStorage(settings.standalone_artifact_upload_root)


def get_standalone_artifact_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    storage: Annotated[ArtifactUploadStorage, Depends(get_artifact_upload_storage)],
) -> StandaloneArtifactService:
    return StandaloneArtifactService(standalone_service, storage)


ArtifactServiceDependency = Annotated[StandaloneArtifactService, Depends(get_standalone_artifact_service)]
CurrentUserDependency = Annotated[UserPublicResponse, Depends(get_current_user)]


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=[ErrorDetail(field=field, message=detail)])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _failure(exc: Exception) -> JSONResponse:
    """Maps service failures to explicit responses. Messages never include storage paths."""
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before uploading artifacts")
    if isinstance(exc, (UploadNotFoundError, ExtractionNotFoundError)):
        return _error(status.HTTP_404_NOT_FOUND, "Artifact upload not found", "upload_id", "No matching upload exists for this agent project")
    if isinstance(exc, (UploadStorageError, ExtractionStorageError, StandaloneServiceError)):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Artifact storage failed", "storage", "Artifact upload storage is unavailable")
    if isinstance(exc, ArtifactAgentTypeError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unsupported agent project", "agent_project_id", str(exc))
    if isinstance(exc, UnsupportedExtractionSourceError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Extraction not available", "upload_id", str(exc))
    if isinstance(exc, ValueError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Validation failed", "file", str(exc))
    raise exc


@router.post(
    "/{agent_project_id}/artifact-uploads",
    response_model=SuccessResponse[ArtifactUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_artifact(
    agent_project_id: str,
    service: ArtifactServiceDependency,
    current_user: CurrentUserDependency,
    source_type: Annotated[str, Form()],
    artifact_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    label: Annotated[str | None, Form()] = None,
) -> SuccessResponse[ArtifactUploadResponse] | JSONResponse:
    try:
        data = await service.upload(
            agent_project_id,
            current_user,
            source_type=source_type,
            artifact_type=artifact_type,
            label=label,
            upload=file,
        )
    except (AgentProjectNotFoundError, ArchivedAgentProjectError, StandaloneServiceError, UploadStorageError, ValueError) as exc:
        return _failure(exc)
    return SuccessResponse(message="Artifact uploaded", data=data)


@router.delete(
    "/{agent_project_id}/artifact-uploads/{upload_id}",
    response_model=SuccessResponse[ArtifactUploadDeleteResponse],
)
def delete_artifact(
    agent_project_id: str,
    upload_id: str,
    service: ArtifactServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[ArtifactUploadDeleteResponse] | JSONResponse:
    try:
        service.delete(agent_project_id, current_user, upload_id)
    except (AgentProjectNotFoundError, ArchivedAgentProjectError, StandaloneServiceError, UploadNotFoundError, UploadStorageError, ValueError) as exc:
        return _failure(exc)
    return SuccessResponse(
        message="Artifact upload removed",
        data=ArtifactUploadDeleteResponse(upload_id=upload_id, deleted=True),
    )


@router.post(
    "/{agent_project_id}/artifact-uploads/{upload_id}/extraction",
    response_model=SuccessResponse[ArtifactExtractionResponse],
)
def extract_artifact_document(
    agent_project_id: str,
    upload_id: str,
    service: ArtifactServiceDependency,
    current_user: CurrentUserDependency,
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[ArtifactExtractionResponse] | JSONResponse:
    try:
        data = service.extract(agent_project_id, current_user, upload_id, force=force)
    except (
        AgentProjectNotFoundError, ArchivedAgentProjectError, StandaloneServiceError,
        UploadNotFoundError, UploadStorageError, ExtractionStorageError,
        UnsupportedExtractionSourceError, ValueError,
    ) as exc:
        return _failure(exc)
    return SuccessResponse(message="Document extraction finished", data=data)


@router.get(
    "/{agent_project_id}/artifact-uploads/{upload_id}/extraction",
    response_model=SuccessResponse[ArtifactExtractionResponse],
)
def get_artifact_document_extraction(
    agent_project_id: str,
    upload_id: str,
    service: ArtifactServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[ArtifactExtractionResponse] | JSONResponse:
    try:
        data = service.get_existing(agent_project_id, current_user, upload_id)
    except (
        AgentProjectNotFoundError, ArchivedAgentProjectError, StandaloneServiceError,
        UploadNotFoundError, UploadStorageError, ExtractionNotFoundError,
        UnsupportedExtractionSourceError, ValueError,
    ) as exc:
        return _failure(exc)
    return SuccessResponse(message="Document extraction loaded", data=data)
