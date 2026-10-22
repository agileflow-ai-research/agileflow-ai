"""Comprehensive test suite for Jira Cloud resource discovery and selection.

Verifies all 26 requirements:
1. sites require Jira connection
2. accessible sites are normalized
3. multiple sites are returned without auto-selection
4. inaccessible cloud_id cannot be selected
5. valid site can be selected
6. projects require selected site
7. projects use selected cloud_id
8. project results are normalized
9. pagination works
10. inaccessible project cannot be selected
11. valid project selection persists
12. boards require selected project
13. board discovery filters by selected project
14. board discovery requests type=scrum
15. board pagination works
16. multiple boards are not auto-selected
17. inaccessible board cannot be selected
18. non-Scrum board cannot be selected
19. valid Scrum board selection persists
20. changing site clears project/board
21. changing project invalidates old board appropriately
22. context endpoint exposes no tokens
23. user A cannot access user B's Jira context
24. token refresh still works
25. Prompt 3 OAuth tests still pass
26. Prompt 4 Jira client tests still pass
Also tests centralized OAuth scopes including read:project:jira and error normalization.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.integrations.jira.client import JiraApiClient
from app.modules.integrations.jira.constants import (
    ATLASSIAN_ACCESSIBLE_RESOURCES_URL,
    JIRA_SCOPES,
)
from app.modules.integrations.jira.router import (
    get_jira_api_client,
    get_jira_connection_repository,
    get_jira_oauth_client,
    get_jira_oauth_service,
    get_jira_state_store,
)
from app.modules.integrations.jira.schemas import (
    JiraConnectionDocument,
    JiraSelectedBoard,
    JiraSelectedProject,
    JiraSelectedSite,
)
from app.modules.integrations.jira.service import (
    JiraConfiguration,
    JiraOAuthService,
    JiraRateLimitError,
    JiraStateStore,
)


TEST_TIME = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
TEST_CLIENT_ID = "test-jira-client-id-discovery"
TEST_CLIENT_SECRET = "test-jira-client-secret-discovery"
TEST_REDIRECT_URI = "http://localhost:8000/api/v1/integrations/jira/callback"
TEST_RETURN_URL = "http://localhost:5173/integrations/jira"


class Clock:
    def __init__(self, initial_time: datetime = TEST_TIME) -> None:
        self.time = initial_time

    def __call__(self) -> datetime:
        return self.time

    def advance(self, **kwargs) -> None:
        self.time += timedelta(**kwargs)


class FakeJiraConnectionRepository:
    def __init__(self) -> None:
        self.connections: dict[str, dict[str, Any]] = {}

    def find_by_owner(self, owner_id: str) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        return doc.copy() if doc is not None else None

    def upsert(self, connection: JiraConnectionDocument) -> dict[str, Any]:
        doc = connection.model_dump(mode="python")
        self.connections[connection.owner_id] = doc
        return doc.copy()

    def update_tokens_atomic(
        self,
        owner_id: str,
        expected_refresh_token: str,
        new_access_token: str,
        new_refresh_token: str | None,
        expires_at: datetime,
        now: datetime,
    ) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc or doc.get("refresh_token") != expected_refresh_token:
            return None

        doc["access_token"] = new_access_token
        doc["expires_at"] = expires_at
        doc["updated_at"] = now
        doc["status"] = "CONNECTED"
        doc["reauthorization_reason"] = None
        doc["version"] = doc.get("version", 1) + 1
        if new_refresh_token is not None:
            doc["refresh_token"] = new_refresh_token
        self.connections[owner_id] = doc
        return doc.copy()

    def update_selected_site(
        self, owner_id: str, site: JiraSelectedSite
    ) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc:
            return None
        current_site = doc.get("selected_site")
        is_changing = not current_site or current_site.get("cloud_id") != site.cloud_id

        doc["selected_site"] = site.model_dump(mode="python")
        doc["updated_at"] = datetime.now(timezone.utc)
        if is_changing:
            doc["selected_project"] = None
            doc["selected_board"] = None
        self.connections[owner_id] = doc
        return doc.copy()

    def update_selected_project(
        self, owner_id: str, project: JiraSelectedProject
    ) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc:
            return None
        current_proj = doc.get("selected_project")
        is_changing = (
            not current_proj
            or current_proj.get("project_id") != project.project_id
            or current_proj.get("project_key") != project.project_key
        )

        doc["selected_project"] = project.model_dump(mode="python")
        doc["updated_at"] = datetime.now(timezone.utc)
        if is_changing:
            doc["selected_board"] = None
        self.connections[owner_id] = doc
        return doc.copy()

    def update_selected_board(
        self, owner_id: str, board: JiraSelectedBoard
    ) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc:
            return None
        doc["selected_board"] = board.model_dump(mode="python")
        doc["updated_at"] = datetime.now(timezone.utc)
        self.connections[owner_id] = doc
        return doc.copy()

    def mark_reauthorization_required(
        self, owner_id: str, reason: str = "Reauthorization required"
    ) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc:
            return None
        doc["status"] = "REAUTHORIZATION_REQUIRED"
        doc["reauthorization_reason"] = reason
        doc["updated_at"] = datetime.now(timezone.utc)
        self.connections[owner_id] = doc
        return doc.copy()

    def delete_by_owner(self, owner_id: str) -> bool:
        return self.connections.pop(owner_id, None) is not None


class FakeJiraOAuthClient:
    def __init__(self) -> None:
        self.refresh_calls: list[dict[str, Any]] = []
        self.fail_with: Exception | None = None
        self.mock_refresh_response: dict[str, Any] = {
            "access_token": "refreshed-discovery-access-token",
            "refresh_token": "refreshed-discovery-refresh-token",
            "expires_in": 3600,
            "scope": " ".join(JIRA_SCOPES),
            "token_type": "Bearer",
        }

    def exchange_code_for_tokens(self, **kwargs) -> dict[str, Any]:
        return {
            "access_token": "init-access-token",
            "refresh_token": "init-refresh-token",
            "expires_in": 3600,
            "scope": " ".join(JIRA_SCOPES),
            "token_type": "Bearer",
        }

    def refresh_access_token(self, **kwargs) -> dict[str, Any]:
        self.refresh_calls.append(kwargs)
        if self.fail_with:
            raise self.fail_with
        return self.mock_refresh_response


class MockHttpTransport:
    """Mock transport intercepting all outbound API requests to api.atlassian.com."""

    def __init__(self) -> None:
        self.recorded_requests: list[dict[str, Any]] = []
        self.url_handlers: dict[str, Any] = {}
        self.response_queue: list[httpx.Response] = []

    def queue_response(
        self, status_code: int = 200, json_data: Any = None, text: str = ""
    ) -> None:
        if json_data is not None:
            resp = httpx.Response(status_code=status_code, json=json_data)
        else:
            resp = httpx.Response(status_code=status_code, text=text)
        self.response_queue.append(resp)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout: float = 10.0,
    ) -> httpx.Response:
        self.recorded_requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "params": params,
                "json": json,
            }
        )
        if self.response_queue:
            return self.response_queue.pop(0)

        # Default URL matchers
        if url.endswith("/oauth/token/accessible-resources"):
            return httpx.Response(
                status_code=200,
                json=[
                    {
                        "id": "site-cloud-111",
                        "name": "Acme Jira Cloud 1",
                        "url": "https://acme1.atlassian.net",
                        "scopes": [
                            "read:jira-work",
                            "read:project:jira",
                            "read:board-scope:jira-software",
                        ],
                        "avatarUrl": "https://acme1.atlassian.net/avatar.png",
                    },
                    {
                        "id": "site-cloud-222",
                        "name": "Acme Jira Cloud 2",
                        "url": "https://acme2.atlassian.net",
                        "scopes": ["read:jira-work"],
                        "avatarUrl": "https://acme2.atlassian.net/avatar2.png",
                    },
                ],
            )

        if "rest/api/3/project/search" in url:
            return httpx.Response(
                status_code=200,
                json={
                    "startAt": params.get("startAt", 0) if params else 0,
                    "maxResults": params.get("maxResults", 50) if params else 50,
                    "total": 2,
                    "values": [
                        {
                            "id": "10001",
                            "key": "PROJ",
                            "name": "Project Alpha",
                            "projectTypeKey": "software",
                            "simplified": False,
                            "avatarUrls": {
                                "48x48": "https://acme1.atlassian.net/proj.png"
                            },
                        },
                        {
                            "id": "10002",
                            "key": "BETA",
                            "name": "Project Beta",
                            "projectTypeKey": "software",
                            "simplified": True,
                            "avatarUrls": {
                                "48x48": "https://acme1.atlassian.net/beta.png"
                            },
                        },
                    ],
                },
            )

        if "rest/api/3/project/" in url:
            proj_id_or_key = url.split("rest/api/3/project/")[-1]
            if proj_id_or_key in ("PROJ", "10001"):
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": "10001",
                        "key": "PROJ",
                        "name": "Project Alpha",
                        "projectTypeKey": "software",
                    },
                )
            if proj_id_or_key in ("BETA", "10002"):
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": "10002",
                        "key": "BETA",
                        "name": "Project Beta",
                        "projectTypeKey": "software",
                    },
                )
            return httpx.Response(status_code=404, json={"errorMessages": ["Not found"]})

        if url.endswith("rest/agile/1.0/board"):
            return httpx.Response(
                status_code=200,
                json={
                    "startAt": params.get("startAt", 0) if params else 0,
                    "maxResults": params.get("maxResults", 50) if params else 50,
                    "total": 2,
                    "values": [
                        {"id": 101, "name": "Alpha Scrum Board", "type": "scrum"},
                        {"id": 102, "name": "Alpha Second Scrum Board", "type": "scrum"},
                    ],
                },
            )

        if "rest/agile/1.0/board/" in url:
            board_id = url.split("rest/agile/1.0/board/")[-1]
            if board_id == "101":
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": 101,
                        "name": "Alpha Scrum Board",
                        "type": "scrum",
                        "location": {
                            "projectId": "10001",
                            "projectKey": "PROJ",
                        },
                    },
                )
            if board_id == "102":
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": 102,
                        "name": "Alpha Second Scrum Board",
                        "type": "scrum",
                        "location": {
                            "projectId": "10001",
                            "projectKey": "PROJ",
                        },
                    },
                )
            if board_id == "103":
                # Kanban board
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": 103,
                        "name": "Alpha Kanban Board",
                        "type": "kanban",
                        "location": {
                            "projectId": "10001",
                            "projectKey": "PROJ",
                        },
                    },
                )
            if board_id == "104":
                # Belongs to a different project
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": 104,
                        "name": "Other Project Scrum Board",
                        "type": "scrum",
                        "location": {
                            "projectId": "99999",
                            "projectKey": "OTHER",
                        },
                    },
                )
            return httpx.Response(status_code=404, json={"errorMessages": ["Board not found"]})

        return httpx.Response(status_code=200, json={})


@pytest.fixture
def discovery_context(authentication_context):
    clock = Clock()
    repository = FakeJiraConnectionRepository()
    state_store = JiraStateStore(clock=clock, ttl=timedelta(minutes=10))
    oauth_client = FakeJiraOAuthClient()
    mock_transport = MockHttpTransport()

    config = JiraConfiguration(
        client_id=TEST_CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET,
        redirect_uri=TEST_REDIRECT_URI,
        frontend_return_url=TEST_RETURN_URL,
        timeout_seconds=10.0,
    )

    service = JiraOAuthService(
        configuration=config,
        repository=repository,
        state_store=state_store,
        client=oauth_client,
        clock=clock,
    )

    api_client = JiraApiClient(
        service=service,
        http_client=mock_transport,
        timeout_seconds=10.0,
    )

    app.dependency_overrides[get_jira_connection_repository] = lambda: repository
    app.dependency_overrides[get_jira_state_store] = lambda: state_store
    app.dependency_overrides[get_jira_oauth_client] = lambda: oauth_client
    app.dependency_overrides[get_jira_oauth_service] = lambda: service
    app.dependency_overrides[get_jira_api_client] = lambda: api_client

    def create_connection(
        owner_id: str,
        access_token: str = "valid-access-token",
        refresh_token: str = "valid-refresh-token",
        expires_at: datetime | None = None,
        selected_site: JiraSelectedSite | None = None,
        selected_project: JiraSelectedProject | None = None,
        selected_board: JiraSelectedBoard | None = None,
    ) -> JiraConnectionDocument:
        exp = expires_at if expires_at is not None else clock() + timedelta(hours=1)
        doc = JiraConnectionDocument(
            owner_id=owner_id,
            provider="JIRA",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            scope=" ".join(JIRA_SCOPES),
            expires_at=exp,
            connected_at=clock(),
            updated_at=clock(),
            status="CONNECTED",
            selected_site=selected_site,
            selected_project=selected_project,
            selected_board=selected_board,
        )
        repository.upsert(doc)
        return doc

    yield {
        "clock": clock,
        "repository": repository,
        "state_store": state_store,
        "oauth_client": oauth_client,
        "service": service,
        "api_client": api_client,
        "mock_transport": mock_transport,
        "auth": authentication_context,
        "create_connection": create_connection,
    }

    app.dependency_overrides.pop(get_jira_connection_repository, None)
    app.dependency_overrides.pop(get_jira_state_store, None)
    app.dependency_overrides.pop(get_jira_oauth_client, None)
    app.dependency_overrides.pop(get_jira_oauth_service, None)
    app.dependency_overrides.pop(get_jira_api_client, None)


# ===========================================================================
# Centralized OAuth Scopes Test
# ===========================================================================
def test_centralized_oauth_scopes_include_read_project_jira():
    """Verify that centralized JIRA_SCOPES contains read:project:jira and all required scopes."""
    assert "read:project:jira" in JIRA_SCOPES
    assert "read:jira-work" in JIRA_SCOPES
    assert "write:jira-work" in JIRA_SCOPES
    assert "read:board-scope:jira-software" in JIRA_SCOPES
    assert "read:sprint:jira-software" in JIRA_SCOPES
    assert "write:sprint:jira-software" in JIRA_SCOPES
    assert "offline_access" in JIRA_SCOPES


# ===========================================================================
# 1. Sites require Jira connection
# ===========================================================================
def test_1_sites_require_jira_connection(discovery_context):
    """GET /api/v1/integrations/jira/sites requires active connection."""
    client = discovery_context["auth"].client("USR-001")
    res = client.get("/api/v1/integrations/jira/sites")
    assert res.status_code == 400
    assert "JIRA_NOT_CONNECTED" in res.text


# ===========================================================================
# 2. Accessible sites are normalized
# ===========================================================================
def test_2_accessible_sites_are_normalized(discovery_context):
    """GET /api/v1/integrations/jira/sites returns normalized safe fields."""
    discovery_context["create_connection"]("USR-001")
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/sites")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2
    site = data[0]
    assert site["cloud_id"] == "site-cloud-111"
    assert site["name"] == "Acme Jira Cloud 1"
    assert site["url"] == "https://acme1.atlassian.net"
    assert site["avatar_url"] == "https://acme1.atlassian.net/avatar.png"
    # Never leak tokens or client secret
    assert "access_token" not in res.text
    assert "refresh_token" not in res.text
    assert "client_secret" not in res.text


# ===========================================================================
# 3. Multiple sites are returned without auto-selection
# ===========================================================================
def test_3_multiple_sites_returned_without_auto_selection(discovery_context):
    """Multiple sites are returned; none is auto-selected."""
    discovery_context["create_connection"]("USR-001")
    client = discovery_context["auth"].client("USR-001")

    res_sites = client.get("/api/v1/integrations/jira/sites")
    assert len(res_sites.json()) == 2

    res_ctx = client.get("/api/v1/integrations/jira/context")
    assert res_ctx.status_code == 200
    ctx = res_ctx.json()
    assert ctx["connected"] is True
    assert ctx["site"] is None
    assert ctx["project"] is None
    assert ctx["board"] is None


# ===========================================================================
# 4. Inaccessible cloud_id cannot be selected
# ===========================================================================
def test_4_inaccessible_cloud_id_cannot_be_selected(discovery_context):
    """PUT /api/v1/integrations/jira/site rejects unauthorized cloud_id."""
    discovery_context["create_connection"]("USR-001")
    client = discovery_context["auth"].client("USR-001")

    res = client.put(
        "/api/v1/integrations/jira/site",
        json={"cloud_id": "malicious-unauthorized-site-id"},
    )
    assert res.status_code == 404
    assert "JIRA_SITE_NOT_ACCESSIBLE" in res.text


# ===========================================================================
# 5. Valid site can be selected
# ===========================================================================
def test_5_valid_site_can_be_selected(discovery_context):
    """PUT /api/v1/integrations/jira/site persists valid authorized site."""
    discovery_context["create_connection"]("USR-001")
    client = discovery_context["auth"].client("USR-001")

    res = client.put(
        "/api/v1/integrations/jira/site",
        json={"cloud_id": "site-cloud-111"},
    )
    assert res.status_code == 200
    site = res.json()
    assert site["cloud_id"] == "site-cloud-111"
    assert site["site_name"] == "Acme Jira Cloud 1"
    assert site["site_url"] == "https://acme1.atlassian.net"

    # Context reflects selected site
    res_ctx = client.get("/api/v1/integrations/jira/context")
    ctx = res_ctx.json()
    assert ctx["site"]["cloud_id"] == "site-cloud-111"
    assert ctx["site"]["name"] == "Acme Jira Cloud 1"


# ===========================================================================
# 6. Projects require selected site
# ===========================================================================
def test_6_projects_require_selected_site(discovery_context):
    """GET and PUT /project require selected Jira site."""
    discovery_context["create_connection"]("USR-001")
    client = discovery_context["auth"].client("USR-001")

    # No site selected
    res_get = client.get("/api/v1/integrations/jira/projects")
    assert res_get.status_code == 400
    assert "JIRA_SITE_NOT_SELECTED" in res_get.text

    res_put = client.put(
        "/api/v1/integrations/jira/project",
        json={"project_key": "PROJ"},
    )
    assert res_put.status_code == 400
    assert "JIRA_SITE_NOT_SELECTED" in res_put.text


# ===========================================================================
# 7. Projects use selected cloud_id
# ===========================================================================
def test_7_projects_use_selected_cloud_id(discovery_context):
    """GET /projects issues Jira Platform REST v3 with selected cloud_id."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        site_url="https://acme1.atlassian.net",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/projects")
    assert res.status_code == 200

    reqs = discovery_context["mock_transport"].recorded_requests
    project_req = next(r for r in reqs if "rest/api/3/project/search" in r["url"])
    assert "site-cloud-111" in project_req["url"]
    assert project_req["params"]["typeKey"] == "software"


