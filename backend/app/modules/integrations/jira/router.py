"""HTTP Router for Jira Cloud OAuth 2.0 (3LO) integration."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.common.response import ErrorDetail, ErrorResponse
from app.core.config import settings
from app.modules.auth.dependencies import (
    bearer_scheme,
    get_current_user,
    get_user_repository,
)
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import UserPublicResponse
from app.modules.integrations.jira.client import JiraApiClient
from app.modules.integrations.jira.repository import JiraConnectionRepository
from app.modules.integrations.jira.schemas import (
    JiraBoardResponse,
    JiraConnectResponse,
    JiraContextResponse,
    JiraDisconnectResponse,
    JiraIssueTypeResponse,
    JiraPreviewResponse,
    JiraProjectResponse,
    JiraSelectBoardRequest,
    JiraSelectProjectRequest,
    JiraSelectSiteRequest,
    JiraSelectedBoard,
    JiraSelectedProject,
    JiraSelectedSite,
    JiraSiteResponse,
    JiraStatusResponse,
    JiraSyncPreviewRequest,
)
from app.modules.integrations.jira.service import (
    JiraApiClientError,
    JiraAuthenticationError,
    JiraBoardNotAccessibleError,
    JiraBoardNotScrumError,
    JiraBoardNotSelectedError,
    JiraConfiguration,
    JiraConfigurationError,
    JiraCrossUserStateError,
    JiraHierarchyInvalidError,
    JiraIssueTypeUnavailableError,
    JiraMalformedResponseError,
    JiraMappingIncompleteError,
    JiraMissingCodeError,
    JiraNetworkError,
    JiraNetworkTimeoutError,
    JiraNotConnectedError,
    JiraOAuthApiError,
    JiraOAuthClient,
    JiraOAuthService,
    JiraPermissionError,
    JiraPlanUnavailableError,
    JiraProjectNotAccessibleError,
    JiraProjectNotSelectedError,
    JiraRateLimitError,
    JiraReauthorizationRequiredError,
    JiraRemoteApiError,
    JiraResourceNotFoundError,
    JiraSiteNotAccessibleError,
    JiraSiteNotSelectedError,
    JiraStateExpiredError,
    JiraStateInvalidError,
    JiraStateReusedError,
    JiraStateStore,
    JiraUpstreamError,
)
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import StandaloneService

router = APIRouter(prefix="/integrations/jira", tags=["integrations-jira"])

_global_jira_state_store = JiraStateStore()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_jira_connection_repository() -> JiraConnectionRepository:
    return JiraConnectionRepository()


def get_jira_state_store() -> JiraStateStore:
    return _global_jira_state_store


def get_jira_oauth_client() -> JiraOAuthClient:
    return JiraOAuthClient(timeout_seconds=settings.jira_http_timeout_seconds)


def get_jira_oauth_service(
    repository: Annotated[
        JiraConnectionRepository, Depends(get_jira_connection_repository)
    ],
    state_store: Annotated[JiraStateStore, Depends(get_jira_state_store)],
    client: Annotated[JiraOAuthClient, Depends(get_jira_oauth_client)],
) -> JiraOAuthService:
    try:
        config: JiraConfiguration | None = JiraConfiguration.from_settings(
            settings
        )
    except JiraConfigurationError:
        config = None

    return JiraOAuthService(
        configuration=config,
        repository=repository,
        state_store=state_store,
        client=client,
    )


def get_jira_api_client(
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
) -> JiraApiClient:
    return JiraApiClient(
        service=service,
        timeout_seconds=settings.jira_http_timeout_seconds,
    )


def get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserPublicResponse | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        return get_current_user(credentials, repository)
    except Exception:
        return None


def _error_response(
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
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


def _handle_jira_exception(exc: Exception) -> JSONResponse:
    if isinstance(exc, JiraNotConnectedError):
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="JIRA_NOT_CONNECTED",
            field="jira",
            detail=f"JIRA_NOT_CONNECTED: {exc}",
        )
    if isinstance(exc, JiraReauthorizationRequiredError):
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="JIRA_REAUTHORIZATION_REQUIRED",
            field="jira",
            detail=f"JIRA_REAUTHORIZATION_REQUIRED: {exc}",
        )
    if isinstance(exc, JiraSiteNotSelectedError):
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="JIRA_SITE_NOT_SELECTED",
            field="site",
            detail=f"JIRA_SITE_NOT_SELECTED: {exc}",
        )
    if isinstance(exc, JiraSiteNotAccessibleError):
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="JIRA_SITE_NOT_ACCESSIBLE",
            field="cloud_id",
            detail=f"JIRA_SITE_NOT_ACCESSIBLE: {exc}",
        )
    if isinstance(exc, JiraProjectNotSelectedError):
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="JIRA_PROJECT_NOT_SELECTED",
            field="project",
            detail=f"JIRA_PROJECT_NOT_SELECTED: {exc}",
        )
    if isinstance(exc, JiraProjectNotAccessibleError):
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="JIRA_PROJECT_NOT_ACCESSIBLE",
            field="project_id",
            detail=f"JIRA_PROJECT_NOT_ACCESSIBLE: {exc}",
        )
    if isinstance(exc, JiraBoardNotAccessibleError):
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="JIRA_BOARD_NOT_ACCESSIBLE",
            field="board_id",
            detail=f"JIRA_BOARD_NOT_ACCESSIBLE: {exc}",
        )
    if isinstance(exc, JiraBoardNotScrumError):
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="JIRA_BOARD_NOT_SCRUM",
            field="board_id",
            detail=f"JIRA_BOARD_NOT_SCRUM: {exc}",
        )
    if isinstance(exc, JiraBoardNotSelectedError):
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="JIRA_BOARD_NOT_SELECTED",
            field="board",
            detail=f"JIRA_BOARD_NOT_SELECTED: {exc}",
        )
    if isinstance(exc, JiraPlanUnavailableError):
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="JIRA_PLAN_UNAVAILABLE",
            field="jira_plan",
            detail=f"JIRA_PLAN_UNAVAILABLE: {exc}",
        )
    if isinstance(exc, JiraMappingIncompleteError):
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            message="JIRA_MAPPING_INCOMPLETE",
            field="mappings",
            detail=f"JIRA_MAPPING_INCOMPLETE: {exc}",
        )
    if isinstance(exc, JiraIssueTypeUnavailableError):
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            message="JIRA_ISSUE_TYPE_UNAVAILABLE",
            field="mappings",
            detail=f"JIRA_ISSUE_TYPE_UNAVAILABLE: {exc}",
        )
    if isinstance(exc, JiraHierarchyInvalidError):
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            message="JIRA_HIERARCHY_INVALID",
            field="hierarchy",
            detail=f"JIRA_HIERARCHY_INVALID: {exc}",
        )
    if isinstance(exc, JiraRateLimitError):
        return _error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message="JIRA_RATE_LIMITED",
            field="jira",
            detail=f"JIRA_RATE_LIMITED: {exc}",
        )
    if isinstance(
        exc,
        (
            JiraUpstreamError,
            JiraAuthenticationError,
            JiraPermissionError,
            JiraResourceNotFoundError,
            JiraNetworkTimeoutError,
            JiraNetworkError,
            JiraMalformedResponseError,
            JiraRemoteApiError,
            JiraOAuthApiError,
            JiraApiClientError,
        ),
    ):
        code = status.HTTP_502_BAD_GATEWAY
        if isinstance(exc, JiraNetworkTimeoutError):
            code = status.HTTP_504_GATEWAY_TIMEOUT
        elif isinstance(exc, JiraAuthenticationError):
            code = status.HTTP_401_UNAUTHORIZED
        elif isinstance(exc, JiraPermissionError):
            code = status.HTTP_403_FORBIDDEN
        elif isinstance(exc, JiraResourceNotFoundError):
            code = status.HTTP_404_NOT_FOUND

        return _error_response(
            status_code=code,
            message="JIRA_UPSTREAM_ERROR",
            field="jira",
            detail=f"JIRA_UPSTREAM_ERROR: {exc}",
        )
    if isinstance(exc, ValueError):
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="VALIDATION_ERROR",
            field="request",
            detail=str(exc),
        )
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="JIRA_INTERNAL_ERROR",
        field="jira",
        detail="An unexpected Jira integration error occurred",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=JiraStatusResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def get_jira_status(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
) -> JiraStatusResponse:
    """Retrieve the Jira connection status for the authenticated user.

    Identity is derived strictly from the authenticated token, not from client input.
    Never returns access tokens, refresh tokens, secrets, or authorization codes.
    """
    return service.get_status(current_user.user_id)


@router.get(
    "/connect",
    response_model=JiraConnectResponse,
    status_code=status.HTTP_200_OK,
)
def connect_jira(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
) -> JiraConnectResponse | JSONResponse:
    """Initiate Jira Cloud OAuth 2.0 flow.

    Generates a cryptographically random, user-bound, single-use, expiring state
    and returns the safe Atlassian authorization URL.
    """
    if not service.is_configured:
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="Jira connection unavailable",
            field="jira",
            detail="Jira Cloud OAuth credentials are not configured",
        )

    try:
        return service.begin_connection(current_user)
    except JiraConfigurationError as exc:
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="Jira connection unavailable",
            field="jira",
            detail=str(exc),
        )


@router.get(
    "/callback",
    include_in_schema=True,
)
def jira_callback(
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
    optional_user: Annotated[
        UserPublicResponse | None, Depends(get_optional_current_user)
    ] = None,
) -> RedirectResponse:
    """Handle the Atlassian OAuth authorization callback.

    Validates state existence, expiration, single-use, and user binding.
    Exchanges code server-to-server and persists connection info.
    Redirects back to frontend with only a safe success or error parameter.
    Tokens or authorization codes are NEVER included in frontend URLs.
    """
    del error_description

    if not service.is_configured:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(
                error_code="configuration_unavailable"
            ),
            status_code=status.HTTP_302_FOUND,
        )

    if error:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(error_code=error),
            status_code=status.HTTP_302_FOUND,
        )

    expected_user_id = optional_user.user_id if optional_user is not None else None

    try:
        service.complete_connection(
            state=state,
            code=code,
            expected_user_id=expected_user_id,
        )
    except JiraMissingCodeError:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(error_code="missing_code"),
            status_code=status.HTTP_302_FOUND,
        )
    except JiraStateReusedError:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(error_code="reused_state"),
            status_code=status.HTTP_302_FOUND,
        )
    except JiraStateExpiredError:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(error_code="expired_state"),
            status_code=status.HTTP_302_FOUND,
        )
    except JiraCrossUserStateError:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(error_code="cross_user_state"),
            status_code=status.HTTP_302_FOUND,
        )
    except JiraStateInvalidError:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(error_code="invalid_state"),
            status_code=status.HTTP_302_FOUND,
        )
    except JiraOAuthApiError:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(
                error_code="token_exchange_failed"
            ),
            status_code=status.HTTP_302_FOUND,
        )
    except Exception:
        return RedirectResponse(
            url=service.build_frontend_redirect_url(
                error_code="unexpected_error"
            ),
            status_code=status.HTTP_302_FOUND,
        )

    return RedirectResponse(
        url=service.build_frontend_redirect_url(connected=True),
        status_code=status.HTTP_302_FOUND,
    )


@router.delete(
    "/connection",
    response_model=JiraDisconnectResponse,
    status_code=status.HTTP_200_OK,
)
def disconnect_jira(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
) -> JiraDisconnectResponse:
    """Disconnect Jira for the authenticated user by removing local tokens and connection.

    Notice: This removes the AgileFlow-side connection and stored credentials only.
    """
    service.disconnect(current_user.user_id)
    return JiraDisconnectResponse(
        disconnected=True,
        message="Jira connection removed successfully",
    )


# ---------------------------------------------------------------------------
# Discovery and Selection Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/sites",
    response_model=list[JiraSiteResponse],
    status_code=status.HTTP_200_OK,
)
def get_jira_sites(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
) -> list[JiraSiteResponse] | JSONResponse:
    """Retrieve authorized Jira Cloud sites for the authenticated user.

    Does not auto-select a site. Never returns tokens or client credentials.
    """
    try:
        return service.get_sites(user_id=current_user.user_id, client=api_client)
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.put(
    "/site",
    response_model=JiraSelectedSite,
    status_code=status.HTTP_200_OK,
)
def select_jira_site(
    payload: JiraSelectSiteRequest,
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
) -> JiraSelectedSite | JSONResponse:
    """Select an authorized Jira Cloud site for the authenticated user.

    Validates that the cloud_id is authorized and accessible.
    Changing site invalidates any previously selected project or board.
    """
    try:
        return service.select_site(
            user_id=current_user.user_id,
            cloud_id=payload.cloud_id,
            client=api_client,
        )
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.get(
    "/projects",
    response_model=list[JiraProjectResponse],
    status_code=status.HTTP_200_OK,
)
def get_jira_projects(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
    start_at: Annotated[int, Query(ge=0)] = 0,
    max_results: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[JiraProjectResponse] | JSONResponse:
    """Retrieve accessible Jira Software projects for the selected Jira Cloud site.

    Requires an active Jira connection and selected site.
    """
    try:
        return service.get_projects(
            user_id=current_user.user_id,
            start_at=start_at,
            max_results=max_results,
            client=api_client,
        )
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.put(
    "/project",
    response_model=JiraSelectedProject,
    status_code=status.HTTP_200_OK,
)
def select_jira_project(
    payload: JiraSelectProjectRequest,
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
) -> JiraSelectedProject | JSONResponse:
    """Select an accessible Jira project on the selected Jira Cloud site.

    Validates project accessibility server-side.
    Changing project invalidates any previously selected board.
    """
    try:
        return service.select_project(
            user_id=current_user.user_id,
            project_id=payload.project_id,
            project_key=payload.project_key,
            client=api_client,
        )
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.get(
    "/boards",
    response_model=list[JiraBoardResponse],
    status_code=status.HTTP_200_OK,
)
def get_jira_boards(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
    start_at: Annotated[int, Query(ge=0)] = 0,
    max_results: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[JiraBoardResponse] | JSONResponse:
    """Retrieve Scrum boards for the selected project.

    Requires a selected site and selected project. Restricts to Scrum boards.
    """
    try:
        return service.get_scrum_boards(
            user_id=current_user.user_id,
            start_at=start_at,
            max_results=max_results,
            client=api_client,
        )
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.put(
    "/board",
    response_model=JiraSelectedBoard,
    status_code=status.HTTP_200_OK,
)
def select_jira_board(
    payload: JiraSelectBoardRequest,
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
) -> JiraSelectedBoard | JSONResponse:
    """Select a Scrum board for the selected Jira project.

    Validates server-side that board exists, is a Scrum board, and belongs to selected project.
    """
    try:
        return service.select_board(
            user_id=current_user.user_id,
            board_id=payload.board_id,
            client=api_client,
        )
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.get(
    "/context",
    response_model=JiraContextResponse,
    status_code=status.HTTP_200_OK,
)
def get_jira_context(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
) -> JiraContextResponse | JSONResponse:
    """Retrieve current Jira connection and selection context for the authenticated user.

    Returns null for selections not completed yet. Never exposes OAuth tokens or secrets.
    """
    try:
        return service.get_context(user_id=current_user.user_id)
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.get(
    "/issue-types",
    response_model=list[JiraIssueTypeResponse],
    status_code=status.HTTP_200_OK,
)
def get_jira_issue_types(
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
) -> list[JiraIssueTypeResponse] | JSONResponse:
    """Retrieve available Jira issue types for the currently selected project."""
    try:
        return service.get_project_issue_types(
            user_id=current_user.user_id,
            client=api_client,
        )
    except Exception as exc:
        return _handle_jira_exception(exc)


@router.post(
    "/preview",
    response_model=JiraPreviewResponse,
    status_code=status.HTTP_200_OK,
)
def generate_jira_sync_preview(
    payload: JiraSyncPreviewRequest,
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    service: Annotated[JiraOAuthService, Depends(get_jira_oauth_service)],
    api_client: Annotated[JiraApiClient, Depends(get_jira_api_client)],
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
) -> JiraPreviewResponse | JSONResponse:
    """Generate a deterministic synchronization preview for Agent 2 planning results.

    Validates Jira connection, target resources, planning outputs, issue-type mappings,
    and hierarchy integrity. Makes ZERO Jira write or mutation requests.
    """
    try:
        return service.build_sync_preview(
            user_id=current_user.user_id,
            agent_project_id=payload.agent_project_id,
            mappings=payload.mappings,
            run_id=payload.run_id,
            outputs=payload.outputs,
            client=api_client,
            standalone_service=standalone_service,
        )
    except Exception as exc:
        return _handle_jira_exception(exc)
