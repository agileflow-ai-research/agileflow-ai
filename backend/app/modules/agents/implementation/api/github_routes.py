"""Agent 3 HTTP routes grouped by responsibility."""

from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.agents.implementation.contracts.schemas import (
    GitHubConnectionStatus,
    GitHubConnectResponse,
    GitHubRepositoryCreateRequest,
    GitHubRepositoryStatus,
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)
from app.modules.agents.implementation.github.auth import (
    GitHubAppAuthenticationError,
    GitHubAppAuthenticator,
    GitHubAppPermissionError,
    GitHubExternalServiceError,
    GitHubInstallationRevokedError,
    GitHubPrivateKeyError,
)
from app.modules.agents.implementation.github.repository_service import (
    GitHubConnectionRequiredError,
    GitHubOrganizationConnectionError,
    GitHubRepositoryAlreadyBoundError,
    GitHubRepositoryAuthenticationError,
    GitHubRepositoryClient,
    GitHubRepositoryExternalError,
    GitHubRepositoryNameConflictError,
    GitHubRepositoryPartialFailureError,
    GitHubRepositoryPermissionError,
    GitHubRepositoryService,
    GitHubRepositoryValidationError,
)
from app.modules.agents.implementation.github.connection_service import (
    GitHubApiClient,
    GitHubCallbackError,
    GitHubConfiguration,
    GitHubConfigurationError,
    GitHubConnectionService,
    GitHubStateError,
    GitHubStateStore,
)
from app.modules.agents.implementation.github.repository import (
    GitHubConnectionRepository,
    GitHubConnectionRepositoryError,
    GitHubRepositoryBindingRepository,
    GitHubRepositoryBindingRepositoryError,
)
from app.modules.agents.implementation.inputs.upload.service import (
    ImplementationInputService,
    WrongAgentProjectTypeError,
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
    get_github_connection_service,
    get_github_repository_service,
)
from app.modules.agents.implementation.api.errors import (
    _error,
    _frontend_callback_url,
)


router = APIRouter()


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


def _repository_failure(
    status_code: int,
    message: str,
    detail: str,
    repository: GitHubRepositoryStatus | None = None,
) -> JSONResponse:
    content = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field="repository", message=detail)],
    ).model_dump(mode="json")
    if repository is not None:
        content["data"] = {
            "repository": repository.model_dump(mode="json", exclude_none=True)
        }
    return JSONResponse(status_code=status_code, content=content)


@router.get(
    "/{agent_project_id}/github/repository",
    response_model=SuccessResponse[GitHubRepositoryStatus],
    response_model_exclude_none=True,
)
def get_github_repository(
    agent_project_id: str,
    service: Annotated[
        GitHubRepositoryService, Depends(get_github_repository_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubRepositoryStatus] | JSONResponse:
    try:
        repository = service.get_repository(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before checking its GitHub repository",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except (StandaloneServiceError, GitHubRepositoryBindingRepositoryError):
        return _repository_failure(
            503,
            "GitHub repository unavailable",
            "Repository binding storage is unavailable",
        )
    return SuccessResponse(message="GitHub repository retrieved", data=repository)


@router.post(
    "/{agent_project_id}/github/repository",
    response_model=SuccessResponse[GitHubRepositoryStatus],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_github_repository(
    agent_project_id: str,
    request: GitHubRepositoryCreateRequest,
    service: Annotated[
        GitHubRepositoryService, Depends(get_github_repository_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubRepositoryStatus] | JSONResponse:
    try:
        repository = service.create_repository(
            agent_project_id, current_user, request
        )
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before creating a GitHub repository",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except GitHubRepositoryAlreadyBoundError as exc:
        return _repository_failure(409, str(exc), str(exc), exc.repository)
    except GitHubConnectionRequiredError as exc:
        return _repository_failure(409, "GitHub connection required", str(exc))
    except GitHubOrganizationConnectionError as exc:
        return _repository_failure(422, "Unsupported GitHub account", str(exc))
    except GitHubPrivateKeyError as exc:
        return _repository_failure(503, "GitHub App configuration unavailable", str(exc))
    except (GitHubInstallationRevokedError, GitHubRepositoryAuthenticationError) as exc:
        return _repository_failure(409, "GitHub reconnection required", str(exc))
    except GitHubAppAuthenticationError as exc:
        return _repository_failure(502, "GitHub App authentication failed", str(exc))
    except (GitHubAppPermissionError, GitHubRepositoryPermissionError) as exc:
        return _repository_failure(403, "GitHub App permission denied", str(exc))
    except GitHubRepositoryNameConflictError as exc:
        return _repository_failure(409, "Repository name unavailable", str(exc))
    except GitHubRepositoryValidationError as exc:
        return _repository_failure(422, "Repository creation rejected", str(exc))
    except GitHubRepositoryPartialFailureError as exc:
        return _repository_failure(
            502,
            "Repository created but binding failed",
            str(exc),
            exc.repository,
        )
    except (GitHubExternalServiceError, GitHubRepositoryExternalError) as exc:
        return _repository_failure(502, "GitHub repository unavailable", str(exc))
    except (
        StandaloneServiceError,
        GitHubConnectionRepositoryError,
        GitHubRepositoryBindingRepositoryError,
    ):
        return _repository_failure(
            503,
            "GitHub repository unavailable",
            "GitHub repository storage is unavailable",
        )
    return SuccessResponse(message="GitHub repository created", data=repository)
