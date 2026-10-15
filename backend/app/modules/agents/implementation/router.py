from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.agents.implementation.schemas import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)
from app.modules.agents.implementation.service import (
    ImplementationInputService,
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.storage import (
    ImplementationUploadStorage,
    UploadNotFoundError,
    UploadStorageError,
    UploadValidationError,
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


router = APIRouter(
    prefix="/agents/implementation", tags=["implementation-agent"]
)


def get_implementation_upload_storage() -> ImplementationUploadStorage:
    return ImplementationUploadStorage(settings.agent3_upload_root)


def get_implementation_input_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> ImplementationInputService:
    return ImplementationInputService(standalone_service, storage)


def _error(
    status_code: int,
    message: str,
    field: str,
    detail: str,
) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=detail)],
    )
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


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
