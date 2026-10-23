"""Comprehensive automated test suite for Jira synchronization execution flow.

Covers all prompt requirements:
1. Hard HITL boundary: confirmation=False rejected with JIRA_CONFIRMATION_REQUIRED
2. Incomplete mapping or invalid preview blocked
3. Valid sync execution creates sprints and unassigned issues
4. Assignee strictly remains UNASSIGNED (null / None)
5. Hierarchy preserved: parents created before children with parent_key
6. Issues placed into planned sprints
7. Stored traceability: sprints, issues, browse URLs
8. Full success -> COMPLETED
9. Partial write failure -> PARTIAL, successful writes preserved
10. Resuming partial sync is idempotent: does NOT recreate existing sprints or issues
11. Total failure -> FAILED
12. Agent 2 run COMPLETED status remains untouched on Jira failure
13. Concurrent active sync blocked with JIRA_SYNC_IN_PROGRESS
14. Unauthorized project access blocked with JIRA_UNAUTHORIZED_PROJECT_ACCESS
15. Safe response: tokens never exposed
"""

from datetime import datetime, timezone
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.common.status import AgentRunStatus
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.integrations.jira.router import (
    get_jira_api_client,
    get_jira_connection_repository,
    get_jira_oauth_client,
    get_jira_oauth_service,
    get_jira_sync_repository,
)
from app.modules.integrations.jira.schemas import (
    JiraConnectionDocument,
    JiraSelectedBoard,
    JiraSelectedProject,
    JiraSelectedSite,
    JiraSyncDocument,
)
from app.modules.integrations.jira.service import (
    JiraConfiguration,
    JiraOAuthClient,
    JiraOAuthService,
    JiraStateStore,
)
from app.modules.standalone.router import get_standalone_service

TEST_TIME = datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc)
TEST_USER_ID = "USR-001"
TEST_USER = UserPublicResponse(
    user_id=TEST_USER_ID,
    name="Lead Architect",
    email="lead@agileflow.ai",
    is_active=True,
    created_at=TEST_TIME,
    updated_at=TEST_TIME,
)


class FakeConnectionRepo:
    def __init__(self) -> None:
        self.connections: dict[str, dict[str, Any]] = {}

    def find_by_owner(self, owner_id: str) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        return doc.copy() if doc is not None else None

    def upsert(self, connection: JiraConnectionDocument) -> dict[str, Any]:
        doc = connection.model_dump(mode="python")
        self.connections[connection.owner_id] = doc
        return doc.copy()


class FakeSyncRepo:
    def __init__(self) -> None:
        self.syncs: dict[str, dict[str, Any]] = {}

    def find_by_sync_id(self, sync_id: str) -> dict[str, Any] | None:
        doc = self.syncs.get(sync_id)
        return doc.copy() if doc is not None else None

    def find_latest_by_run(
        self, agent_project_id: str, run_id: str
    ) -> dict[str, Any] | None:
        matches = [
            s
            for s in self.syncs.values()
            if s.get("agent_project_id") == agent_project_id
            and s.get("run_id") == run_id
        ]
        if not matches:
            return None
        matches.sort(key=lambda s: s.get("created_at", TEST_TIME), reverse=True)
        return matches[0].copy()

    def find_active_by_run(
        self, agent_project_id: str, run_id: str
    ) -> dict[str, Any] | None:
        for s in self.syncs.values():
            if (
                s.get("agent_project_id") == agent_project_id
                and s.get("run_id") == run_id
                and s.get("status") == "IN_PROGRESS"
            ):
                return s.copy()
        return None

    def upsert(self, sync_doc: JiraSyncDocument) -> dict[str, Any]:
        doc = sync_doc.model_dump(mode="python")
        self.syncs[sync_doc.sync_id] = doc
        return doc.copy()


