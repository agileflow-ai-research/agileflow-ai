from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.modules.agents.implementation.github.connection_service import (
    GitHubApiClient,
    GitHubApiError,
    GitHubAuthorizationError,
    GitHubCallbackError,
    GitHubConfiguration,
    GitHubConnectionService,
    GitHubStateError,
    GitHubStateExpiredError,
    GitHubStateStore,
    OrganizationInstallationError,
)
from app.modules.agents.implementation.api.router import (
    get_github_connection_repository,
    get_github_connection_service,
)
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from app.modules.standalone.service import StandaloneService
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


NOW = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.value = NOW

    def __call__(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


class FakeConnectionRepository:
    def __init__(self):
        self.documents = {}
        self.persisted_payloads = []

    def find_by_owner(self, owner_id):
        return self.documents.get(owner_id)

    def upsert(self, connection):
        document = connection.model_dump(mode="python")
        self.persisted_payloads.append(document.copy())
        self.documents[connection.owner_id] = document
        return document.copy()


class FakeGitHubClient:
    def __init__(self):
        self.exchange_error = None
        self.user_error = None
        self.installations_error = None
        self.tokens = []
        self.verifiers = []
        self.user = {
            "id": 123,
            "login": "octocat",
            "avatar_url": "https://avatars.example/octocat.png",
        }
        self.installations = [
            {
                "id": 456,
                "account": {"id": 123, "login": "octocat", "type": "User"},
            }
        ]

    def exchange_code(self, code, code_verifier):
        if self.exchange_error:
            raise self.exchange_error
        self.verifiers.append(code_verifier)
        return "temporary-user-token"

    def get_user(self, token):
        self.tokens.append(token)
        if self.user_error:
            raise self.user_error
        return self.user.copy()

    def get_installations(self, token):
        self.tokens.append(token)
        if self.installations_error:
            raise self.installations_error
        return [item.copy() for item in self.installations]


def configuration():
    return GitHubConfiguration(
        app_id="123",
        client_id="client-id",
        client_secret="test-client-secret",
        app_slug="agileflow-test",
        setup_callback_url="http://backend.test/install-callback",
        oauth_callback_url="http://backend.test/oauth-callback",
        web_base_url="https://github.test",
        api_base_url="https://api.github.test",
        frontend_base_url="http://frontend.test",
        timeout_seconds=3,
    )


@pytest.fixture
def github_context(authentication_context):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    repository = FakeConnectionRepository()
    clock = Clock()
    states = GitHubStateStore(clock=clock)
    github_client = FakeGitHubClient()
    standalone = StandaloneService(projects, runs, clock=clock)
    service = GitHubConnectionService(
        standalone,
        repository,
        states,
        github_client,
        configuration(),
        clock=clock,
    )
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_github_connection_service] = lambda: service
    try:
        yield {
            "authentication": authentication_context,
            "projects": projects,
            "repository": repository,
            "clock": clock,
            "states": states,
            "github_client": github_client,
            "service": service,
        }
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_github_connection_service, None)
        app.dependency_overrides.pop(get_github_connection_repository, None)


def create_project(client, agent_type="IMPLEMENTATION"):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": agent_type, "name": "Builder", "domain": "SaaS"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def connect_path(project_id):
    return f"/api/v1/agents/implementation/{project_id}/github/connect"


def status_path(project_id):
    return f"/api/v1/agents/implementation/{project_id}/github/connection"


def public_user(authentication, user_id="USR-001"):
    from app.modules.auth.schemas import UserPublicResponse

    document = authentication.repository.users[user_id]
    return UserPublicResponse.model_validate(
        {key: value for key, value in document.items() if key != "password_hash"}
    )


def begin_oauth(service, user, project_id, installation_id=456):
    installation = service.begin_connection(project_id, user)
    install_state = parse_qs(urlparse(installation.installation_url).query)["state"][0]
    oauth_url = service.continue_after_installation(install_state, installation_id)
    oauth_query = parse_qs(urlparse(oauth_url).query)
    return oauth_query["state"][0], oauth_query


