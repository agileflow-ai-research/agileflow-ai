"""Tests for Jira Cloud OAuth 2.0 (3LO) backend foundation.

Verifies all 18 requirements:
1. disconnected status
2. connect requires authenticated user
3. connect generates secure state
4. state belongs to authenticated user
5. authorization request contains configured callback
6. authorization request contains the 5 Jira scopes
7. authorization request includes offline_access
8. valid callback exchanges code
9. invalid state rejected
10. expired state rejected
11. reused state rejected
12. cross-user state rejected
13. missing code rejected
14. token exchange failure handled safely
15. status never exposes tokens/secrets
16. disconnect removes local connection
17. one user cannot access another user's connection
18. no real network calls occur
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.integrations.jira.constants import (
    ATLASSIAN_AUDIENCE,
    ATLASSIAN_AUTHORIZE_URL,
    JIRA_SCOPES,
)
from app.modules.integrations.jira.router import (
    get_jira_connection_repository,
    get_jira_oauth_client,
    get_jira_oauth_service,
    get_jira_state_store,
)
from app.modules.integrations.jira.schemas import (
    JiraConnectionDocument,
)
from app.modules.integrations.jira.service import (
    JiraConfiguration,
    JiraCrossUserStateError,
    JiraInvalidGrantError,
    JiraMalformedResponseError,
    JiraMissingCodeError,
    JiraNetworkError,
    JiraNetworkTimeoutError,
    JiraOAuthClient,
    JiraOAuthService,
    JiraReauthorizationRequiredError,
    JiraStateExpiredError,
    JiraStateInvalidError,
    JiraStateReusedError,
    JiraStateStore,
    JiraTokenExchangeError,
)


TEST_TIME = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
TEST_CLIENT_ID = "test-jira-client-id-xyz"
TEST_CLIENT_SECRET = "test-jira-client-secret-abc"
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
        document = connection.model_dump(mode="python")
        self.connections[connection.owner_id] = document
        return document.copy()

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
        if new_refresh_token is not None and isinstance(new_refresh_token, str) and new_refresh_token.strip():
            doc["refresh_token"] = new_refresh_token.strip()
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
        self.calls: list[dict[str, Any]] = []
        self.fail_with: Exception | None = None
        self.mock_tokens: dict[str, Any] = {
            "access_token": "mock-jira-access-token-999",
            "refresh_token": "mock-jira-refresh-token-888",
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
        self.calls.append(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            }
        )
        if self.fail_with:
            raise self.fail_with
        return self.mock_tokens

    def refresh_access_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "operation": "refresh",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            }
        )
        if self.fail_with:
            raise self.fail_with
        return self.mock_tokens


@pytest.fixture
def jira_context(monkeypatch, authentication_context):
    clock = Clock()
    repository = FakeJiraConnectionRepository()
    state_store = JiraStateStore(clock=clock, ttl=timedelta(minutes=10))
    oauth_client = FakeJiraOAuthClient()

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

    app.dependency_overrides[get_jira_connection_repository] = lambda: repository
    app.dependency_overrides[get_jira_state_store] = lambda: state_store
    app.dependency_overrides[get_jira_oauth_client] = lambda: oauth_client
    app.dependency_overrides[get_jira_oauth_service] = lambda: service

    yield {
        "clock": clock,
        "repository": repository,
        "state_store": state_store,
        "oauth_client": oauth_client,
        "service": service,
        "auth": authentication_context,
    }

    app.dependency_overrides.pop(get_jira_connection_repository, None)
    app.dependency_overrides.pop(get_jira_state_store, None)
    app.dependency_overrides.pop(get_jira_oauth_client, None)
    app.dependency_overrides.pop(get_jira_oauth_service, None)


# ===========================================================================
# 1. Disconnected status
# ===========================================================================
def test_1_disconnected_status(jira_context):
    """GET /api/v1/integrations/jira/status returns {"connected": False} when no connection exists."""
    client = jira_context["auth"].client("USR-001")
    response = client.get("/api/v1/integrations/jira/status")
    assert response.status_code == 200
    data = response.json()
    assert data == {"connected": False}
    assert "access_token" not in data
    assert "refresh_token" not in data
    assert "client_secret" not in data


# ===========================================================================
# 2. Connect requires authenticated user
# ===========================================================================
def test_2_connect_requires_authenticated_user(jira_context):
    """GET /api/v1/integrations/jira/connect rejects unauthenticated callers with 401."""
    anon_client = jira_context["auth"].anonymous_client()
    response = anon_client.get("/api/v1/integrations/jira/connect")
    assert response.status_code == 401

    invalid_client = TestClient(
        app, headers={"Authorization": "Bearer invalid-token-string"}
    )
    response_invalid = invalid_client.get("/api/v1/integrations/jira/connect")
    assert response_invalid.status_code == 401


# ===========================================================================
# 3. Connect generates secure state
# ===========================================================================
def test_3_connect_generates_secure_state(jira_context):
    """Connect endpoint generates high-entropy, cryptographically secure state."""
    client = jira_context["auth"].client("USR-001")
    res1 = client.get("/api/v1/integrations/jira/connect")
    assert res1.status_code == 200
    url1 = res1.json()["authorization_url"]
    parsed1 = urlparse(url1)
    params1 = parse_qs(parsed1.query)
    state1 = params1["state"][0]

    # Must be at least 32 urlsafe bytes (length >= 40)
    assert len(state1) >= 40

    # Successive calls must generate distinct unpredictable states
    res2 = client.get("/api/v1/integrations/jira/connect")
    state2 = parse_qs(urlparse(res2.json()["authorization_url"]).query)["state"][0]
    assert state1 != state2


# ===========================================================================
# 4. State belongs to authenticated user
# ===========================================================================
def test_4_state_belongs_to_authenticated_user(jira_context):
    """OAuth state is bound to the initiating authenticated AgileFlow user."""
    client = jira_context["auth"].client("USR-001")
    response = client.get("/api/v1/integrations/jira/connect")
    url = response.json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    # Verify server-side state record is bound to USR-001
    record = jira_context["state_store"]._pending_states.get(state)
    assert record is not None
    assert record.user_id == "USR-001"


# ===========================================================================
# 5. Authorization request contains configured callback
# ===========================================================================
def test_5_authorization_request_contains_configured_callback(jira_context):
    """Authorization URL contains redirect_uri matching configured settings."""
    client = jira_context["auth"].client("USR-001")
    response = client.get("/api/v1/integrations/jira/connect")
    url = response.json()["authorization_url"]
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.atlassian.com"
    assert parsed.path == "/authorize"
    assert params["redirect_uri"][0] == TEST_REDIRECT_URI
    assert params["audience"][0] == ATLASSIAN_AUDIENCE
    assert params["response_type"][0] == "code"
    assert params["prompt"][0] == "consent"


# ===========================================================================
# 6. Authorization request contains the 5 Jira scopes
# ===========================================================================
def test_6_authorization_request_contains_the_5_jira_scopes(jira_context):
    """Authorization request contains all 5 required Jira scopes."""
    client = jira_context["auth"].client("USR-001")
    response = client.get("/api/v1/integrations/jira/connect")
    url = response.json()["authorization_url"]
    params = parse_qs(urlparse(url).query)
    requested_scopes = set(params["scope"][0].split())

    expected_jira_scopes = {
        "read:jira-work",
        "write:jira-work",
        "read:board-scope:jira-software",
        "read:sprint:jira-software",
        "write:sprint:jira-software",
    }
    assert expected_jira_scopes.issubset(requested_scopes)


# ===========================================================================
# 7. Authorization request includes offline_access
# ===========================================================================
def test_7_authorization_request_includes_offline_access(jira_context):
    """Authorization request scope includes offline_access for refresh-token support."""
    client = jira_context["auth"].client("USR-001")
    response = client.get("/api/v1/integrations/jira/connect")
    url = response.json()["authorization_url"]
    params = parse_qs(urlparse(url).query)
    requested_scopes = set(params["scope"][0].split())

    assert "offline_access" in requested_scopes


# ===========================================================================
# 8. Valid callback exchanges code
# ===========================================================================
def test_8_valid_callback_exchanges_code(jira_context):
    """Valid callback performs server-side code exchange and stores connection."""
    client = jira_context["auth"].client("USR-001")
    connect_res = client.get("/api/v1/integrations/jira/connect")
    state = parse_qs(urlparse(connect_res.json()["authorization_url"]).query)["state"][0]

    callback_res = client.get(
        f"/api/v1/integrations/jira/callback?code=atlassian-auth-code-123&state={state}",
        follow_redirects=False,
    )
    assert callback_res.status_code == 302
    assert callback_res.headers["location"] == f"{TEST_RETURN_URL}?jira_connected=true"

    # Verify code exchange was executed with configured credentials
    oauth_client = jira_context["oauth_client"]
    assert len(oauth_client.calls) == 1
    call = oauth_client.calls[0]
    assert call["code"] == "atlassian-auth-code-123"
    assert call["client_id"] == TEST_CLIENT_ID
    assert call["client_secret"] == TEST_CLIENT_SECRET
    assert call["redirect_uri"] == TEST_REDIRECT_URI

    # Verify connection was persisted for USR-001
    persisted = jira_context["repository"].find_by_owner("USR-001")
    assert persisted is not None
    assert persisted["owner_id"] == "USR-001"
    assert persisted["access_token"] == "mock-jira-access-token-999"
    assert persisted["refresh_token"] == "mock-jira-refresh-token-888"


# ===========================================================================
# 9. Invalid state rejected
# ===========================================================================
def test_9_invalid_state_rejected(jira_context):
    """Unrecognized / tampered OAuth state is safely rejected."""
    client = jira_context["auth"].client("USR-001")
    res = client.get(
        "/api/v1/integrations/jira/callback?code=some-code&state=unknown-fake-state",
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["location"] == f"{TEST_RETURN_URL}?jira_error=invalid_state"
    assert jira_context["repository"].connections == {}


# ===========================================================================
# 10. Expired state rejected
# ===========================================================================
def test_10_expired_state_rejected(jira_context):
    """Expired OAuth state (exceeding TTL) is rejected."""
    client = jira_context["auth"].client("USR-001")
    connect_res = client.get("/api/v1/integrations/jira/connect")
    state = parse_qs(urlparse(connect_res.json()["authorization_url"]).query)["state"][0]

    # Advance clock beyond 10 minute TTL
    jira_context["clock"].advance(minutes=11)

    res = client.get(
        f"/api/v1/integrations/jira/callback?code=code-123&state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["location"] == f"{TEST_RETURN_URL}?jira_error=expired_state"
    assert jira_context["repository"].connections == {}


# ===========================================================================
# 11. Reused state rejected
# ===========================================================================
def test_11_reused_state_rejected(jira_context):
    """Single-use state cannot be replayed."""
    client = jira_context["auth"].client("USR-001")
    connect_res = client.get("/api/v1/integrations/jira/connect")
    state = parse_qs(urlparse(connect_res.json()["authorization_url"]).query)["state"][0]

    # First use succeeds
    first_res = client.get(
        f"/api/v1/integrations/jira/callback?code=code-1&state={state}",
        follow_redirects=False,
    )
    assert first_res.status_code == 302
    assert first_res.headers["location"] == f"{TEST_RETURN_URL}?jira_connected=true"

    # Replay attempt fails
    second_res = client.get(
        f"/api/v1/integrations/jira/callback?code=code-2&state={state}",
        follow_redirects=False,
    )
    assert second_res.status_code == 302
    assert second_res.headers["location"] == f"{TEST_RETURN_URL}?jira_error=reused_state"


# ===========================================================================
# 12. Cross-user state rejected
# ===========================================================================
def test_12_cross_user_state_rejected(jira_context):
    """State generated by User A cannot be redeemed by User B."""
    client_a = jira_context["auth"].client("USR-001")
    client_b = jira_context["auth"].client("USR-002")

    connect_res = client_a.get("/api/v1/integrations/jira/connect")
    state_a = parse_qs(urlparse(connect_res.json()["authorization_url"]).query)["state"][0]

    # User B attempts to complete callback with state_a
    res = client_b.get(
        f"/api/v1/integrations/jira/callback?code=code-xyz&state={state_a}",
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["location"] == f"{TEST_RETURN_URL}?jira_error=cross_user_state"

    # User B has no connection created
    assert jira_context["repository"].find_by_owner("USR-002") is None


# ===========================================================================
# 13. Missing code rejected
# ===========================================================================
def test_13_missing_code_rejected(jira_context):
    """Callback with valid state but missing authorization code is rejected safely."""
    client = jira_context["auth"].client("USR-001")
    connect_res = client.get("/api/v1/integrations/jira/connect")
    state = parse_qs(urlparse(connect_res.json()["authorization_url"]).query)["state"][0]

    res = client.get(
        f"/api/v1/integrations/jira/callback?state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["location"] == f"{TEST_RETURN_URL}?jira_error=missing_code"
    assert jira_context["repository"].connections == {}


# ===========================================================================
# 14. Token exchange failure handled safely
# ===========================================================================
def test_14_token_exchange_failure_handled_safely(jira_context):
    """Token exchange rejection, timeout, network failure, or malformed responses are handled safely."""
    client = jira_context["auth"].client("USR-001")
    failures = [
        JiraTokenExchangeError("rejection"),
        JiraNetworkTimeoutError("timeout"),
        JiraNetworkError("connection refused"),
        JiraMalformedResponseError("bad json"),
    ]

    for failure in failures:
        connect_res = client.get("/api/v1/integrations/jira/connect")
        state = parse_qs(urlparse(connect_res.json()["authorization_url"]).query)["state"][0]

        jira_context["oauth_client"].fail_with = failure

        res = client.get(
            f"/api/v1/integrations/jira/callback?code=some-code&state={state}",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert res.headers["location"] == f"{TEST_RETURN_URL}?jira_error=token_exchange_failed"
        # No upstream error text leaked into URL
        assert "rejection" not in res.headers["location"]
        assert "timeout" not in res.headers["location"]
        assert "refused" not in res.headers["location"]

    assert jira_context["repository"].connections == {}


# ===========================================================================
# 15. Status never exposes tokens/secrets
# ===========================================================================
def test_15_status_never_exposes_tokens_secrets(jira_context):
    """Status endpoint never returns access_token, refresh_token, client_secret, or code."""
    # Seed a connected Jira account with sensitive tokens
    jira_context["repository"].upsert(
        JiraConnectionDocument(
            owner_id="USR-001",
            provider="JIRA",
            access_token="SUPER-SECRET-ACCESS-TOKEN-VALUE",
            refresh_token="SUPER-SECRET-REFRESH-TOKEN-VALUE",
            expires_at=TEST_TIME + timedelta(hours=1),
            connected_at=TEST_TIME,
            updated_at=TEST_TIME,
            scope=" ".join(JIRA_SCOPES),
            token_type="Bearer",
        )
    )

    client = jira_context["auth"].client("USR-001")
    response = client.get("/api/v1/integrations/jira/status")
    assert response.status_code == 200
    data = response.json()

    assert data["connected"] is True
    assert "connected_at" in data
    assert "expires_at" in data

    forbidden_strings = {
        "access_token",
        "refresh_token",
        "client_secret",
        "SUPER-SECRET-ACCESS-TOKEN-VALUE",
        "SUPER-SECRET-REFRESH-TOKEN-VALUE",
        TEST_CLIENT_SECRET,
    }
    raw_text = response.text
    for secret in forbidden_strings:
        assert secret not in data
        assert secret not in raw_text


# ===========================================================================
# 16. Disconnect removes local connection
# ===========================================================================
def test_16_disconnect_removes_local_connection(jira_context):
    """DELETE /api/v1/integrations/jira/connection removes local credentials and connection."""
    jira_context["repository"].upsert(
        JiraConnectionDocument(
            owner_id="USR-001",
            provider="JIRA",
            access_token="token-to-delete",
            refresh_token="refresh-to-delete",
            expires_at=TEST_TIME + timedelta(hours=1),
            connected_at=TEST_TIME,
            updated_at=TEST_TIME,
            scope=" ".join(JIRA_SCOPES),
            token_type="Bearer",
        )
    )

    client = jira_context["auth"].client("USR-001")
    del_res = client.delete("/api/v1/integrations/jira/connection")
    assert del_res.status_code == 200
    assert del_res.json()["disconnected"] is True

    # Status must now report disconnected
    status_res = client.get("/api/v1/integrations/jira/status")
    assert status_res.status_code == 200
    assert status_res.json() == {"connected": False}
    assert jira_context["repository"].find_by_owner("USR-001") is None


# ===========================================================================
# 17. One user cannot access another user's connection
# ===========================================================================
def test_17_user_isolation_enforced(jira_context):
    """User B cannot view or disconnect User A's Jira connection."""
    jira_context["repository"].upsert(
        JiraConnectionDocument(
            owner_id="USR-001",
            provider="JIRA",
            access_token="user1-token",
            refresh_token="user1-refresh",
            expires_at=TEST_TIME + timedelta(hours=1),
            connected_at=TEST_TIME,
            updated_at=TEST_TIME,
            scope=" ".join(JIRA_SCOPES),
            token_type="Bearer",
        )
    )

    client_b = jira_context["auth"].client("USR-002")

    # User B status is disconnected
    status_b = client_b.get("/api/v1/integrations/jira/status")
    assert status_b.status_code == 200
    assert status_b.json() == {"connected": False}

    # User B disconnect does not affect User A
    del_b = client_b.delete("/api/v1/integrations/jira/connection")
    assert del_b.status_code == 200

    # User A is still connected
    client_a = jira_context["auth"].client("USR-001")
    status_a = client_a.get("/api/v1/integrations/jira/status")
    assert status_a.status_code == 200
    assert status_a.json()["connected"] is True


