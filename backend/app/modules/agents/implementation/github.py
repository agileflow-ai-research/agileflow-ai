import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.agents.implementation.repository import (
    GitHubConnectionRepository,
    GitHubConnectionRepositoryError,
)
from app.modules.agents.implementation.schemas import (
    GitHubConnection,
    GitHubConnectionStatus,
    GitHubConnectResponse,
)
from app.modules.agents.implementation.service import (
    require_implementation_project,
)
from app.modules.auth.schemas import UserPublicResponse
from app.common.status import AgentType
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)


GITHUB_STATE_TTL = timedelta(minutes=10)
MAX_PENDING_GITHUB_STATES = 1000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class GitHubConfiguration:
    app_id: str
    client_id: str
    client_secret: str
    app_slug: str
    setup_callback_url: str
    oauth_callback_url: str
    web_base_url: str
    api_base_url: str
    frontend_base_url: str
    timeout_seconds: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "GitHubConfiguration":
        values = {
            "app_id": settings.github_app_id,
            "client_id": settings.github_app_client_id,
            "client_secret": settings.github_app_client_secret,
            "app_slug": settings.github_app_slug,
            "setup_callback_url": settings.github_app_setup_callback_url,
            "oauth_callback_url": settings.github_app_oauth_callback_url,
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise GitHubConfigurationError(
                "GitHub App connection is not configured"
            )
        return cls(
            **{name: str(value) for name, value in values.items()},
            web_base_url=settings.github_web_base_url.rstrip("/"),
            api_base_url=settings.github_api_base_url.rstrip("/"),
            frontend_base_url=settings.frontend_base_url.rstrip("/"),
            timeout_seconds=settings.github_http_timeout_seconds,
        )


@dataclass(frozen=True)
class PendingInstallation:
    state: str
    owner_id: str
    agent_project_id: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class PendingOAuth:
    oauth_state: str
    owner_id: str
    agent_project_id: str
    candidate_installation_id: int
    code_verifier: str
    code_challenge: str
    created_at: datetime
    expires_at: datetime


class GitHubConfigurationError(RuntimeError):
    pass


class GitHubStateError(ValueError):
    pass


class GitHubStateExpiredError(GitHubStateError):
    pass


class GitHubApiError(RuntimeError):
    pass


class GitHubAuthorizationError(GitHubApiError):
    pass


class GitHubCallbackError(RuntimeError):
    def __init__(self, reason: str, agent_project_id: str, message: str) -> None:
        self.reason = reason
        self.agent_project_id = agent_project_id
        super().__init__(message)


class OrganizationInstallationError(GitHubCallbackError):
    def __init__(self, agent_project_id: str) -> None:
        super().__init__(
            "organization_not_supported",
            agent_project_id,
            "Organization GitHub installations are not supported in the "
            "current standalone Agent 3 MVP.",
        )


class GitHubStateStore:
    def __init__(
        self,
        *,
        clock=utc_now,
        ttl: timedelta = GITHUB_STATE_TTL,
        max_entries: int = MAX_PENDING_GITHUB_STATES,
    ) -> None:
        self._clock = clock
        self._ttl = ttl
        self._max_entries = max_entries
        self._install_states: dict[str, PendingInstallation] = {}
        self._oauth_states: dict[str, PendingOAuth] = {}
        self._lock = Lock()

    def create_installation(
        self, owner_id: str, agent_project_id: str
    ) -> PendingInstallation:
        with self._lock:
            now = self._clock()
            self._cleanup(now)
            self._make_room(self._install_states)
            state = secrets.token_urlsafe(32)
            record = PendingInstallation(
                state=state,
                owner_id=owner_id,
                agent_project_id=agent_project_id,
                created_at=now,
                expires_at=now + self._ttl,
            )
            self._install_states[state] = record
            return record

    def consume_installation(self, state: str) -> PendingInstallation:
        with self._lock:
            record = self._install_states.pop(state, None)
            if record is None:
                raise GitHubStateError("GitHub installation state is invalid")
            if record.expires_at <= self._clock():
                raise GitHubStateExpiredError("GitHub installation state expired")
            return record

    def create_oauth(
        self,
        installation: PendingInstallation,
        candidate_installation_id: int,
    ) -> PendingOAuth:
        with self._lock:
            now = self._clock()
            self._cleanup(now)
            self._make_room(self._oauth_states)
            oauth_state = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(64)
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            ).rstrip(b"=").decode("ascii")
            record = PendingOAuth(
                oauth_state=oauth_state,
                owner_id=installation.owner_id,
                agent_project_id=installation.agent_project_id,
                candidate_installation_id=candidate_installation_id,
                code_verifier=verifier,
                code_challenge=challenge,
                created_at=now,
                expires_at=now + self._ttl,
            )
            self._oauth_states[oauth_state] = record
            return record

    def consume_oauth(self, state: str) -> PendingOAuth:
        with self._lock:
            record = self._oauth_states.pop(state, None)
            if record is None:
                raise GitHubStateError("GitHub OAuth state is invalid")
            if record.expires_at <= self._clock():
                raise GitHubStateExpiredError("GitHub OAuth state expired")
            return record

    def _cleanup(self, now: datetime) -> None:
        for records in (self._install_states, self._oauth_states):
            expired = [
                state
                for state, record in records.items()
                if record.expires_at <= now
            ]
            for state in expired:
                records.pop(state, None)

    def _make_room(self, records: dict[str, Any]) -> None:
        while len(records) >= self._max_entries:
            oldest = min(records, key=lambda state: records[state].created_at)
            records.pop(oldest, None)


