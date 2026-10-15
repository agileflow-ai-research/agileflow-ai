from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from urllib.parse import urlencode

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.agents.implementation.schemas import (
    GitHubConnectionStatus,
    GitHubConnectResponse,
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)
from app.modules.agents.implementation.github import (
    GitHubApiClient,
    GitHubCallbackError,
    GitHubConfiguration,
    GitHubConfigurationError,
    GitHubConnectionService,
    GitHubStateError,
    GitHubStateStore,
)
from app.modules.agents.implementation.repository import (
    GitHubConnectionRepository,
    GitHubConnectionRepositoryError,
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

_github_states = GitHubStateStore()


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


def get_github_connection_repository() -> GitHubConnectionRepository:
    return GitHubConnectionRepository()


def get_github_connection_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    repository: Annotated[
        GitHubConnectionRepository,
        Depends(get_github_connection_repository),
    ],
) -> GitHubConnectionService | None:
    try:
        configuration = GitHubConfiguration.from_settings(settings)
    except GitHubConfigurationError:
        return None
    return GitHubConnectionService(
        standalone_service,
        repository,
        _github_states,
        GitHubApiClient(configuration),
        configuration,
    )


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


def _frontend_callback_url(
    *,
    agent_project_id: str | None = None,
    connected: bool = False,
    reason: str | None = None,
) -> str:
    base = settings.frontend_base_url.rstrip("/")
    path = (
        f"/agent-projects/{agent_project_id}"
        if agent_project_id
        else "/agents/implementation"
    )
    query = {"github": "connected" if connected else "error"}
    if reason and not connected:
        query["reason"] = reason
    return f"{base}{path}?{urlencode(query)}"


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


@router.post(
    "/{agent_project_id}/github/connect",
    response_model=SuccessResponse[GitHubConnectResponse],
)
def connect_github(
    agent_project_id: str,
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubConnectResponse] | JSONResponse:
    if service is None:
        return _error(
            503,
            "GitHub connection unavailable",
            "github",
            "GitHub App connection is not configured",
        )
    try:
        result = service.begin_connection(agent_project_id, current_user)
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
            "Reactivate the agent project before connecting GitHub",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except StandaloneServiceError:
        return _error(
            503,
            "GitHub connection unavailable",
            "database",
            "Standalone project storage is unavailable",
        )
    return SuccessResponse(message="GitHub installation started", data=result)


@router.get("/github/install-callback", include_in_schema=True)
def github_install_callback(
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    state_value: Annotated[str | None, Query(alias="state")] = None,
    installation_id: Annotated[int | None, Query()] = None,
    setup_action: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    del setup_action
    if service is None:
        return RedirectResponse(
            _frontend_callback_url(reason="configuration_unavailable"),
            status_code=302,
        )
    if not state_value or installation_id is None:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    try:
        authorization_url = service.continue_after_installation(
            state_value, installation_id
        )
    except GitHubStateError:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    except GitHubCallbackError as exc:
        return RedirectResponse(
            _frontend_callback_url(
                agent_project_id=exc.agent_project_id,
                reason=exc.reason,
            ),
            status_code=302,
        )
    return RedirectResponse(authorization_url, status_code=302)


@router.get("/github/oauth-callback", include_in_schema=True)
def github_oauth_callback(
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    state_value: Annotated[str | None, Query(alias="state")] = None,
    code: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    del error_description
    if service is None:
        return RedirectResponse(
            _frontend_callback_url(reason="configuration_unavailable"),
            status_code=302,
        )
    if not state_value:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    try:
        agent_project_id = service.complete_connection(
            state=state_value,
            code=code,
            oauth_error=error,
        )
    except GitHubStateError:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    except GitHubCallbackError as exc:
        return RedirectResponse(
            _frontend_callback_url(
                agent_project_id=exc.agent_project_id,
                reason=exc.reason,
            ),
            status_code=302,
        )
    return RedirectResponse(
        _frontend_callback_url(
            agent_project_id=agent_project_id, connected=True
        ),
        status_code=302,
    )


@router.get(
    "/{agent_project_id}/github/connection",
    response_model=SuccessResponse[GitHubConnectionStatus],
    response_model_exclude_none=True,
)
def get_github_connection(
    agent_project_id: str,
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubConnectionStatus] | JSONResponse:
    if service is None:
        return _error(
            503,
            "GitHub connection unavailable",
            "github",
            "GitHub App connection is not configured",
        )
    try:
        result = service.connection_status(agent_project_id, current_user)
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
            "Reactivate the agent project before checking GitHub",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except (StandaloneServiceError, GitHubConnectionRepositoryError):
        return _error(
            503,
            "GitHub connection unavailable",
            "database",
            "GitHub connection storage is unavailable",
        )
    return SuccessResponse(message="GitHub connection retrieved", data=result)
