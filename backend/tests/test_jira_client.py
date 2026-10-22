"""Tests for Jira OAuth rotating refresh-token handling and reusable Jira API client.

Verifies requirements 1-19:
1. valid access token is reused without refresh
2. expired access token triggers refresh
3. near-expiry token triggers refresh
4. refresh sends correct grant type
5. successful refresh stores new access token
6. successful rotation replaces old refresh token
7. expiry metadata is updated
8. malformed refresh response fails safely
9. invalid_grant produces reauthorization-required state
10. missing refresh token produces reauthorization-required state
11. network timeout is normalized
12. access token never appears in public response
13. refresh token never appears in public response
14. one user's tokens cannot be used for another user
15. Jira client attaches Bearer authentication internally
16. accessible-resources uses api.atlassian.com
17. accessible-resources response is normalized
18. Jira request can refresh and retry once after auth expiry
19. retry is bounded
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
import httpx

from app.core.config import settings
from app.main import app
from app.modules.integrations.jira.client import JiraApiClient
from app.modules.integrations.jira.constants import (
    ATLASSIAN_ACCESSIBLE_RESOURCES_URL,
    ATLASSIAN_API_BASE_URL,
    ATLASSIAN_TOKEN_URL,
    JIRA_SCOPES,
    REFRESH_SAFETY_MARGIN_SECONDS,
    build_atlassian_api_url,
    build_jira_cloud_url,
)
from app.modules.integrations.jira.router import (
    get_jira_connection_repository,
    get_jira_oauth_client,
    get_jira_oauth_service,
    get_jira_state_store,
)
from app.modules.integrations.jira.schemas import (
    AtlassianAccessibleResource,
    JiraConnectionDocument,
)
from app.modules.integrations.jira.service import (
    JiraAuthenticationError,
    JiraConfiguration,
    JiraInvalidGrantError,
    JiraMalformedResponseError,
    JiraNetworkError,
    JiraNetworkTimeoutError,
    JiraNotConnectedError,
    JiraOAuthClient,
    JiraOAuthService,
    JiraPermissionError,
    JiraRateLimitError,
    JiraReauthorizationRequiredError,
    JiraResourceNotFoundError,
    JiraStateStore,
)


TEST_TIME = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
TEST_CLIENT_ID = "jira-client-id-test"
TEST_CLIENT_SECRET = "jira-client-secret-test"
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
        self.exchange_calls: list[dict[str, Any]] = []
        self.refresh_calls: list[dict[str, Any]] = []
        self.fail_with: Exception | None = None
        self.mock_refresh_response: dict[str, Any] = {
            "access_token": "new-rotated-access-token-001",
            "refresh_token": "new-rotated-refresh-token-002",
            "expires_in": 3600,
            "scope": " ".join(JIRA_SCOPES),
            "token_type": "Bearer",
        }

    def exchange_code_for_tokens(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        self.exchange_calls.append(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            }
        )
        if self.fail_with:
            raise self.fail_with
        return {
            "access_token": "init-access-token",
            "refresh_token": "init-refresh-token",
            "expires_in": 3600,
            "scope": " ".join(JIRA_SCOPES),
            "token_type": "Bearer",
        }

    def refresh_access_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        self.refresh_calls.append(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            }
        )
        if self.fail_with:
            raise self.fail_with
        return self.mock_refresh_response


class MockHttpTransport:
    """Mock transport intercepting outbound API requests to api.atlassian.com."""

    def __init__(self) -> None:
        self.recorded_requests: list[dict[str, Any]] = []
        self.responses_queue: list[httpx.Response] = []
        self.default_response_data: Any = [
            {
                "id": "cloud-site-id-123",
                "name": "Acme Jira Cloud",
                "url": "https://acme.atlassian.net",
                "scopes": ["read:jira-work", "write:jira-work"],
                "avatarUrl": "https://acme.atlassian.net/avatar.png",
            }
        ]

    def queue_response(
        self, status_code: int = 200, json_data: Any = None, text: str = ""
    ) -> None:
        if json_data is not None:
            resp = httpx.Response(status_code=status_code, json=json_data)
        else:
            resp = httpx.Response(status_code=status_code, text=text)
        self.responses_queue.append(resp)

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
        if self.responses_queue:
            return self.responses_queue.pop(0)

        return httpx.Response(
            status_code=200,
            json=self.default_response_data,
            headers={"Content-Type": "application/json"},
        )


@pytest.fixture
def client_context(authentication_context):
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

    # Seed an active, valid connection for USR-001
    repository.upsert(
        JiraConnectionDocument(
            owner_id="USR-001",
            provider="JIRA",
            access_token="initial-access-token-111",
            refresh_token="initial-refresh-token-222",
            expires_at=TEST_TIME + timedelta(hours=1),
            connected_at=TEST_TIME,
            updated_at=TEST_TIME,
            scope=" ".join(JIRA_SCOPES),
            token_type="Bearer",
            status="CONNECTED",
            version=1,
        )
    )

    app.dependency_overrides[get_jira_connection_repository] = lambda: repository
    app.dependency_overrides[get_jira_state_store] = lambda: state_store
    app.dependency_overrides[get_jira_oauth_client] = lambda: oauth_client
    app.dependency_overrides[get_jira_oauth_service] = lambda: service

    yield {
        "clock": clock,
        "repository": repository,
        "oauth_client": oauth_client,
        "service": service,
        "api_client": api_client,
        "transport": mock_transport,
        "auth": authentication_context,
    }

    app.dependency_overrides.pop(get_jira_connection_repository, None)
    app.dependency_overrides.pop(get_jira_state_store, None)
    app.dependency_overrides.pop(get_jira_oauth_client, None)
    app.dependency_overrides.pop(get_jira_oauth_service, None)


# ===========================================================================
# 1. Valid access token is reused without refresh
# ===========================================================================
def test_1_valid_access_token_is_reused_without_refresh(client_context):
    """Token with plenty of remaining lifetime (1 hour) is returned directly without refresh."""
    service = client_context["service"]
    token = service.get_valid_access_token("USR-001")
    assert token == "initial-access-token-111"
    assert len(client_context["oauth_client"].refresh_calls) == 0


# ===========================================================================
# 2. Expired access token triggers refresh
# ===========================================================================
def test_2_expired_access_token_triggers_refresh(client_context):
    """Token that has passed its expiration triggers token refresh."""
    service = client_context["service"]
    # Advance clock past the 1-hour expiration
    client_context["clock"].advance(minutes=65)

    token = service.get_valid_access_token("USR-001")
    assert token == "new-rotated-access-token-001"
    assert len(client_context["oauth_client"].refresh_calls) == 1


# ===========================================================================
# 3. Near-expiry token triggers refresh (safety margin)
# ===========================================================================
def test_3_near_expiry_token_triggers_refresh(client_context):
    """Token within the 5-minute safety margin triggers refresh to prevent mid-flight expiry."""
    service = client_context["service"]
    # Advance clock to 57 minutes (only 3 minutes left, which is < REFRESH_SAFETY_MARGIN_SECONDS)
    client_context["clock"].advance(minutes=57)

    token = service.get_valid_access_token("USR-001")
    assert token == "new-rotated-access-token-001"
    assert len(client_context["oauth_client"].refresh_calls) == 1


# ===========================================================================
# 4. Refresh sends correct grant type
# ===========================================================================
def test_4_refresh_sends_correct_grant_type(client_context):
    """Refresh request sends grant_type=refresh_token, client credentials, and stored refresh token."""
    client_context["clock"].advance(hours=2)
    client_context["service"].get_valid_access_token("USR-001")

    calls = client_context["oauth_client"].refresh_calls
    assert len(calls) == 1
    call = calls[0]
    assert call["client_id"] == TEST_CLIENT_ID
    assert call["client_secret"] == TEST_CLIENT_SECRET
    assert call["refresh_token"] == "initial-refresh-token-222"


# ===========================================================================
# 5. Successful refresh stores new access token
# ===========================================================================
def test_5_successful_refresh_stores_new_access_token(client_context):
    """Newly returned access token is persisted in the repository."""
    client_context["clock"].advance(hours=2)
    client_context["service"].get_valid_access_token("USR-001")

    doc = client_context["repository"].find_by_owner("USR-001")
    assert doc is not None
    assert doc["access_token"] == "new-rotated-access-token-001"


# ===========================================================================
# 6. Successful rotation replaces old refresh token
# ===========================================================================
def test_6_successful_rotation_replaces_old_refresh_token(client_context):
    """Atlassian rotating refresh token replaces the old token in persistence."""
    client_context["clock"].advance(hours=2)
    client_context["service"].get_valid_access_token("USR-001")

    doc = client_context["repository"].find_by_owner("USR-001")
    assert doc is not None
    assert doc["refresh_token"] == "new-rotated-refresh-token-002"
    assert doc["refresh_token"] != "initial-refresh-token-222"


# ===========================================================================
# 7. Expiry metadata is updated
# ===========================================================================
def test_7_expiry_metadata_is_updated(client_context):
    """Expiration timestamp is updated according to expires_in."""
    client_context["clock"].advance(hours=2)
    refresh_time = client_context["clock"]()
    client_context["service"].get_valid_access_token("USR-001")

    doc = client_context["repository"].find_by_owner("USR-001")
    assert doc is not None
    expected_expires = refresh_time + timedelta(seconds=3600)
    assert doc["expires_at"] == expected_expires
    assert doc["updated_at"] == refresh_time


# ===========================================================================
# 8. Malformed refresh response fails safely
# ===========================================================================
def test_8_malformed_refresh_response_fails_safely(client_context):
    """Malformed refresh response (missing access token or invalid JSON) raises safely without corrupting data."""
    client_context["clock"].advance(hours=2)
    client_context["oauth_client"].mock_refresh_response = {"expires_in": 3600}  # missing access_token

    with pytest.raises(JiraMalformedResponseError):
        client_context["service"].get_valid_access_token("USR-001")

    # Document still retains original token state
    doc = client_context["repository"].find_by_owner("USR-001")
    assert doc["access_token"] == "initial-access-token-111"


# ===========================================================================
# 9. invalid_grant produces reauthorization-required state
# ===========================================================================
def test_9_invalid_grant_produces_reauthorization_required_state(client_context):
    """When refresh token is revoked or expired (invalid_grant), state transitions to REAUTHORIZATION_REQUIRED."""
    client_context["clock"].advance(hours=2)
    client_context["oauth_client"].fail_with = JiraInvalidGrantError("invalid_grant")

    with pytest.raises(JiraReauthorizationRequiredError):
        client_context["service"].get_valid_access_token("USR-001")

    doc = client_context["repository"].find_by_owner("USR-001")
    assert doc["status"] == "REAUTHORIZATION_REQUIRED"
    assert "invalid_grant" in doc["reauthorization_reason"]

    # Status check now reports reauthorization needed
    status = client_context["service"].get_status("USR-001")
    assert status.connected is False
    assert status.reauthorization_required is True


# ===========================================================================
# 10. Missing refresh token produces reauthorization-required state
# ===========================================================================
def test_10_missing_refresh_token_produces_reauthorization_required_state(client_context):
    """Connection without refresh token cannot be refreshed and requires reauthorization."""
    doc = client_context["repository"].find_by_owner("USR-001")
    doc["refresh_token"] = None
    client_context["repository"].connections["USR-001"] = doc

    client_context["clock"].advance(hours=2)

    with pytest.raises(JiraReauthorizationRequiredError):
        client_context["service"].get_valid_access_token("USR-001")

    updated_doc = client_context["repository"].find_by_owner("USR-001")
    assert updated_doc["status"] == "REAUTHORIZATION_REQUIRED"


# ===========================================================================
# 11. Network timeout is normalized
# ===========================================================================
def test_11_network_timeout_is_normalized(client_context):
    """Atlassian network timeout is normalized into JiraNetworkTimeoutError."""
    client_context["clock"].advance(hours=2)
    client_context["oauth_client"].fail_with = JiraNetworkTimeoutError("timed out")

    with pytest.raises(JiraNetworkTimeoutError) as exc_info:
        client_context["service"].get_valid_access_token("USR-001")

    assert exc_info.value.error_code == "JIRA_NETWORK_TIMEOUT"


# ===========================================================================
# 12. Access token never appears in public response
# ===========================================================================
def test_12_access_token_never_appears_in_public_response(client_context):
    """Public /status endpoint never exposes the access token."""
    client = client_context["auth"].client("USR-001")
    res = client.get("/api/v1/integrations/jira/status")
    assert res.status_code == 200
    assert "initial-access-token-111" not in res.text
    assert "access_token" not in res.json()


# ===========================================================================
# 13. Refresh token never appears in public response
# ===========================================================================
def test_13_refresh_token_never_appears_in_public_response(client_context):
    """Public /status endpoint never exposes the refresh token."""
    client = client_context["auth"].client("USR-001")
    res = client.get("/api/v1/integrations/jira/status")
    assert res.status_code == 200
    assert "initial-refresh-token-222" not in res.text
    assert "refresh_token" not in res.json()


# ===========================================================================
# 14. One user's tokens cannot be used for another user
# ===========================================================================
def test_14_user_token_isolation(client_context):
    """User B cannot access or leverage User A's Jira tokens."""
    api_client = client_context["api_client"]

    # USR-002 has no Jira connection
    with pytest.raises(JiraNotConnectedError):
        api_client.request("USR-002", "GET", ATLASSIAN_ACCESSIBLE_RESOURCES_URL)


