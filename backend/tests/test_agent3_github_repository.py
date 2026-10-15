from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.main import app
from app.modules.agents.implementation.github_auth import (
    GitHubAppAuthenticationError,
    GitHubAppAuthenticator,
    GitHubAppPermissionError,
    GitHubExternalServiceError,
    GitHubInstallationRevokedError,
    GitHubPrivateKeyError,
)
from app.modules.agents.implementation.github_repository_service import (
    GitHubRepositoryAlreadyBoundError,
    GitHubRepositoryAuthenticationError,
    GitHubRepositoryClient,
    GitHubRepositoryCreationCoordinator,
    GitHubRepositoryExternalError,
    GitHubRepositoryNameConflictError,
    GitHubRepositoryPermissionError,
    GitHubRepositoryService,
    GitHubRepositoryValidationError,
)
from app.modules.agents.implementation.repository import (
    GitHubRepositoryBindingRepositoryError,
)
from app.modules.agents.implementation.router import get_github_repository_service
from app.modules.agents.implementation.schemas import (
    GitHubRepositoryCreateRequest,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from app.modules.standalone.service import StandaloneService
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


NOW = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)


def connection(owner_id="USR-001", **overrides):
    document = {
        "owner_id": owner_id,
        "provider": "GITHUB",
        "github_user_id": 123,
        "github_login": "octocat",
        "github_avatar_url": "https://avatars.example/octocat.png",
        "installation_id": 456,
        "installation_account_id": 123,
        "installation_account_login": "octocat",
        "installation_account_type": "User",
        "status": "CONNECTED",
        "connected_at": NOW,
        "updated_at": NOW,
    }
    document.update(overrides)
    return document


def remote_repository(private=True, name="quickbook", **overrides):
    document = {
        "id": 789,
        "owner": {"id": 123, "login": "octocat"},
        "name": name,
        "full_name": f"octocat/{name}",
        "html_url": f"https://github.example/octocat/{name}",
        "private": private,
        "default_branch": "main",
        "created_at": "2026-10-16T08:00:00Z",
    }
    document.update(overrides)
    return document


class FakeConnectionRepository:
    def __init__(self):
        self.documents = {"USR-001": connection()}

    def find_by_owner(self, owner_id):
        document = self.documents.get(owner_id)
        return document.copy() if document else None


class FakeBindingRepository:
    def __init__(self):
        self.documents = {}
        self.persisted = []
        self.fail_creates = 0

    def find_by_project(self, project_id, owner_id):
        document = self.documents.get(project_id)
        if document is None or document["owner_id"] != owner_id:
            return None
        return document.copy()

    def create(self, binding):
        if self.fail_creates:
            self.fail_creates -= 1
            raise GitHubRepositoryBindingRepositoryError("failed")
        if binding.agent_project_id in self.documents:
            raise GitHubRepositoryBindingRepositoryError("duplicate")
        document = binding.model_dump(mode="python")
        self.persisted.append(document.copy())
        self.documents[binding.agent_project_id] = document
        return document.copy()


class FakeAuthenticator:
    def __init__(self):
        self.installation_ids = []
        self.error = None

    def create_installation_token(self, installation_id):
        self.installation_ids.append(installation_id)
        if self.error:
            raise self.error
        return "ephemeral-installation-token"


class FakeRepositoryClient:
    def __init__(self):
        self.calls = []
        self.error = None

    def create_repository(self, token, request):
        self.calls.append((token, request))
        if self.error:
            raise self.error
        return remote_repository(
            private=request.visibility.value == "PRIVATE", name=request.name
        )


def create_project(client, agent_type="IMPLEMENTATION"):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": agent_type, "name": "Builder", "domain": "SaaS"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def repository_path(project_id):
    return f"/api/v1/agents/implementation/{project_id}/github/repository"


def create_payload(**overrides):
    payload = {
        "name": "quickbook",
        "description": "QuickBook appointment booking system",
        "visibility": "PRIVATE",
    }
    payload.update(overrides)
    return payload


def public_user(authentication, user_id="USR-001"):
    document = authentication.repository.users[user_id]
    return UserPublicResponse.model_validate(
        {key: value for key, value in document.items() if key != "password_hash"}
    )


