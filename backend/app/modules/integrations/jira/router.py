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
    JiraConnectResponse,
    JiraDisconnectResponse,
    JiraStatusResponse,
)
from app.modules.integrations.jira.service import (
    JiraConfiguration,
    JiraConfigurationError,
    JiraCrossUserStateError,
    JiraMissingCodeError,
    JiraOAuthApiError,
    JiraOAuthClient,
    JiraOAuthService,
    JiraStateExpiredError,
    JiraStateInvalidError,
    JiraStateReusedError,
    JiraStateStore,
)

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