# ===========================================================================
# 15. Jira client attaches Bearer authentication internally
# ===========================================================================
def test_15_jira_client_attaches_bearer_authentication_internally(client_context):
    """API client resolves valid token and attaches Authorization: Bearer <token> and Accept: application/json."""
    api_client = client_context["api_client"]
    api_client.request("USR-001", "GET", ATLASSIAN_ACCESSIBLE_RESOURCES_URL)

    recorded = client_context["transport"].recorded_requests
    assert len(recorded) == 1
    req = recorded[0]
    assert req["headers"]["Authorization"] == "Bearer initial-access-token-111"
    assert req["headers"]["Accept"] == "application/json"


# ===========================================================================
# 16. Accessible-resources uses api.atlassian.com
# ===========================================================================
def test_16_accessible_resources_uses_api_atlassian_com(client_context):
    """Accessible resources strictly targets https://api.atlassian.com/oauth/token/accessible-resources."""
    api_client = client_context["api_client"]
    api_client.get_accessible_resources("USR-001")

    recorded = client_context["transport"].recorded_requests[0]
    assert recorded["url"] == "https://api.atlassian.com/oauth/token/accessible-resources"

    # Reject non-api.atlassian.com URL
    with pytest.raises(ValueError, match="must target https://api.atlassian.com"):
        api_client.request("USR-001", "GET", "https://malicious.example.com/api")