@pytest.fixture
def repository_context(authentication_context):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    connections = FakeConnectionRepository()
    bindings = FakeBindingRepository()
    authenticator = FakeAuthenticator()
    github = FakeRepositoryClient()
    standalone = StandaloneService(projects, runs, clock=lambda: NOW)
    coordinator = GitHubRepositoryCreationCoordinator()
    service = GitHubRepositoryService(
        standalone,
        connections,
        bindings,
        authenticator,
        github,
        clock=lambda: NOW,
        coordinator=coordinator,
    )
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_github_repository_service] = lambda: service
    try:
        yield {
            "authentication": authentication_context,
            "projects": projects,
            "connections": connections,
            "bindings": bindings,
            "authenticator": authenticator,
            "github": github,
            "service": service,
            "coordinator": coordinator,
        }
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_github_repository_service, None)


@pytest.fixture
def rsa_material(tmp_path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path = tmp_path / "github-app.pem"
    path.write_bytes(private_pem)
    return path, public_pem


def auth_settings(private_key_path):
    return settings.model_copy(
        update={
            "github_app_client_id": "Iv1.client-id",
            "github_app_private_key_path": private_key_path,
            "github_api_base_url": "https://api.github.test",
            "github_http_timeout_seconds": 3,
        }
    )


def test_app_jwt_uses_rs256_client_id_and_safe_time_window(rsa_material):
    private_path, public_pem = rsa_material
    authenticator = GitHubAppAuthenticator(
        auth_settings(private_path), clock=lambda: NOW
    )
    token = authenticator.create_app_jwt()
    header = jwt.get_unverified_header(token)
    claims = jwt.decode(
        token,
        public_pem,
        algorithms=["RS256"],
        options={"verify_iat": False, "verify_exp": False},
    )
    assert header["alg"] == "RS256"
    assert claims["iss"] == "Iv1.client-id"
    assert claims["iat"] == int((NOW - timedelta(seconds=60)).timestamp())
    assert claims["exp"] == int((NOW + timedelta(minutes=9)).timestamp())
    assert claims["exp"] - int(NOW.timestamp()) <= 600


def test_private_key_missing_unreadable_and_invalid_are_safe(tmp_path, monkeypatch):
    missing = GitHubAppAuthenticator(auth_settings(None), clock=lambda: NOW)
    with pytest.raises(GitHubPrivateKeyError, match="not configured"):
        missing.create_app_jwt()

    unreadable_path = tmp_path / "unreadable.pem"
    unreadable_path.write_text("key", encoding="utf-8")
    original_read_text = type(unreadable_path).read_text

    def unreadable(self, *args, **kwargs):
        if self == unreadable_path:
            raise PermissionError("denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(type(unreadable_path), "read_text", unreadable)
    with pytest.raises(GitHubPrivateKeyError, match="cannot be read"):
        GitHubAppAuthenticator(
            auth_settings(unreadable_path), clock=lambda: NOW
        ).create_app_jwt()

    invalid_path = tmp_path / "invalid.pem"
    invalid_path.write_text("not a private key", encoding="utf-8")
    with pytest.raises(GitHubPrivateKeyError, match="invalid"):
        GitHubAppAuthenticator(
            auth_settings(invalid_path), clock=lambda: NOW
        ).create_app_jwt()


def test_installation_token_request_success_is_ephemeral(
    rsa_material, monkeypatch, caplog
):
    private_path, _ = rsa_material
    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return httpx.Response(
            201,
            json={
                "token": "installation-secret",
                "expires_at": "2026-10-16T09:00:00Z",
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    authenticator = GitHubAppAuthenticator(
        auth_settings(private_path), clock=lambda: NOW
    )
    assert authenticator.create_installation_token(456) == "installation-secret"
    assert captured["url"].endswith("/app/installations/456/access_tokens")
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert "installation-secret" not in caplog.text
    assert captured["headers"]["Authorization"] not in caplog.text


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, GitHubAppAuthenticationError),
        (403, GitHubAppPermissionError),
        (404, GitHubInstallationRevokedError),
        (500, GitHubExternalServiceError),
    ],
)
def test_installation_token_maps_github_failures(
    rsa_material, monkeypatch, status_code, error_type
):
    private_path, _ = rsa_material
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(status_code, json={"message": "safe"}),
    )
    with pytest.raises(error_type):
        GitHubAppAuthenticator(
            auth_settings(private_path), clock=lambda: NOW
        ).create_installation_token(456)


def test_installation_token_maps_timeout_and_malformed_response(
    rsa_material, monkeypatch
):
    private_path, _ = rsa_material
    authenticator = GitHubAppAuthenticator(
        auth_settings(private_path), clock=lambda: NOW
    )
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ReadTimeout("timeout")),
    )
    with pytest.raises(GitHubExternalServiceError, match="temporarily"):
        authenticator.create_installation_token(456)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(201, content=b"not-json"),
    )
    with pytest.raises(GitHubExternalServiceError, match="invalid"):
        authenticator.create_installation_token(456)