def test_valid_connect_request_has_random_expiring_server_state(github_context):
    client = github_context["authentication"].client()
    project = create_project(client)
    first = client.post(connect_path(project["agent_project_id"]))
    second = client.post(connect_path(project["agent_project_id"]))
    assert first.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["installation_url"].startswith(
        "https://github.test/apps/agileflow-test/installations/new?state="
    )
    assert first_data["installation_url"] != second_data["installation_url"]
    assert datetime.fromisoformat(first_data["expires_at"]) == NOW + timedelta(minutes=10)
    assert "secret" not in first_data["installation_url"]


def test_connect_rejects_foreign_archived_and_wrong_type_projects(github_context):
    owner = github_context["authentication"].client("USR-001")
    foreign = github_context["authentication"].client("USR-002")
    project = create_project(owner)
    assert foreign.post(connect_path(project["agent_project_id"])).status_code == 404
    owner.patch(
        f'/api/v1/agent-projects/{project["agent_project_id"]}',
        json={"status": "ARCHIVED"},
    )
    assert owner.post(connect_path(project["agent_project_id"])).status_code == 409
    wrong = create_project(owner, "REQUIREMENTS")
    assert owner.post(connect_path(wrong["agent_project_id"])).status_code == 422


def test_missing_github_configuration_is_safe(github_context, monkeypatch):
    client = github_context["authentication"].client()
    project = create_project(client)
    app.dependency_overrides.pop(get_github_connection_service, None)
    app.dependency_overrides[get_github_connection_repository] = (
        lambda: github_context["repository"]
    )
    monkeypatch.setattr(settings, "github_app_client_secret", None)
    response = client.post(connect_path(project["agent_project_id"]))
    assert response.status_code == 503
    assert response.json()["errors"][0]["message"] == (
        "GitHub App connection is not configured"
    )
    app.dependency_overrides[get_github_connection_service] = (
        lambda: github_context["service"]
    )


def test_state_is_required_expiring_and_one_time():
    clock = Clock()
    states = GitHubStateStore(clock=clock)
    with pytest.raises(GitHubStateError):
        states.consume_installation("missing")
    pending = states.create_installation("USR-001", "AGP-001")
    assert states.consume_installation(pending.state) == pending
    with pytest.raises(GitHubStateError):
        states.consume_installation(pending.state)
    expired = states.create_installation("USR-001", "AGP-001")
    clock.advance(minutes=11)
    with pytest.raises(GitHubStateExpiredError):
        states.consume_installation(expired.state)