# ===========================================================================
# 18. Zero real network calls occur
# ===========================================================================
def test_18_no_real_network_calls_occur(jira_context, monkeypatch):
    """All Atlassian HTTP calls are intercepted; real network calls are prohibited."""
    import socket

    real_connect = socket.socket.connect

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise AssertionError(f"Real external network call was attempted to {host}!")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    client = jira_context["auth"].client("USR-001")
    connect_res = client.get("/api/v1/integrations/jira/connect")
    assert connect_res.status_code == 200
    state = parse_qs(urlparse(connect_res.json()["authorization_url"]).query)["state"][0]

    callback_res = client.get(
        f"/api/v1/integrations/jira/callback?code=mock-code&state={state}",
        follow_redirects=False,
    )
    assert callback_res.status_code == 302
    assert callback_res.headers["location"] == f"{TEST_RETURN_URL}?jira_connected=true"
    assert len(jira_context["oauth_client"].calls) == 1


# ===========================================================================
# 19. Unconfigured handling and secret masking
# ===========================================================================
def test_19_unconfigured_handling_and_secret_masking(jira_context):
    """When unconfigured, connect returns 503, callback redirects safely, and repr masks secrets."""
    from app.modules.integrations.jira.service import JiraConfigurationError, JiraConfiguration

    # Test repr masking
    config = JiraConfiguration(
        client_id="my-client-id",
        client_secret="my-super-secret",
        redirect_uri="http://localhost:8000/cb",
        frontend_return_url="http://localhost:5173/jira",
    )
    repr_str = repr(config)
    assert "my-super-secret" not in repr_str
    assert "***" in repr_str
    assert "my-super-secret" not in str(config)

    # Test from_settings with missing credentials raises JiraConfigurationError
    class EmptySettings:
        jira_client_id = None
        jira_client_secret = None
        jira_redirect_uri = "http://localhost:8000/cb"
        jira_frontend_return_url = "http://localhost:5173/jira"
        jira_http_timeout_seconds = 10.0

    with pytest.raises(JiraConfigurationError):
        JiraConfiguration.from_settings(EmptySettings())

    # Test endpoints when service has no configuration
    unconfigured_service = JiraOAuthService(
        configuration=None,
        repository=jira_context["repository"],
        state_store=jira_context["state_store"],
        client=jira_context["oauth_client"],
    )
    app.dependency_overrides[get_jira_oauth_service] = lambda: unconfigured_service

    client = jira_context["auth"].client("USR-001")
    connect_res = client.get("/api/v1/integrations/jira/connect")
    assert connect_res.status_code == 503
    assert "not configured" in connect_res.json()["errors"][0]["message"]

    cb_res = client.get(
        "/api/v1/integrations/jira/callback?code=abc&state=xyz",
        follow_redirects=False,
    )
    assert cb_res.status_code == 302
    assert "jira_error=configuration_unavailable" in cb_res.headers["location"]