# ===========================================================================
# 8. Project results are normalized
# ===========================================================================
def test_8_project_results_are_normalized(discovery_context):
    """GET /projects returns safe normalized project data."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/projects")
    assert res.status_code == 200
    projects = res.json()
    assert len(projects) == 2
    proj = projects[0]
    assert proj["id"] == "10001"
    assert proj["key"] == "PROJ"
    assert proj["name"] == "Project Alpha"
    assert proj["project_type_key"] == "software"
    assert proj["simplified"] is False
    assert proj["avatar_url"] == "https://acme1.atlassian.net/proj.png"


# ===========================================================================
# 9. Pagination works for projects
# ===========================================================================
def test_9_project_pagination_works(discovery_context):
    """GET /projects propagates start_at and max_results."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/projects?start_at=10&max_results=5")
    assert res.status_code == 200

    reqs = discovery_context["mock_transport"].recorded_requests
    project_req = next(r for r in reqs if "rest/api/3/project/search" in r["url"])
    assert project_req["params"]["startAt"] == 10
    assert project_req["params"]["maxResults"] == 5


# ===========================================================================
# 10. Inaccessible project cannot be selected
# ===========================================================================
def test_10_inaccessible_project_cannot_be_selected(discovery_context):
    """PUT /project rejects project not found on the selected site."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    client = discovery_context["auth"].client("USR-001")

    res = client.put(
        "/api/v1/integrations/jira/project",
        json={"project_key": "NONEXISTENT"},
    )
    assert res.status_code == 404
    assert "JIRA_PROJECT_NOT_ACCESSIBLE" in res.text


# ===========================================================================
# 11. Valid project selection persists
# ===========================================================================
def test_11_valid_project_selection_persists(discovery_context):
    """PUT /project persists safe selected project metadata."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    client = discovery_context["auth"].client("USR-001")

    res = client.put(
        "/api/v1/integrations/jira/project",
        json={"project_key": "PROJ"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == "10001"
    assert data["project_key"] == "PROJ"
    assert data["project_name"] == "Project Alpha"
    assert data["project_type_key"] == "software"

    # Context reflects selected project
    res_ctx = client.get("/api/v1/integrations/jira/context")
    ctx = res_ctx.json()
    assert ctx["project"]["id"] == "10001"
    assert ctx["project"]["key"] == "PROJ"
    assert ctx["project"]["name"] == "Project Alpha"


# ===========================================================================
# 12. Boards require selected project
# ===========================================================================
def test_12_boards_require_selected_project(discovery_context):
    """GET and PUT /board require selected Jira project."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    client = discovery_context["auth"].client("USR-001")

    res_get = client.get("/api/v1/integrations/jira/boards")
    assert res_get.status_code == 400
    assert "JIRA_PROJECT_NOT_SELECTED" in res_get.text

    res_put = client.put(
        "/api/v1/integrations/jira/board",
        json={"board_id": 101},
    )
    assert res_put.status_code == 400
    assert "JIRA_PROJECT_NOT_SELECTED" in res_put.text


# ===========================================================================
# 13. Board discovery filters by selected project
# ===========================================================================
def test_13_board_discovery_filters_by_selected_project(discovery_context):
    """GET /boards passes selected project key/id to Jira Agile API."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001", selected_site=site, selected_project=project
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/boards")
    assert res.status_code == 200

    reqs = discovery_context["mock_transport"].recorded_requests
    board_req = next(r for r in reqs if "rest/agile/1.0/board" in r["url"])
    assert board_req["params"]["projectKeyOrId"] == "PROJ"


# ===========================================================================
# 14. Board discovery requests type=scrum
# ===========================================================================
def test_14_board_discovery_requests_type_scrum(discovery_context):
    """GET /boards enforces type=scrum in query params."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001", selected_site=site, selected_project=project
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/boards")
    assert res.status_code == 200

    reqs = discovery_context["mock_transport"].recorded_requests
    board_req = next(r for r in reqs if "rest/agile/1.0/board" in r["url"])
    assert board_req["params"]["type"] == "scrum"


# ===========================================================================
# 15. Board pagination works
# ===========================================================================
def test_15_board_pagination_works(discovery_context):
    """GET /boards passes start_at and max_results."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001", selected_site=site, selected_project=project
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/boards?start_at=20&max_results=10")
    assert res.status_code == 200

    reqs = discovery_context["mock_transport"].recorded_requests
    board_req = next(r for r in reqs if "rest/agile/1.0/board" in r["url"])
    assert board_req["params"]["startAt"] == 20
    assert board_req["params"]["maxResults"] == 10


# ===========================================================================
# 16. Multiple boards are not auto-selected
# ===========================================================================
def test_16_multiple_boards_are_not_auto_selected(discovery_context):
    """Multiple Scrum boards returned; none is auto-selected."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001", selected_site=site, selected_project=project
    )
    client = discovery_context["auth"].client("USR-001")

    res_boards = client.get("/api/v1/integrations/jira/boards")
    assert len(res_boards.json()) == 2

    res_ctx = client.get("/api/v1/integrations/jira/context")
    ctx = res_ctx.json()
    assert ctx["board"] is None


# ===========================================================================
# 17. Inaccessible board cannot be selected
# ===========================================================================
def test_17_inaccessible_board_cannot_be_selected(discovery_context):
    """PUT /board rejects board not found or belonging to different project."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001", selected_site=site, selected_project=project
    )
    client = discovery_context["auth"].client("USR-001")

    # Non-existent board
    res_none = client.put(
        "/api/v1/integrations/jira/board",
        json={"board_id": 999},
    )
    assert res_none.status_code == 404
    assert "JIRA_BOARD_NOT_ACCESSIBLE" in res_none.text

    # Board belonging to OTHER project
    res_other = client.put(
        "/api/v1/integrations/jira/board",
        json={"board_id": 104},
    )
    assert res_other.status_code == 404
    assert "JIRA_BOARD_NOT_ACCESSIBLE" in res_other.text


# ===========================================================================
# 18. Non-Scrum board cannot be selected
# ===========================================================================
def test_18_non_scrum_board_cannot_be_selected(discovery_context):
    """PUT /board rejects Kanban boards with JIRA_BOARD_NOT_SCRUM."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001", selected_site=site, selected_project=project
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.put(
        "/api/v1/integrations/jira/board",
        json={"board_id": 103},  # board 103 is kanban
    )
    assert res.status_code == 400
    assert "JIRA_BOARD_NOT_SCRUM" in res.text


# ===========================================================================
# 19. Valid Scrum board selection persists
# ===========================================================================
def test_19_valid_scrum_board_selection_persists(discovery_context):
    """PUT /board persists Scrum board and updates context."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001", selected_site=site, selected_project=project
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.put(
        "/api/v1/integrations/jira/board",
        json={"board_id": 101},
    )
    assert res.status_code == 200
    board = res.json()
    assert board["board_id"] == 101
    assert board["board_name"] == "Alpha Scrum Board"
    assert board["board_type"] == "scrum"

    # Context reflects full hierarchy
    res_ctx = client.get("/api/v1/integrations/jira/context")
    ctx = res_ctx.json()
    assert ctx["connected"] is True
    assert ctx["site"]["cloud_id"] == "site-cloud-111"
    assert ctx["project"]["key"] == "PROJ"
    assert ctx["board"]["id"] == 101
    assert ctx["board"]["name"] == "Alpha Scrum Board"
    assert ctx["board"]["type"] == "scrum"


# ===========================================================================
# 20. Changing site clears project/board
# ===========================================================================
def test_20_changing_site_clears_project_and_board(discovery_context):
    """Changing selected Jira site automatically clears selected project and board."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    board = JiraSelectedBoard(
        board_id=101,
        board_name="Alpha Scrum Board",
        board_type="scrum",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001",
        selected_site=site,
        selected_project=project,
        selected_board=board,
    )
    client = discovery_context["auth"].client("USR-001")

    # Select site 222
    res = client.put(
        "/api/v1/integrations/jira/site",
        json={"cloud_id": "site-cloud-222"},
    )
    assert res.status_code == 200

    res_ctx = client.get("/api/v1/integrations/jira/context")
    ctx = res_ctx.json()
    assert ctx["site"]["cloud_id"] == "site-cloud-222"
    assert ctx["project"] is None
    assert ctx["board"] is None


# ===========================================================================
# 21. Changing project invalidates old board appropriately
# ===========================================================================
def test_21_changing_project_invalidates_old_board(discovery_context):
    """Changing selected project clears previously selected board."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    board = JiraSelectedBoard(
        board_id=101,
        board_name="Alpha Scrum Board",
        board_type="scrum",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001",
        selected_site=site,
        selected_project=project,
        selected_board=board,
    )
    client = discovery_context["auth"].client("USR-001")

    # Change project to BETA
    res = client.put(
        "/api/v1/integrations/jira/project",
        json={"project_key": "BETA"},
    )
    assert res.status_code == 200
    assert res.json()["project_key"] == "BETA"

    res_ctx = client.get("/api/v1/integrations/jira/context")
    ctx = res_ctx.json()
    assert ctx["project"]["key"] == "BETA"
    assert ctx["board"] is None  # Cleared