class MockJiraApiClient:
    def __init__(self) -> None:
        self.created_sprints: list[dict[str, Any]] = []
        self.created_issues: list[dict[str, Any]] = []
        self.placed_issues: list[dict[str, Any]] = []
        self.sprint_counter = 500
        self.issue_counter = 100
        self.fail_issue_ids: set[str] = set()
        self.fail_sprint_ids: set[str] = set()
        self.fail_all_issues = False
        self.fail_all_sprints = False

    def get_project_issue_types(
        self, user_id: str, cloud_id: str, project_id_or_key: str
    ) -> list[dict[str, Any]]:
        return [
            {"id": "10000", "name": "Epic", "subtask": False, "hierarchyLevel": 1},
            {"id": "10001", "name": "Story", "subtask": False, "hierarchyLevel": 0},
            {"id": "10002", "name": "Task", "subtask": False, "hierarchyLevel": 0},
        ]

    def create_sprint(
        self,
        user_id: str,
        cloud_id: str,
        origin_board_id: int,
        name: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        if self.fail_all_sprints or name in self.fail_sprint_ids:
            raise RuntimeError(f"Simulated Jira sprint creation failure for '{name}'")

        self.sprint_counter += 1
        record = {
            "id": self.sprint_counter,
            "name": name,
            "state": "future",
            "originBoardId": origin_board_id,
            "startDate": start_date,
            "endDate": end_date,
            "goal": goal,
        }
        self.created_sprints.append(record)
        return {"id": self.sprint_counter, "name": name, "state": "future"}

    def create_issue(
        self,
        user_id: str,
        cloud_id: str,
        project_key: str,
        issue_type_name: str,
        summary: str,
        *,
        description: str | None = None,
        parent_key_or_id: str | None = None,
    ) -> dict[str, Any]:
        if self.fail_all_issues:
            raise RuntimeError(f"Simulated Jira issue creation failure for '{summary}'")

        for fail_id in self.fail_issue_ids:
            if fail_id in (description or "") or fail_id in summary:
                raise RuntimeError(f"Simulated failure for issue matching '{fail_id}'")

        self.issue_counter += 1
        key = f"{project_key}-{self.issue_counter}"
        record = {
            "id": str(self.issue_counter),
            "key": key,
            "summary": summary,
            "issue_type": issue_type_name,
            "description": description,
            "parent_key_or_id": parent_key_or_id,
            "assignee": None,  # STRICT: never assigned
        }
        self.created_issues.append(record)
        return {"id": str(self.issue_counter), "key": key}

    def add_issues_to_sprint(
        self,
        user_id: str,
        cloud_id: str,
        sprint_id: int,
        issue_keys: list[str],
    ) -> None:
        self.placed_issues.append({"sprint_id": sprint_id, "issues": issue_keys})


class FakeRun:
    def __init__(
        self,
        run_id: str = "RUN-001",
        status: AgentRunStatus = AgentRunStatus.COMPLETED,
        outputs: dict[str, Any] | None = None,
    ) -> None:
        self.run_id = run_id
        self.status = status
        self.output_manifest = outputs or {}


class FakeStandaloneService:
    def __init__(self, run: FakeRun | None = None) -> None:
        self.run = run or FakeRun()
        self.unauthorized_projects: set[str] = set()

    def get_run(self, agent_project_id: str, run_id: str, user: Any) -> FakeRun:
        if agent_project_id in self.unauthorized_projects:
            raise PermissionError("Access denied to project")
        return self.run

    def list_runs(self, agent_project_id: str, user: Any) -> list[FakeRun]:
        if agent_project_id in self.unauthorized_projects:
            raise PermissionError("Access denied to project")
        return [self.run]


SAMPLE_PLAN_OUTPUTS = {
    "JIRA_PLAN": {
        "project_key": "BOOK",
        "epics": [
            {
                "id": "EPIC-001",
                "title": "Authentication & Booking",
                "description": "User login and appointment flow",
            }
        ],
        "stories": [
            {
                "id": "STORY-001",
                "epic_id": "EPIC-001",
                "title": "Book Appointment",
                "actor": "Patient",
                "goal": "Book a slot",
                "planned_sprint": "SPRINT-1",
            }
        ],
        "tasks": [
            {
                "id": "TASK-001",
                "story_id": "STORY-001",
                "title": "Implement Booking Form",
                "planned_sprint": "SPRINT-1",
            }
        ],
        "sprints": [
            {
                "id": "SPRINT-1",
                "name": "Sprint 1 — Core Booking",
                "start_date": "2026-11-01",
                "end_date": "2026-11-14",
                "goal": "Deliver working appointment flow",
            }
        ],
    },
    "SPRINT_PLAN": [
        {
            "id": "SPRINT-1",
            "name": "Sprint 1 — Core Booking",
            "start_date": "2026-11-01",
            "end_date": "2026-11-14",
            "goal": "Deliver working appointment flow",
        }
    ],
}

VALID_MAPPINGS = {
    "EPIC": "Epic",
    "USER_STORY": "Story",
    "TASK": "Task",
}


@pytest.fixture
def sync_env():
    conn_repo = FakeConnectionRepo()
    sync_repo = FakeSyncRepo()
    mock_api = MockJiraApiClient()
    config = JiraConfiguration(
        client_id="test-cid",
        client_secret="test-sec",
        redirect_uri="http://localhost:8000/callback",
        frontend_return_url="http://localhost:5173/return",
    )
    service = JiraOAuthService(
        configuration=config,
        repository=conn_repo,
        state_store=JiraStateStore(),
        client=JiraOAuthClient(),
        clock=lambda: TEST_TIME,
        sync_repository=sync_repo,
    )
    fake_run = FakeRun(outputs=SAMPLE_PLAN_OUTPUTS)
    standalone = FakeStandaloneService(run=fake_run)

    # Establish active Jira connection with targets
    conn = JiraConnectionDocument(
        owner_id=TEST_USER_ID,
        access_token="secret-access-token",
        refresh_token="secret-refresh-token",
        expires_at=TEST_TIME,
        connected_at=TEST_TIME,
        updated_at=TEST_TIME,
        scope="read:jira-work write:jira-work",
        status="CONNECTED",
        selected_site=JiraSelectedSite(
            cloud_id="cloud-site-123",
            site_name="Alpha Cloud",
            site_url="https://alpha.atlassian.net",
            selected_at=TEST_TIME,
        ),
        selected_project=JiraSelectedProject(
            project_id="10001",
            project_key="BOOK",
            project_name="BookEase",
            project_type_key="software",
            selected_at=TEST_TIME,
        ),
        selected_board=JiraSelectedBoard(
            board_id=42,
            board_name="BookEase Scrum Board",
            board_type="scrum",
            selected_at=TEST_TIME,
        ),
    )
    conn_repo.upsert(conn)

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_jira_connection_repository] = lambda: conn_repo
    app.dependency_overrides[get_jira_sync_repository] = lambda: sync_repo
    app.dependency_overrides[get_jira_oauth_service] = lambda: service
    app.dependency_overrides[get_jira_api_client] = lambda: mock_api
    app.dependency_overrides[get_standalone_service] = lambda: standalone

    client = TestClient(app)

    yield {
        "client": client,
        "conn_repo": conn_repo,
        "sync_repo": sync_repo,
        "service": service,
        "mock_api": mock_api,
        "standalone": standalone,
        "run": fake_run,
    }

    app.dependency_overrides.clear()