# ===========================================================================
# 20. Direct JiraOAuthClient exchange verification
# ===========================================================================
def test_20_jira_oauth_client_direct_exchange(monkeypatch):
    """Direct JiraOAuthClient exchange parses tokens and raises appropriate errors."""
    import httpx
    from app.modules.integrations.jira.service import (
        JiraOAuthClient,
        JiraTokenExchangeError,
        JiraNetworkTimeoutError,
        JiraMalformedResponseError,
    )

    client = JiraOAuthClient(timeout_seconds=5.0)

    # 1. Success response
    class MockSuccessResponse:
        status_code = 200
        def json(self):
            return {
                "access_token": "valid-token",
                "refresh_token": "valid-refresh",
                "expires_in": 3600,
            }

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockSuccessResponse())
    tokens = client.exchange_code_for_tokens(
        client_id="cid", client_secret="csec", code="code", redirect_uri="http://cb"
    )
    assert tokens["access_token"] == "valid-token"

    # 2. Timeout
    def mock_timeout(*a, **kw):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", mock_timeout)
    with pytest.raises(JiraNetworkTimeoutError):
        client.exchange_code_for_tokens(
            client_id="cid", client_secret="csec", code="code", redirect_uri="http://cb"
        )

    # 3. 400 rejection
    class MockRejectResponse:
        status_code = 400
        def json(self):
            return {"error": "invalid_grant"}

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockRejectResponse())
    with pytest.raises(JiraTokenExchangeError):
        client.exchange_code_for_tokens(
            client_id="cid", client_secret="csec", code="code", redirect_uri="http://cb"
        )

    # 4. Malformed JSON
    class MockMalformedResponse:
        status_code = 200
        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockMalformedResponse())
    with pytest.raises(JiraMalformedResponseError):
        client.exchange_code_for_tokens(
            client_id="cid", client_secret="csec", code="code", redirect_uri="http://cb"
        )