def test_install_callback_generates_pkce_and_consumes_install_state(github_context):
    client = github_context["authentication"].client()
    project = create_project(client)
    current_user = public_user(github_context["authentication"])
    response = github_context["service"].begin_connection(
        project["agent_project_id"], current_user
    )
    install_state = parse_qs(urlparse(response.installation_url).query)["state"][0]
    oauth_url = github_context["service"].continue_after_installation(
        install_state, 456
    )
    query = parse_qs(urlparse(oauth_url).query)
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://backend.test/oauth-callback"]
    assert query["code_challenge_method"] == ["S256"]
    oauth = github_context["states"].consume_oauth(query["state"][0])
    expected = __import__("base64").urlsafe_b64encode(
        __import__("hashlib").sha256(oauth.code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    assert oauth.code_challenge == expected
    assert oauth.code_verifier not in oauth_url
    with pytest.raises(GitHubStateError):
        github_context["states"].consume_installation(install_state)


def test_callback_routes_reject_missing_unknown_and_reused_state(github_context):
    client = github_context["authentication"].anonymous_client()
    for path in (
        "/api/v1/agents/implementation/github/install-callback",
        "/api/v1/agents/implementation/github/install-callback?state=unknown&installation_id=1",
        "/api/v1/agents/implementation/github/oauth-callback?state=unknown&code=x",
    ):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert "github=error" in response.headers["location"]
        assert "invalid_state" in response.headers["location"]


def test_successful_oauth_verifies_user_installation_and_persists_only_safe_data(
    github_context,
):
    auth = github_context["authentication"]
    client = auth.client()
    project = create_project(client)
    current_user = public_user(auth)
    oauth_state, _ = begin_oauth(
        github_context["service"], current_user, project["agent_project_id"]
    )
    completed_project = github_context["service"].complete_connection(
        state=oauth_state, code="valid-code", oauth_error=None
    )
    assert completed_project == project["agent_project_id"]
    assert github_context["github_client"].tokens == [
        "temporary-user-token",
        "temporary-user-token",
    ]
    persisted = github_context["repository"].persisted_payloads[0]
    assert persisted["owner_id"] == "USR-001"
    assert persisted["github_user_id"] == 123
    assert persisted["installation_id"] == 456
    assert persisted["installation_account_type"] == "User"
    prohibited = {
        "access_token", "refresh_token", "installation_token", "code",
        "state", "oauth_state", "code_verifier", "client_secret",
    }
    assert prohibited.isdisjoint(persisted)
    assert "temporary-user-token" not in str(persisted)
    with pytest.raises(GitHubStateError):
        github_context["service"].complete_connection(
            state=oauth_state, code="reused", oauth_error=None
        )


def test_oauth_denial_bad_code_timeout_and_api_failure(github_context):
    auth = github_context["authentication"]
    client = auth.client()
    project = create_project(client)
    user = public_user(auth)
    denied, _ = begin_oauth(github_context["service"], user, project["agent_project_id"])
    with pytest.raises(GitHubCallbackError, match="not completed"):
        github_context["service"].complete_connection(
            state=denied, code=None, oauth_error="access_denied"
        )

    for failure in (
        GitHubAuthorizationError("bad code"),
        GitHubApiError("timeout"),
        GitHubApiError("api failure"),
    ):
        state, _ = begin_oauth(
            github_context["service"], user, project["agent_project_id"]
        )
        github_context["github_client"].exchange_error = failure
        with pytest.raises(GitHubCallbackError):
            github_context["service"].complete_connection(
                state=state, code="code", oauth_error=None
            )
    assert github_context["repository"].documents == {}


def test_installation_substitution_account_mismatch_and_organization_are_rejected(
    github_context,
):
    auth = github_context["authentication"]
    client = auth.client()
    project = create_project(client)
    user = public_user(auth)
    state, _ = begin_oauth(
        github_context["service"], user, project["agent_project_id"], 999
    )
    with pytest.raises(GitHubCallbackError, match="not accessible"):
        github_context["service"].complete_connection(
            state=state, code="code", oauth_error=None
        )

    github_context["github_client"].installations = [{
        "id": 456,
        "account": {"id": 999, "login": "other", "type": "User"},
    }]
    state, _ = begin_oauth(github_context["service"], user, project["agent_project_id"])
    with pytest.raises(GitHubCallbackError, match="does not match"):
        github_context["service"].complete_connection(
            state=state, code="code", oauth_error=None
        )

    github_context["github_client"].installations = [{
        "id": 456,
        "account": {"id": 123, "login": "org", "type": "Organization"},
    }]
    state, _ = begin_oauth(github_context["service"], user, project["agent_project_id"])
    with pytest.raises(OrganizationInstallationError, match="Organization GitHub"):
        github_context["service"].complete_connection(
            state=state, code="code", oauth_error=None
        )
    assert github_context["repository"].documents == {}


def test_user_connection_is_reused_across_projects_and_isolated_between_users(
    github_context,
):
    auth = github_context["authentication"]
    owner = auth.client("USR-001")
    foreign = auth.client("USR-002")
    first = create_project(owner)
    second = create_project(owner)
    foreign_project = create_project(foreign)
    user = public_user(auth)
    state, _ = begin_oauth(
        github_context["service"], user, first["agent_project_id"]
    )
    github_context["service"].complete_connection(
        state=state, code="code", oauth_error=None
    )
    owner_status = owner.get(status_path(second["agent_project_id"]))
    foreign_status = foreign.get(status_path(foreign_project["agent_project_id"]))
    assert owner_status.json()["data"]["github_login"] == "octocat"
    assert foreign_status.json()["data"] == {"connected": False}


@pytest.mark.parametrize("status_code", [401, 403, 404, 500, 503])
def test_github_http_client_maps_api_failures_without_token_leak(
    monkeypatch, status_code
):
    def fake_get(*args, **kwargs):
        del args, kwargs
        return httpx.Response(status_code, json={"message": "failure"})

    monkeypatch.setattr(httpx, "get", fake_get)
    client = GitHubApiClient(configuration())
    with pytest.raises(GitHubApiError) as caught:
        client.get_user("do-not-leak")
    assert "do-not-leak" not in str(caught.value)


def test_github_http_client_maps_timeout_and_malformed_response(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            httpx.ReadTimeout("timeout")
        ),
    )
    client = GitHubApiClient(configuration())
    with pytest.raises(GitHubApiError, match="unavailable"):
        client.get_user("token")

    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(200, content=b"not-json"),
    )
    with pytest.raises(GitHubApiError, match="invalid response"):
        client.get_user("token")


