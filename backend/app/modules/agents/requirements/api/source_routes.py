from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.requirements.api.dependencies import get_requirement_source_service
from app.modules.agents.requirements.api.errors import (
    requirement_error,
    requirement_project_error,
)
from app.modules.agents.requirements.contracts.schemas import (
    RequirementSourceMetadata,
    RequirementSourceType,
)
from app.modules.agents.requirements.infrastructure.storage import (
    SourceNotFoundError,
    SourceStorageError,
    SourceValidationError,
)
from app.modules.agents.requirements.inputs.upload.service import RequirementSourceService
from app.modules.agents.requirements.service import WrongAgentProjectTypeError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
)


router = APIRouter()


@router.post(
    "/{agent_project_id}/sources",
    response_model=SuccessResponse[RequirementSourceMetadata],
    status_code=status.HTTP_201_CREATED,
)
async def upload_requirement_source(
    agent_project_id: str,
    source_type: Annotated[RequirementSourceType, Form()],
    file: Annotated[UploadFile, File()],
    service: Annotated[RequirementSourceService, Depends(get_requirement_source_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[RequirementSourceMetadata] | JSONResponse:
    try:
        metadata = await service.upload(agent_project_id, current_user, source_type, file)
    except (AgentProjectNotFoundError, ArchivedAgentProjectError, WrongAgentProjectTypeError) as exc:
        return requirement_project_error(exc, "uploading sources")
    except SourceValidationError as exc:
        return requirement_error(422, "Source validation failed", "file", str(exc))
    except (StandaloneServiceError, SourceStorageError):
        return requirement_error(503, "Source storage failed", "storage", "The requirement source could not be stored")
    finally:
        await file.close()
    return SuccessResponse(message="Requirement source uploaded", data=metadata)


@router.get(
    "/{agent_project_id}/sources",
    response_model=SuccessResponse[list[RequirementSourceMetadata]],
)
def list_requirement_sources(
    agent_project_id: str,
    service: Annotated[RequirementSourceService, Depends(get_requirement_source_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[list[RequirementSourceMetadata]] | JSONResponse:
    try:
        sources = service.list(agent_project_id, current_user)
    except (AgentProjectNotFoundError, ArchivedAgentProjectError, WrongAgentProjectTypeError) as exc:
        return requirement_project_error(exc, "listing sources")
    except (StandaloneServiceError, SourceStorageError, SourceNotFoundError):
        return requirement_error(503, "Source storage failed", "storage", "Requirement sources could not be listed")
    return SuccessResponse(message="Requirement sources retrieved", data=sources)


@router.delete(
    "/{agent_project_id}/sources/{source_id}",
    response_model=SuccessResponse[dict[str, str]],
)
def delete_requirement_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[RequirementSourceService, Depends(get_requirement_source_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[dict[str, str]] | JSONResponse:
    try:
        service.delete(agent_project_id, source_id, current_user)
    except (AgentProjectNotFoundError, ArchivedAgentProjectError, WrongAgentProjectTypeError) as exc:
        return requirement_project_error(exc, "removing sources")
    except SourceNotFoundError:
        return requirement_error(404, "Requirement source not found", "source_id", "Requirement source not found")
    except (StandaloneServiceError, SourceStorageError):
        return requirement_error(503, "Source storage failed", "storage", "The requirement source could not be removed")
    return SuccessResponse(
        message="Requirement source removed", data={"source_id": source_id}
    )