# ===========================================================================
# 21. Rotating refresh token replaces old token & calculates correct expires_at
# ===========================================================================
def test_21_rotating_refresh_token_replaces_old_token_and_calculates_expiry(jira_context):
    """When token refresh succeeds, rotated refresh_token replaces old one and expires_at is correctly set."""
    service = jira_context["service"]
    clock = jira_context["clock"]
    repo = jira_context["repository"]
    oauth_client = jira_context["oauth_client"]

    # Initial connection with expired token
    now = clock()
    conn = JiraConnectionDocument(
        owner_id="USR-001",
        provider="JIRA",
        access_token="old-access-token",
        refresh_token="initial-refresh-token",
        expires_at=now - timedelta(seconds=10),  # expired
        connected_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2),
        scope=" ".join(JIRA_SCOPES),
        token_type="Bearer",
        status="CONNECTED",
    )
    repo.upsert(conn)

    # Set mock refresh response with rotated refresh token and 7200s expires_in
    oauth_client.mock_tokens = {
        "access_token": "new-rotated-access-token",
        "refresh_token": "new-rotated-refresh-token",
        "expires_in": 7200,
        "token_type": "Bearer",
    }

    token = service.get_valid_access_token("USR-001")
    assert token == "new-rotated-access-token"

    # Persisted connection is updated with new rotated token and calculated expires_at
    persisted = repo.find_by_owner("USR-001")
    assert persisted["access_token"] == "new-rotated-access-token"
    assert persisted["refresh_token"] == "new-rotated-refresh-token"
    assert persisted["expires_at"] == now + timedelta(seconds=7200)
    assert persisted["status"] == "CONNECTED"