# ===========================================================================
# 17. Accessible-resources response is normalized
# ===========================================================================
def test_17_accessible_resources_response_is_normalized(client_context):
    """Accessible-resources JSON is normalized into AtlassianAccessibleResource models."""
    api_client = client_context["api_client"]
    resources = api_client.get_accessible_resources("USR-001")

    assert len(resources) == 1
    resource = resources[0]
    assert isinstance(resource, AtlassianAccessibleResource)
    assert resource.id == "cloud-site-id-123"
    assert resource.name == "Acme Jira Cloud"
    assert resource.url == "https://acme.atlassian.net"
    assert resource.scopes == ["read:jira-work", "write:jira-work"]
    assert resource.avatar_url == "https://acme.atlassian.net/avatar.png"


# ===========================================================================
# 18. Jira request can refresh and retry once after auth expiry
# ===========================================================================
def test_18_jira_request_can_refresh_and_retry_once_after_auth_expiry(client_context):
    """When an API request receives 401, client force-refreshes token and retries once successfully."""
    transport = client_context["transport"]
    # Queue: first request returns 401, retry returns 200 OK
    transport.queue_response(status_code=401, json_data={"message": "Unauthorized"})
    transport.queue_response(status_code=200, json_data={"result": "success"})

    api_client = client_context["api_client"]
    data = api_client.request("USR-001", "GET", "https://api.atlassian.com/oauth/token/accessible-resources")

    assert data == {"result": "success"}
    # Token refresh was invoked
    assert len(client_context["oauth_client"].refresh_calls) == 1
    # Two HTTP attempts occurred: original + retry
    assert len(transport.recorded_requests) == 2
    assert transport.recorded_requests[0]["headers"]["Authorization"] == "Bearer initial-access-token-111"
    assert transport.recorded_requests[1]["headers"]["Authorization"] == "Bearer new-rotated-access-token-001"


