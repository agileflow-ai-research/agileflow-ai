import json
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.modules.agents.implementation.github.auth import (
    GitHubAppAuthenticator,
)
from app.modules.agents.implementation.github.repository import (
    GitHubConnectionRepository,
    GitHubConnectionRepositoryError,
    GitHubRepositoryBindingRepository,
    GitHubRepositoryBindingRepositoryError,
)
from app.modules.agents.implementation.contracts.schemas import (
    GitHubConnection,
    GitHubRepositoryBinding,
    GitHubRepositoryCreateRequest,
    GitHubRepositoryStatus,
    GitHubRepositoryVisibility,
)
from app.modules.agents.implementation.inputs.upload.service import (
    require_implementation_project,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


logger = logging.getLogger(__name__)


class GitHubConnectionRequiredError(RuntimeError):
    pass


class GitHubOrganizationConnectionError(RuntimeError):
    pass


class GitHubRepositoryAlreadyBoundError(RuntimeError):
    def __init__(self, repository: GitHubRepositoryStatus) -> None:
        self.repository = repository
        super().__init__("Agent project already has a GitHub repository")


class GitHubRepositoryNameConflictError(RuntimeError):
    pass


class GitHubRepositoryValidationError(RuntimeError):
    pass


class GitHubRepositoryAuthenticationError(RuntimeError):
    pass


class GitHubRepositoryPermissionError(RuntimeError):
    pass


class GitHubRepositoryExternalError(RuntimeError):
    pass


class GitHubRepositoryPartialFailureError(RuntimeError):
    def __init__(self, repository: GitHubRepositoryStatus) -> None:
        self.repository = repository
        super().__init__(
            "GitHub repository was created, but its AgileFlow binding could not be saved"
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GitHubRepositoryCreationCoordinator:
    def __init__(self, max_pending_reconciliations: int = 1000) -> None:
        self.lock = Lock()
        self.pending_reconciliations: dict[str, GitHubRepositoryBinding] = {}
        self.max_pending_reconciliations = max_pending_reconciliations

    def remember_partial(self, binding: GitHubRepositoryBinding) -> None:
        while len(self.pending_reconciliations) >= self.max_pending_reconciliations:
            oldest = min(
                self.pending_reconciliations,
                key=lambda project_id: self.pending_reconciliations[project_id].updated_at,
            )
            self.pending_reconciliations.pop(oldest, None)
        self.pending_reconciliations[binding.agent_project_id] = binding


repository_creation_coordinator = GitHubRepositoryCreationCoordinator()


class GitHubRepositoryClient:
    def __init__(self, api_base_url: str, timeout_seconds: float) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def create_repository(
        self,
        installation_token: str,
        request: GitHubRepositoryCreateRequest,
    ) -> dict[str, Any]:
        payload = {
            "name": request.name,
            "description": request.description or "",
            "private": request.visibility is GitHubRepositoryVisibility.PRIVATE,
            "auto_init": False,
        }
        try:
            response = httpx.post(
                f"{self._api_base_url}/user/repos",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {installation_token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json=payload,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise GitHubRepositoryExternalError(
                "GitHub is temporarily unavailable"
            ) from exc
        if response.status_code == 401:
            raise GitHubRepositoryAuthenticationError(
                "GitHub App authentication failed"
            )
        if response.status_code == 403:
            raise GitHubRepositoryPermissionError(
                "GitHub App does not have repository creation permission"
            )
        if response.status_code == 404:
            raise GitHubRepositoryAuthenticationError(
                "GitHub connection is no longer valid. Reconnect GitHub."
            )
        if response.status_code == 422:
            if self._is_name_conflict(response):
                raise GitHubRepositoryNameConflictError(
                    "A repository with this name already exists on the connected GitHub account"
                )
            raise GitHubRepositoryValidationError(
                "GitHub rejected the repository configuration"
            )
        if response.status_code >= 400:
            raise GitHubRepositoryExternalError(
                "GitHub repository creation is temporarily unavailable"
            )
        return self._json_object(response)

    @staticmethod
    def _is_name_conflict(response: httpx.Response) -> bool:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            return False
        if not isinstance(body, dict):
            return False
        safe_text = " ".join(
            str(value)
            for value in (body.get("message"), body.get("errors"))
            if value is not None
        ).lower()
        return "already exists" in safe_text

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise GitHubRepositoryExternalError(
                "GitHub returned an invalid repository response"
            ) from exc
        if not isinstance(body, dict):
            raise GitHubRepositoryExternalError(
                "GitHub returned an invalid repository response"
            )
        return body


class GitHubRepositoryService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        connection_repository: GitHubConnectionRepository,
        binding_repository: GitHubRepositoryBindingRepository,
        authenticator: GitHubAppAuthenticator,
        github_client: GitHubRepositoryClient,
        *,
        clock=utc_now,
        coordinator: GitHubRepositoryCreationCoordinator = repository_creation_coordinator,
    ) -> None:
        self._standalone = standalone_service
        self._connections = connection_repository
        self._bindings = binding_repository
        self._authenticator = authenticator
        self._github = github_client
        self._clock = clock
        self._coordinator = coordinator

    def get_repository(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> GitHubRepositoryStatus:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        document = self._bindings.find_by_project(
            project.agent_project_id, current_user.user_id
        )
        if document is None:
            return GitHubRepositoryStatus(created=False)
        try:
            binding = GitHubRepositoryBinding.model_validate(document)
        except ValidationError as exc:
            raise GitHubRepositoryBindingRepositoryError(
                "Stored GitHub repository binding is invalid"
            ) from exc
        return GitHubRepositoryStatus.from_binding(binding)

    def create_repository(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        request: GitHubRepositoryCreateRequest,
    ) -> GitHubRepositoryStatus:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        with self._coordinator.lock:
            existing = self._bindings.find_by_project(
                project.agent_project_id, current_user.user_id
            )
            if existing is not None:
                binding = GitHubRepositoryBinding.model_validate(existing)
                raise GitHubRepositoryAlreadyBoundError(
                    GitHubRepositoryStatus.from_binding(binding)
                )
            pending = self._coordinator.pending_reconciliations.get(
                project.agent_project_id
            )
            if pending is not None:
                raise GitHubRepositoryPartialFailureError(
                    GitHubRepositoryStatus.from_binding(pending)
                )
            connection = self._load_connection(current_user.user_id)
            installation_token = self._authenticator.create_installation_token(
                connection.installation_id
            )
            remote = self._github.create_repository(installation_token, request)
            binding = self._binding_from_remote(
                project.agent_project_id,
                current_user.user_id,
                connection,
                request,
                remote,
            )
            persisted = self._persist_with_retry(binding)
            if persisted is None:
                self._coordinator.remember_partial(binding)
                repository = GitHubRepositoryStatus.from_binding(binding)
                logger.error(
                    "GitHub repository binding reconciliation required: "
                    "agent_project_id=%s repository_id=%s repository_full_name=%s",
                    binding.agent_project_id,
                    binding.repository_id,
                    binding.repository_full_name,
                )
                raise GitHubRepositoryPartialFailureError(repository)
            self._coordinator.pending_reconciliations.pop(
                project.agent_project_id, None
            )
            return GitHubRepositoryStatus.from_binding(persisted)

    def _load_connection(self, owner_id: str) -> GitHubConnection:
        try:
            document = self._connections.find_by_owner(owner_id)
        except GitHubConnectionRepositoryError:
            raise
        if document is None or document.get("status") != "CONNECTED":
            raise GitHubConnectionRequiredError(
                "Connect and verify a personal GitHub account first"
            )
        if document.get("installation_account_type") == "Organization":
            raise GitHubOrganizationConnectionError(
                "Organization GitHub installations are not supported in the current standalone Agent 3 MVP."
            )
        try:
            return GitHubConnection.model_validate(document)
        except ValidationError as exc:
            raise GitHubConnectionRequiredError(
                "GitHub connection is invalid. Reconnect GitHub."
            ) from exc

    def _binding_from_remote(
        self,
        agent_project_id: str,
        owner_id: str,
        connection: GitHubConnection,
        request: GitHubRepositoryCreateRequest,
        remote: dict[str, Any],
    ) -> GitHubRepositoryBinding:
        repository_id = remote.get("id")
        owner = remote.get("owner")
        repository_name = remote.get("name")
        full_name = remote.get("full_name")
        html_url = remote.get("html_url")
        private = remote.get("private")
        default_branch = remote.get("default_branch")
        created_at = remote.get("created_at")
        if not isinstance(owner, dict):
            raise GitHubRepositoryExternalError(
                "GitHub returned an invalid repository response"
            )
        owner_id_value = owner.get("id")
        owner_login = owner.get("login")
        parsed_url = urlparse(html_url) if isinstance(html_url, str) else None
        if (
            not isinstance(repository_id, int)
            or isinstance(repository_id, bool)
            or repository_id <= 0
            or owner_id_value != connection.installation_account_id
            or not isinstance(owner_login, str)
            or not owner_login
            or not isinstance(repository_name, str)
            or not repository_name
            or not isinstance(full_name, str)
            or full_name != f"{owner_login}/{repository_name}"
            or parsed_url is None
            or parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or not isinstance(private, bool)
            or private is not (request.visibility is GitHubRepositoryVisibility.PRIVATE)
            or (default_branch is not None and not isinstance(default_branch, str))
        ):
            raise GitHubRepositoryExternalError(
                "GitHub returned an invalid repository response"
            )
        now = self._clock()
        try:
            return GitHubRepositoryBinding(
                agent_project_id=agent_project_id,
                owner_id=owner_id,
                github_connection_owner_id=owner_id,
                repository_id=repository_id,
                repository_owner=owner_login,
                repository_name=repository_name,
                repository_full_name=full_name,
                repository_html_url=html_url,
                visibility=request.visibility,
                private=private,
                default_branch=default_branch,
                is_empty=True,
                created_at=created_at,
                updated_at=now,
            )
        except ValidationError as exc:
            raise GitHubRepositoryExternalError(
                "GitHub returned an invalid repository response"
            ) from exc

    def _persist_with_retry(
        self, binding: GitHubRepositoryBinding
    ) -> GitHubRepositoryBinding | None:
        for _ in range(2):
            try:
                document = self._bindings.create(binding)
                return GitHubRepositoryBinding.model_validate(document)
            except (GitHubRepositoryBindingRepositoryError, ValidationError):
                try:
                    existing = self._bindings.find_by_project(
                        binding.agent_project_id, binding.owner_id
                    )
                except GitHubRepositoryBindingRepositoryError:
                    existing = None
                if existing is not None:
                    try:
                        persisted = GitHubRepositoryBinding.model_validate(existing)
                    except ValidationError:
                        persisted = None
                    if (
                        persisted is not None
                        and persisted.repository_id == binding.repository_id
                    ):
                        return persisted
        return None