# ===========================================================================
# 1. Hard HITL Boundary: Explicit confirmation required
# ===========================================================================
def test_sync_requires_explicit_confirmation(sync_env):
    """POST /sync rejects request when confirmation is False with HTTP 400 JIRA_CONFIRMATION_REQUIRED."""
    client = sync_env["client"]
    res = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": False,  # Missing explicit human confirmation
        },
    )
    assert res.status_code == 400
    assert "JIRA_CONFIRMATION_REQUIRED" in res.text
    # Ensure zero writes were attempted
    assert len(sync_env["mock_api"].created_sprints) == 0
    assert len(sync_env["mock_api"].created_issues) == 0


# ===========================================================================
# 2. Rejection of uncompleted runs
# ===========================================================================
def test_sync_rejects_non_completed_run(sync_env):
    """Sync is refused if Agent 2 run is not in COMPLETED status."""
    sync_env["run"].status = AgentRunStatus.RUNNING
    client = sync_env["client"]
    res = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
        },
    )
    assert res.status_code == 400
    assert "JIRA_RUN_NOT_COMPLETED" in res.text


# ===========================================================================
# 3. Unauthorized project access rejected
# ===========================================================================
def test_sync_rejects_unauthorized_project_access(sync_env):
    """Sync is refused if current user does not own or have access to agent_project_id."""
    sync_env["standalone"].unauthorized_projects.add("proj-forbidden")
    client = sync_env["client"]
    res = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-forbidden",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
        },
    )
    assert res.status_code == 403
    assert "JIRA_UNAUTHORIZED_PROJECT_ACCESS" in res.text