# ===========================================================================
# 22. Context endpoint exposes no tokens
# ===========================================================================
def test_22_context_endpoint_exposes_no_tokens(discovery_context):
    """GET /context never includes access_token, refresh_token, or client_secret."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    project = JiraSelectedProject(
        project_id="10001",
        project_key="PROJ",
        project_name="Project Alpha",
        project_type_key="software",
        selected_at=TEST_TIME,
    )
    board = JiraSelectedBoard(
        board_id=101,
        board_name="Alpha Scrum Board",
        board_type="scrum",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"](
        "USR-001",
        selected_site=site,
        selected_project=project,
        selected_board=board,
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/context")
    assert res.status_code == 200
    text = res.text
    assert "access_token" not in text
    assert "refresh_token" not in text
    assert "client_secret" not in text
    assert "valid-access-token" not in text
    assert "valid-refresh-token" not in text


# ===========================================================================
# 23. User A cannot access User B's Jira context
# ===========================================================================
def test_23_user_a_cannot_access_user_b_context(discovery_context):
    """User B cannot access or modify User A's Jira context."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)

    client_b = discovery_context["auth"].client("USR-002")

    # User B has no connection
    res_b_ctx = client_b.get("/api/v1/integrations/jira/context")
    assert res_b_ctx.status_code == 200
    assert res_b_ctx.json() == {
        "connected": False,
        "site": None,
        "project": None,
        "board": None,
    }

    # User B cannot access projects or sites
    res_b_sites = client_b.get("/api/v1/integrations/jira/sites")
    assert res_b_sites.status_code == 400
    assert "JIRA_NOT_CONNECTED" in res_b_sites.text