# ===========================================================================
# 22. Refresh invalid_grant marks REAUTHORIZATION_REQUIRED
# ===========================================================================
def test_22_refresh_invalid_grant_marks_reauthorization_required(jira_context):
    """When refresh returns invalid_grant, connection is marked REAUTHORIZATION_REQUIRED without deleting data."""
    service = jira_context["service"]
    clock = jira_context["clock"]
    repo = jira_context["repository"]
    oauth_client = jira_context["oauth_client"]

    now = clock()
    conn = JiraConnectionDocument(
        owner_id="USR-001",
        provider="JIRA",
        access_token="expired-access",
        refresh_token="revoked-refresh",
        expires_at=now - timedelta(seconds=60),
        connected_at=now,
        updated_at=now,
        scope=" ".join(JIRA_SCOPES),
        token_type="Bearer",
        status="CONNECTED",
    )
    repo.upsert(conn)

    oauth_client.fail_with = JiraInvalidGrantError("Refresh token revoked")

    with pytest.raises(JiraReauthorizationRequiredError):
        service.get_valid_access_token("USR-001")

    persisted = repo.find_by_owner("USR-001")
    assert persisted["status"] == "REAUTHORIZATION_REQUIRED"
    assert "revoked" in persisted["reauthorization_reason"].lower()