@pytest.mark.parametrize("visibility", ["PRIVATE", "PUBLIC"])
def test_valid_repository_creation_and_safe_binding(repository_context, visibility):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    response = owner.post(
        repository_path(project["agent_project_id"]),
        json=create_payload(visibility=visibility),
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["created"] is True
    assert data["visibility"] == visibility
    assert data["private"] is (visibility == "PRIVATE")
    assert data["is_empty"] is True
    assert repository_context["authenticator"].installation_ids == [456]
    token, request = repository_context["github"].calls[0]
    assert token == "ephemeral-installation-token"
    assert request.visibility.value == visibility
    persisted = repository_context["bindings"].persisted[0]
    forbidden = {"token", "access_token", "jwt", "private_key", "client_secret"}
    assert forbidden.isdisjoint(persisted)
    assert "ephemeral-installation-token" not in response.text


@pytest.mark.parametrize(
    "name",
    ["", "   ", ".", "..", "owner/repo", r"owner\repo", "https://github.com/o/r", "bad name"],
)
def test_repository_name_validation_rejects_non_names(repository_context, name):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    response = owner.post(
        repository_path(project["agent_project_id"]),
        json=create_payload(name=name),
    )
    assert response.status_code == 422
    assert repository_context["github"].calls == []


def test_project_ownership_status_and_type_are_enforced(repository_context):
    owner = repository_context["authentication"].client("USR-001")
    foreign = repository_context["authentication"].client("USR-002")
    project = create_project(owner)
    assert foreign.post(repository_path(project["agent_project_id"]), json=create_payload()).status_code == 404
    owner.patch(
        f'/api/v1/agent-projects/{project["agent_project_id"]}',
        json={"status": "ARCHIVED"},
    )
    assert owner.post(repository_path(project["agent_project_id"]), json=create_payload()).status_code == 409
    wrong = create_project(owner, "REQUIREMENTS")
    assert owner.post(repository_path(wrong["agent_project_id"]), json=create_payload()).status_code == 422


def test_connection_is_required_and_organization_is_rejected(repository_context):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    repository_context["connections"].documents.clear()
    assert owner.post(repository_path(project["agent_project_id"]), json=create_payload()).status_code == 409
    repository_context["connections"].documents["USR-001"] = connection(
        installation_account_type="Organization"
    )
    response = owner.post(repository_path(project["agent_project_id"]), json=create_payload())
    assert response.status_code == 422
    assert "Organization" in response.text


def test_duplicate_binding_returns_conflict_and_existing_metadata(repository_context):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    path = repository_path(project["agent_project_id"])
    first = owner.post(path, json=create_payload())
    second = owner.post(path, json=create_payload(name="another"))
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["data"]["repository"]["full_name"] == "octocat/quickbook"
    assert len(repository_context["github"].calls) == 1


def test_same_process_concurrent_creation_is_guarded(repository_context):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    user = public_user(repository_context["authentication"])
    request = GitHubRepositoryCreateRequest.model_validate(create_payload())

    def create():
        try:
            repository_context["service"].create_repository(
                project["agent_project_id"], user, request
            )
            return "created"
        except GitHubRepositoryAlreadyBoundError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create(), range(2)))
    assert sorted(results) == ["conflict", "created"]
    assert len(repository_context["github"].calls) == 1


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GitHubRepositoryNameConflictError("exists"), 409),
        (GitHubRepositoryAuthenticationError("auth"), 409),
        (GitHubRepositoryPermissionError("permission"), 403),
        (GitHubRepositoryValidationError("invalid"), 422),
        (GitHubRepositoryExternalError("unavailable"), 502),
    ],
)
def test_repository_errors_are_safely_mapped(repository_context, error, status_code):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    repository_context["github"].error = error
    response = owner.post(repository_path(project["agent_project_id"]), json=create_payload())
    assert response.status_code == status_code
    assert "ephemeral-installation-token" not in response.text


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GitHubPrivateKeyError("private key unavailable"), 503),
        (GitHubAppAuthenticationError("app auth failed"), 502),
        (GitHubAppPermissionError("permission denied"), 403),
        (GitHubInstallationRevokedError("reconnect GitHub"), 409),
        (GitHubExternalServiceError("GitHub unavailable"), 502),
    ],
)
def test_app_authentication_errors_are_safely_mapped(
    repository_context, error, status_code
):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    repository_context["authenticator"].error = error
    response = owner.post(repository_path(project["agent_project_id"]), json=create_payload())
    assert response.status_code == status_code
    assert "private-key" not in response.text
    assert "ephemeral-installation-token" not in response.text