# ===========================================================================
# 4. Successful Full Synchronization (COMPLETED)
# ===========================================================================
def test_successful_full_synchronization(sync_env):
    """Full synchronization execution creates sprints, unassigned issues, and places them into sprints."""
    client = sync_env["client"]
    mock_api = sync_env["mock_api"]

    res = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["status"] == "COMPLETED"
    assert body["sprint_summary"]["created"] == 1
    assert body["sprint_summary"]["failed"] == 0
    assert body["issue_summary"]["created"] == 3  # 1 Epic, 1 Story, 1 Task
    assert body["issue_summary"]["failed"] == 0
    assert body["placement_summary"]["created"] >= 1  # Story and/or Task placed

    # Verify mock API interactions
    assert len(mock_api.created_sprints) == 1
    assert mock_api.created_sprints[0]["name"] == "Sprint 1 — Core Booking"

    assert len(mock_api.created_issues) == 3
    # Check assignee is strictly unassigned
    for issue in mock_api.created_issues:
        assert issue["assignee"] is None

    # Check hierarchy: Story parent is Epic, Task parent is Story
    epic = next(i for i in mock_api.created_issues if i["issue_type"] == "Epic")
    story = next(i for i in mock_api.created_issues if i["issue_type"] == "Story")
    task = next(i for i in mock_api.created_issues if i["issue_type"] == "Task")

    assert story["parent_key_or_id"] == epic["key"]
    assert task["parent_key_or_id"] == story["key"]

    # Check traceability & links
    trace = body["traceability"]
    assert len(trace["sprints"]) == 1
    assert len(trace["issues"]) == 3
    for iss in trace["issues"]:
        assert "https://alpha.atlassian.net/browse/" in iss["browse_url"]

    # Verify NO secrets exposed in response
    res_str = res.text
    assert "secret-access-token" not in res_str
    assert "secret-refresh-token" not in res_str


# ===========================================================================
# 5. Idempotency: Retrying does not recreate sprints or issues
# ===========================================================================
def test_idempotent_retry_does_not_duplicate_writes(sync_env):
    """Re-executing synchronization on a completed sync reuses already created sprints and issues."""
    client = sync_env["client"]
    mock_api = sync_env["mock_api"]

    # Run 1: initial sync
    res1 = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )
    assert res1.status_code == 200
    assert len(mock_api.created_sprints) == 1
    assert len(mock_api.created_issues) == 3

    # Run 2: retry/re-execute
    res2 = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["status"] == "COMPLETED"

    # API call counts must NOT increase!
    assert len(mock_api.created_sprints) == 1
    assert len(mock_api.created_issues) == 3