def test_callback_routes_complete_without_exposing_credentials(github_context):
    auth = github_context["authentication"]
    owner = auth.client()
    anonymous = auth.anonymous_client()
    project = create_project(owner)
    connect = owner.post(connect_path(project["agent_project_id"])).json()["data"]
    install_state = parse_qs(urlparse(connect["installation_url"]).query)["state"][0]
    install = anonymous.get(
        "/api/v1/agents/implementation/github/install-callback",
        params={"state": install_state, "installation_id": 456, "setup_action": "install"},
        follow_redirects=False,
    )
    assert install.status_code == 302
    oauth_state = parse_qs(urlparse(install.headers["location"]).query)["state"][0]
    oauth = anonymous.get(
        "/api/v1/agents/implementation/github/oauth-callback",
        params={"state": oauth_state, "code": "oauth-code"},
        follow_redirects=False,
    )
    assert oauth.status_code == 302
    location = oauth.headers["location"]
    assert location.endswith(
        f'/agent-projects/{project["agent_project_id"]}?github=connected'
    )
    for secret in ("oauth-code", "temporary-user-token", "test-client-secret"):
        assert secret not in location


def test_openapi_exposes_only_implemented_agent3_routes():
    paths = app.openapi()["paths"]
    agent3 = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith("/api/v1/agents/implementation")
        for method in operations
    }
    assert agent3 == {
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/input-files",
        ),
        (
            "DELETE",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}",
        ),
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/extract",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/extraction",
        ),
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/chunks",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/chunks",
        ),
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/rule-detections",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/rule-detections",
        ),
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/zero-shot-detections",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/zero-shot-detections",
        ),
            (
                "POST",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/hybrid-detections",
            ),
            (
                "GET",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/hybrid-detections",
            ),
            (
                "GET",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/human-reviews",
            ),
            (
                "PUT",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/human-reviews/{chunk_id}",
            ),
            (
                "POST",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/canonical-artifacts",
            ),
            (
                "GET",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/canonical-artifacts",
            ),
            (
                "POST",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/semantic-artifacts",
            ),
            (
                "GET",
                "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/semantic-artifacts",
            ),
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/readiness/evaluate",
        ),
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/github/connect",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/github/install-callback",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/github/oauth-callback",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/{agent_project_id}/github/connection",
        ),
        (
            "POST",
            "/api/v1/agents/implementation/{agent_project_id}/github/repository",
        ),
        (
            "GET",
            "/api/v1/agents/implementation/{agent_project_id}/github/repository",
        ),
    }
    assert not any("/run" in path for _, path in agent3)
    assert not any("/generate" in path for _, path in agent3)
    assert not any("image-analysis" in path for _, path in agent3)
    assert not any(
        segment in path
        for _, path in agent3
        for segment in ("/branches", "/commits", "/pulls", "/pull-requests")
    )