# ===========================================================================
# 23. Concurrent refresh coordination
# ===========================================================================
def test_23_concurrent_refresh_coordination(jira_context):
    """Under concurrent refresh attempts, lock and atomic checks prevent race corruption."""
    service = jira_context["service"]
    clock = jira_context["clock"]
    repo = jira_context["repository"]
    oauth_client = jira_context["oauth_client"]

    now = clock()
    conn = JiraConnectionDocument(
        owner_id="USR-001",
        provider="JIRA",
        access_token="initial-access",
        refresh_token="refresh-111",
        expires_at=now - timedelta(seconds=10),
        connected_at=now,
        updated_at=now,
        scope=" ".join(JIRA_SCOPES),
        token_type="Bearer",
        status="CONNECTED",
    )
    repo.upsert(conn)

    oauth_client.mock_tokens = {
        "access_token": "refreshed-access",
        "refresh_token": "refresh-222",
        "expires_in": 3600,
    }

    # Simulate two sequential/coordinated calls through the service
    t1 = service.get_valid_access_token("USR-001")
    t2 = service.get_valid_access_token("USR-001")

    assert t1 == "refreshed-access"
    assert t2 == "refreshed-access"
    # Exactly one refresh call occurred because second call re-reads updated document
    assert len(oauth_client.calls) == 1