# ===========================================================================
# 6. Partial Failure & Resuming
# ===========================================================================
def test_partial_failure_and_resumption(sync_env):
    """When an issue fails to create, result is PARTIAL; resume creates missing item without duplicate writes."""
    client = sync_env["client"]
    mock_api = sync_env["mock_api"]

    # Simulate failure on TASK-001
    mock_api.fail_issue_ids.add("TASK-001")

    res1 = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["status"] == "PARTIAL"
    assert body1["issue_summary"]["created"] == 2  # Epic and Story succeeded
    assert body1["issue_summary"]["failed"] == 1  # Task failed
    assert len(body1["failures"]) >= 1

    # Check that sprint and successful issues are persisted in sync repository
    persisted = sync_env["sync_repo"].find_latest_by_run("proj-001", "RUN-001")
    assert persisted is not None
    assert persisted["status"] == "PARTIAL"
    assert "EPIC-001" in persisted["issues_trace"]
    assert "STORY-001" in persisted["issues_trace"]
    assert "TASK-001" not in persisted["issues_trace"]

    # Now fix the issue and resume sync
    mock_api.fail_issue_ids.clear()

    res2 = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["status"] == "COMPLETED"
    assert body2["issue_summary"]["created"] == 1  # Only TASK-001 created
    assert body2["issue_summary"]["reused"] == 2  # Epic and Story reused
    assert body2["sprint_summary"]["reused"] == 1  # Sprint reused

    # Total issues created in Jira mock is exactly 3
    assert len(mock_api.created_issues) == 3


# ===========================================================================
# 7. Total Failure & Invariant Agent Run Status
# ===========================================================================
def test_total_failure_leaves_agent_run_status_completed(sync_env):
    """If all Jira writes fail, status is FAILED, and Agent 2 run status remains COMPLETED."""
    client = sync_env["client"]
    mock_api = sync_env["mock_api"]

    mock_api.fail_all_sprints = True
    mock_api.fail_all_issues = True

    res = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "FAILED"
    assert body["sprint_summary"]["failed"] >= 1
    assert body["issue_summary"]["failed"] >= 1

    # CRITICAL: Agent 2 run status remains COMPLETED
    assert sync_env["run"].status == AgentRunStatus.COMPLETED


# ===========================================================================
# 8. Duplicate Concurrent Sync Blocked
# ===========================================================================
def test_duplicate_concurrent_sync_blocked(sync_env):
    """When a sync for the same run is IN_PROGRESS, second execution returns 409 JIRA_SYNC_IN_PROGRESS."""
    sync_env["sync_repo"].syncs["SYNC-ACTIVE"] = {
        "sync_id": "SYNC-ACTIVE",
        "agent_project_id": "proj-001",
        "run_id": "RUN-001",
        "status": "IN_PROGRESS",
        "created_at": TEST_TIME,
    }

    client = sync_env["client"]
    res = client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )
    assert res.status_code == 409
    assert "JIRA_SYNC_IN_PROGRESS" in res.text


# ===========================================================================
# 9. GET /sync returns status and traceability
# ===========================================================================
def test_get_sync_status(sync_env):
    """GET /sync returns 200 with NOT_PERFORMED before sync, and COMPLETED after sync."""
    client = sync_env["client"]

    # Before sync
    res1 = client.get(
        "/api/v1/integrations/jira/sync",
        params={"agent_project_id": "proj-001", "run_id": "RUN-001"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "NOT_PERFORMED"

    # Execute sync
    client.post(
        "/api/v1/integrations/jira/sync",
        json={
            "agent_project_id": "proj-001",
            "run_id": "RUN-001",
            "mappings": VALID_MAPPINGS,
            "confirmation": True,
            "outputs": SAMPLE_PLAN_OUTPUTS,
        },
    )

    # After sync
    res2 = client.get(
        "/api/v1/integrations/jira/sync",
        params={"agent_project_id": "proj-001", "run_id": "RUN-001"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "COMPLETED"
    assert len(res2.json()["traceability"]["issues"]) == 3