# ===========================================================================
# 24. Token refresh still works with discovery
# ===========================================================================
def test_24_token_refresh_still_works_with_discovery(discovery_context):
    """Expired access token is automatically refreshed when discovery endpoint is called."""
    expired_at = TEST_TIME - timedelta(minutes=10)
    discovery_context["create_connection"]("USR-001", expires_at=expired_at)
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/sites")
    assert res.status_code == 200
    assert len(discovery_context["oauth_client"].refresh_calls) == 1

    # Check updated token in repository
    doc = discovery_context["repository"].find_by_owner("USR-001")
    assert doc["access_token"] == "refreshed-discovery-access-token"
    assert doc["refresh_token"] == "refreshed-discovery-refresh-token"


# ===========================================================================
# Normalized Error Handling Tests
# ===========================================================================
def test_rate_limiting_normalized_error(discovery_context):
    """Atlassian 429 returns normalized JIRA_RATE_LIMITED with 429 status."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    discovery_context["mock_transport"].queue_response(
        status_code=429,
        text="Rate limit exceeded",
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/projects")
    assert res.status_code == 429
    assert "JIRA_RATE_LIMITED" in res.text


def test_reauthorization_required_normalized_error(discovery_context):
    """Connection in REAUTHORIZATION_REQUIRED status returns 401 JIRA_REAUTHORIZATION_REQUIRED."""
    discovery_context["create_connection"]("USR-001")
    discovery_context["repository"].mark_reauthorization_required(
        "USR-001", "Token revoked"
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/sites")
    assert res.status_code == 401
    assert "JIRA_REAUTHORIZATION_REQUIRED" in res.text


def test_upstream_500_normalized_error(discovery_context):
    """Atlassian 500 error returns normalized JIRA_UPSTREAM_ERROR with 502 status."""
    site = JiraSelectedSite(
        cloud_id="site-cloud-111",
        site_name="Acme Jira Cloud 1",
        selected_at=TEST_TIME,
    )
    discovery_context["create_connection"]("USR-001", selected_site=site)
    discovery_context["mock_transport"].queue_response(
        status_code=500,
        text="Internal Server Error",
    )
    client = discovery_context["auth"].client("USR-001")

    res = client.get("/api/v1/integrations/jira/projects")
    assert res.status_code == 502
    assert "JIRA_UPSTREAM_ERROR" in res.text