class GitHubApiClient:
    def __init__(self, configuration: GitHubConfiguration) -> None:
        self._configuration = configuration

    def exchange_code(self, code: str, code_verifier: str) -> str:
        try:
            response = httpx.post(
                f"{self._configuration.web_base_url}/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._configuration.client_id,
                    "client_secret": self._configuration.client_secret,
                    "code": code,
                    "redirect_uri": self._configuration.oauth_callback_url,
                    "code_verifier": code_verifier,
                },
                timeout=self._configuration.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise GitHubApiError("GitHub authorization is unavailable") from exc
        body = self._json_object(response)
        if response.status_code == 400 or body.get("error"):
            raise GitHubAuthorizationError("GitHub authorization code was rejected")
        if response.status_code >= 400:
            raise GitHubApiError("GitHub authorization is unavailable")
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise GitHubAuthorizationError("GitHub authorization response was invalid")
        return token

    def get_user(self, access_token: str) -> dict[str, Any]:
        return self._get_json("/user", access_token)

    def get_installations(self, access_token: str) -> list[dict[str, Any]]:
        body = self._get_json(
            "/user/installations?per_page=100&page=1", access_token
        )
        installations = body.get("installations")
        if not isinstance(installations, list) or not all(
            isinstance(item, dict) for item in installations
        ):
            raise GitHubApiError("GitHub installations response was invalid")
        return installations

    def _get_json(self, path: str, access_token: str) -> dict[str, Any]:
        try:
            response = httpx.get(
                f"{self._configuration.api_base_url}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self._configuration.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise GitHubApiError("GitHub API is unavailable") from exc
        if response.status_code >= 400:
            raise GitHubApiError("GitHub API request failed")
        return self._json_object(response)

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise GitHubApiError("GitHub returned an invalid response") from exc
        if not isinstance(body, dict):
            raise GitHubApiError("GitHub returned an invalid response")
        return body


class GitHubConnectionService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        repository: GitHubConnectionRepository,
        states: GitHubStateStore,
        client: GitHubApiClient,
        configuration: GitHubConfiguration,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._repository = repository
        self._states = states
        self._client = client
        self._configuration = configuration
        self._clock = clock

    def begin_connection(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> GitHubConnectResponse:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        pending = self._states.create_installation(
            current_user.user_id, project.agent_project_id
        )
        query = urlencode({"state": pending.state})
        return GitHubConnectResponse(
            installation_url=(
                f"{self._configuration.web_base_url}/apps/"
                f"{self._configuration.app_slug}/installations/new?{query}"
            ),
            expires_at=pending.expires_at,
        )

    def continue_after_installation(
        self, state: str, installation_id: int
    ) -> str:
        pending = self._states.consume_installation(state)
        self._require_pending_project(pending.owner_id, pending.agent_project_id)
        if installation_id <= 0:
            raise GitHubCallbackError(
                "invalid_installation",
                pending.agent_project_id,
                "GitHub installation ID is invalid",
            )
        oauth = self._states.create_oauth(pending, installation_id)
        query = urlencode(
            {
                "client_id": self._configuration.client_id,
                "redirect_uri": self._configuration.oauth_callback_url,
                "state": oauth.oauth_state,
                "code_challenge": oauth.code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self._configuration.web_base_url}/login/oauth/authorize?{query}"

    def complete_connection(
        self,
        *,
        state: str,
        code: str | None,
        oauth_error: str | None,
    ) -> str:
        pending = self._states.consume_oauth(state)
        self._require_pending_project(pending.owner_id, pending.agent_project_id)
        if oauth_error or not code:
            raise GitHubCallbackError(
                "authorization_denied" if oauth_error else "authorization_failed",
                pending.agent_project_id,
                "GitHub authorization was not completed",
            )
        try:
            access_token = self._client.exchange_code(code, pending.code_verifier)
            user = self._client.get_user(access_token)
            installations = self._client.get_installations(access_token)
            connection = self._verified_connection(pending, user, installations)
            existing = self._repository.find_by_owner(pending.owner_id)
            now = self._clock()
            if existing is not None:
                connection = connection.model_copy(
                    update={"connected_at": existing["connected_at"], "updated_at": now}
                )
            persisted = self._repository.upsert(connection)
            GitHubConnection.model_validate(persisted)
        except OrganizationInstallationError:
            raise
        except GitHubAuthorizationError as exc:
            raise GitHubCallbackError(
                "authorization_failed",
                pending.agent_project_id,
                "GitHub authorization failed",
            ) from exc
        except GitHubApiError as exc:
            raise GitHubCallbackError(
                "github_unavailable",
                pending.agent_project_id,
                "GitHub verification is unavailable",
            ) from exc
        except (GitHubConnectionRepositoryError, ValidationError, KeyError) as exc:
            raise GitHubCallbackError(
                "connection_failed",
                pending.agent_project_id,
                "GitHub connection could not be persisted",
            ) from exc
        return pending.agent_project_id

    def connection_status(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> GitHubConnectionStatus:
        require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        try:
            document = self._repository.find_by_owner(current_user.user_id)
            if document is None:
                return GitHubConnectionStatus(connected=False)
            connection = GitHubConnection.model_validate(document)
        except (GitHubConnectionRepositoryError, ValidationError) as exc:
            raise GitHubConnectionRepositoryError(
                "Could not retrieve GitHub connection"
            ) from exc
        return GitHubConnectionStatus(
            connected=True,
            github_user_id=connection.github_user_id,
            github_login=connection.github_login,
            avatar_url=connection.github_avatar_url,
            installation_id=connection.installation_id,
            account_type=connection.installation_account_type,
        )

    def _require_pending_project(
        self, owner_id: str, agent_project_id: str
    ) -> None:
        try:
            project = self._standalone.require_active_project(
                owner_id, agent_project_id
            )
        except (
            AgentProjectNotFoundError,
            ArchivedAgentProjectError,
            StandaloneServiceError,
            ValueError,
        ) as exc:
            raise GitHubCallbackError(
                "project_unavailable",
                agent_project_id,
                "Agent project is unavailable for GitHub connection",
            ) from exc
        if project.agent_type is not AgentType.IMPLEMENTATION:
            raise GitHubCallbackError(
                "project_unavailable",
                agent_project_id,
                "Agent project is unavailable for GitHub connection",
            )

    def _verified_connection(
        self,
        pending: PendingOAuth,
        user: dict[str, Any],
        installations: list[dict[str, Any]],
    ) -> GitHubConnection:
        github_user_id = user.get("id")
        github_login = user.get("login")
        avatar_url = user.get("avatar_url")
        if (
            not isinstance(github_user_id, int)
            or isinstance(github_user_id, bool)
            or github_user_id <= 0
            or not isinstance(github_login, str)
            or not github_login
            or (avatar_url is not None and not isinstance(avatar_url, str))
        ):
            raise GitHubApiError("GitHub user response was invalid")
        candidate = next(
            (
                item
                for item in installations
                if item.get("id") == pending.candidate_installation_id
            ),
            None,
        )
        if candidate is None:
            raise GitHubCallbackError(
                "installation_not_verified",
                pending.agent_project_id,
                "GitHub installation is not accessible to this user",
            )
        account = candidate.get("account")
        if not isinstance(account, dict):
            raise GitHubApiError("GitHub installation response was invalid")
        account_type = account.get("type")
        if account_type == "Organization":
            raise OrganizationInstallationError(pending.agent_project_id)
        if account_type != "User":
            raise GitHubCallbackError(
                "installation_not_verified",
                pending.agent_project_id,
                "GitHub installation account type is unsupported",
            )
        if account.get("id") != github_user_id:
            raise GitHubCallbackError(
                "installation_not_verified",
                pending.agent_project_id,
                "GitHub installation account does not match the authorized user",
            )
        account_login = account.get("login")
        if not isinstance(account_login, str) or not account_login:
            raise GitHubApiError("GitHub installation response was invalid")
        now = self._clock()
        return GitHubConnection(
            owner_id=pending.owner_id,
            github_user_id=github_user_id,
            github_login=github_login,
            github_avatar_url=avatar_url,
            installation_id=pending.candidate_installation_id,
            installation_account_id=github_user_id,
            installation_account_login=account_login,
            installation_account_type="User",
            connected_at=now,
            updated_at=now,
        )