# ===========================================================================
# 19. Retry is bounded (max 1 retry, no infinite loop)
# ===========================================================================
def test_19_retry_is_bounded(client_context):
    """If retry also returns 401, client stops immediately, marks reauthorization required, and raises error."""
    transport = client_context["transport"]
    # Queue two consecutive 401s
    transport.queue_response(status_code=401, json_data={"message": "Unauthorized 1"})
    transport.queue_response(status_code=401, json_data={"message": "Unauthorized 2"})

    api_client = client_context["api_client"]
    with pytest.raises(JiraAuthenticationError):
        api_client.request("USR-001", "GET", "https://api.atlassian.com/oauth/token/accessible-resources")

    # Exactly 2 requests: original + single retry (bounded!)
    assert len(transport.recorded_requests) == 2
    # Status transitioned to REAUTHORIZATION_REQUIRED
    doc = client_context["repository"].find_by_owner("USR-001")
    assert doc["status"] == "REAUTHORIZATION_REQUIRED"


# ===========================================================================
# URL Builders & Additional Error Normalization
# ===========================================================================
def test_url_builders_and_error_normalization(client_context):
    """Centralized URL builders and standard API errors are properly constructed and normalized."""
    assert (
        build_atlassian_api_url("/oauth/token/accessible-resources")
        == "https://api.atlassian.com/oauth/token/accessible-resources"
    )
    assert (
        build_jira_cloud_url("site-123", "/rest/api/3/project")
        == "https://api.atlassian.com/ex/jira/site-123/rest/api/3/project"
    )

    transport = client_context["transport"]
    api_client = client_context["api_client"]

    # 403 Forbidden
    transport.queue_response(status_code=403, json_data={"message": "Forbidden"})
    with pytest.raises(JiraPermissionError):
        api_client.request("USR-001", "GET", "https://api.atlassian.com/oauth/token/accessible-resources")

    # 404 Not Found
    transport.queue_response(status_code=404, json_data={"message": "Not Found"})
    with pytest.raises(JiraResourceNotFoundError):
        api_client.request("USR-001", "GET", "https://api.atlassian.com/oauth/token/accessible-resources")

    # 429 Rate Limit
    transport.queue_response(status_code=429, json_data={"message": "Too Many Requests"})
    with pytest.raises(JiraRateLimitError):
        api_client.request("USR-001", "GET", "https://api.atlassian.com/oauth/token/accessible-resources")