def test_repository_http_request_is_empty_and_has_no_initialization_fields(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return httpx.Response(201, json=remote_repository())

    monkeypatch.setattr(httpx, "post", fake_post)
    client = GitHubRepositoryClient("https://api.github.test", 3)
    request = GitHubRepositoryCreateRequest.model_validate(create_payload())
    client.create_repository("token", request)
    assert captured["url"] == "https://api.github.test/user/repos"
    assert captured["json"] == {
        "name": "quickbook",
        "description": "QuickBook appointment booking system",
        "private": True,
        "auto_init": False,
    }
    assert {"gitignore_template", "license_template", "has_wiki"}.isdisjoint(
        captured["json"]
    )


def test_repository_http_request_maps_public_visibility(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        del url
        captured.update(kwargs)
        return httpx.Response(201, json=remote_repository(private=False))

    monkeypatch.setattr(httpx, "post", fake_post)
    request = GitHubRepositoryCreateRequest.model_validate(
        create_payload(visibility="PUBLIC")
    )
    GitHubRepositoryClient("https://api.github.test", 3).create_repository(
        "token", request
    )
    assert captured["json"]["private"] is False
    assert captured["json"]["auto_init"] is False


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, GitHubRepositoryAuthenticationError),
        (403, GitHubRepositoryPermissionError),
        (422, GitHubRepositoryValidationError),
        (500, GitHubRepositoryExternalError),
    ],
)
def test_repository_http_client_maps_statuses(monkeypatch, status_code, error_type):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(status_code, json={"message": "failure"}),
    )
    with pytest.raises(error_type):
        GitHubRepositoryClient("https://api.github.test", 3).create_repository(
            "secret", GitHubRepositoryCreateRequest.model_validate(create_payload())
        )


def test_repository_http_client_maps_collision_timeout_and_malformed(monkeypatch):
    client = GitHubRepositoryClient("https://api.github.test", 3)
    request = GitHubRepositoryCreateRequest.model_validate(create_payload())
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            422, json={"errors": [{"message": "name already exists on this account"}]}
        ),
    )
    with pytest.raises(GitHubRepositoryNameConflictError):
        client.create_repository("secret", request)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ReadTimeout("timeout")),
    )
    with pytest.raises(GitHubRepositoryExternalError):
        client.create_repository("secret", request)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(201, content=b"not-json"),
    )
    with pytest.raises(GitHubRepositoryExternalError, match="invalid"):
        client.create_repository("secret", request)


def test_binding_reload_and_project_isolation(repository_context):
    owner = repository_context["authentication"].client("USR-001")
    foreign = repository_context["authentication"].client("USR-002")
    first = create_project(owner)
    second = create_project(owner)
    foreign_project = create_project(foreign)
    owner.post(repository_path(first["agent_project_id"]), json=create_payload())
    reloaded = owner.get(repository_path(first["agent_project_id"]))
    other = owner.get(repository_path(second["agent_project_id"]))
    foreign_status = foreign.get(repository_path(foreign_project["agent_project_id"]))
    assert reloaded.json()["data"]["full_name"] == "octocat/quickbook"
    assert other.json()["data"] == {"created": False}
    assert foreign_status.json()["data"] == {"created": False}
    assert foreign.get(repository_path(first["agent_project_id"])).status_code == 404


def test_remote_success_local_failure_is_partial_and_guarded(repository_context, caplog):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    path = repository_path(project["agent_project_id"])
    repository_context["bindings"].fail_creates = 2
    first = owner.post(path, json=create_payload())
    second = owner.post(path, json=create_payload())
    assert first.status_code == 502
    assert first.json()["data"]["repository"]["full_name"] == "octocat/quickbook"
    assert second.status_code == 502
    assert len(repository_context["github"].calls) == 1
    assert "ephemeral-installation-token" not in caplog.text
    assert "octocat/quickbook" in caplog.text


def test_selected_repository_installation_needs_no_extra_selection(repository_context):
    owner = repository_context["authentication"].client()
    project = create_project(owner)
    response = owner.post(repository_path(project["agent_project_id"]), json=create_payload())
    assert response.status_code == 201
    assert repository_context["authenticator"].installation_ids == [456]
    assert all("selection" not in key for key in repository_context["bindings"].persisted[0])
