"""Comprehensive test suite for Jira issue type retrieval, mapping, and sync preview.

Covers all required preview behavior:
1. Issue-type discovery for selected project
2. Safe normalization of issue types (id, name, subtask, hierarchy_level)
3. Auto-suggest obvious mappings (Epic->Epic, Story->Story, Task->Task)
4. Unsupported Feature handling (Feature missing requires human selection, never auto-invented)
5. Incomplete mapping blocked (422 JIRA_MAPPING_INCOMPLETE)
6. Invalid / unavailable Jira issue type rejected (422 JIRA_ISSUE_TYPE_UNAVAILABLE)
7. Hierarchy / reference validation (422 JIRA_HIERARCHY_INVALID)
8. Preview requires completed Jira target (connected, site, project, board)
9. Preview requires JIRA_PLAN (400 JIRA_PLAN_UNAVAILABLE)
10. Deterministic preview preserves AgileFlow IDs, summaries, parents, planned sprints
11. Preview assignee is strictly null / unassigned
12. Synchronization status is strictly NOT_PERFORMED
13. Zero Jira write requests (strictly read-only discovery)
"""

from datetime import datetime, timezone
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.integrations.jira.client import JiraApiClient
from app.modules.integrations.jira.router import (
    get_jira_api_client,
    get_jira_connection_repository,
    get_jira_oauth_client,
    get_jira_oauth_service,
    get_jira_state_store,
)
from app.modules.integrations.jira.schemas import (
    JiraConnectionDocument,
    JiraIssueTypeResponse,
    JiraSelectedBoard,
    JiraSelectedProject,
    JiraSelectedSite,
)
from app.modules.integrations.jira.service import (
    JiraBoardNotSelectedError,
    JiraConfiguration,
    JiraHierarchyInvalidError,
    JiraIssueTypeUnavailableError,
    JiraMappingIncompleteError,
    JiraNotConnectedError,
    JiraOAuthClient,
    JiraOAuthService,
    JiraPlanUnavailableError,
    JiraProjectNotSelectedError,
    JiraSiteNotSelectedError,
    JiraStateStore,
    suggest_issue_type_mappings,
)

TEST_TIME = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)
TEST_USER_ID = "USR-001"
TEST_USER = UserPublicResponse(
    user_id=TEST_USER_ID,
    name="Lead Developer",
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

    def update_selected_site(self, owner_id: str, site: JiraSelectedSite) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc:
            return None
        doc["selected_site"] = site.model_dump(mode="python")
        doc["selected_project"] = None
        doc["selected_board"] = None
        return doc.copy()

    def update_selected_project(self, owner_id: str, project: JiraSelectedProject) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc:
            return None
        doc["selected_project"] = project.model_dump(mode="python")
        doc["selected_board"] = None
        return doc.copy()

    def update_selected_board(self, owner_id: str, board: JiraSelectedBoard) -> dict[str, Any] | None:
        doc = self.connections.get(owner_id)
        if not doc:
            return None
        doc["selected_board"] = board.model_dump(mode="python")
        return doc.copy()

    def delete_by_owner(self, owner_id: str) -> bool:
        return self.connections.pop(owner_id, None) is not None


class TrackingFakeApiClient:
    """Mock Jira API client tracking all method invocations and ensuring ZERO writes."""

    def __init__(self, issue_types: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.issue_types = issue_types or [
            {"id": "10000", "name": "Epic", "subtask": False, "hierarchyLevel": 1},
            {"id": "10001", "name": "Story", "subtask": False, "hierarchyLevel": 0},
            {"id": "10002", "name": "Task", "subtask": False, "hierarchyLevel": 0},
            {"id": "10003", "name": "Sub-task", "subtask": True, "hierarchyLevel": -1},
            {"id": "10004", "name": "Bug", "subtask": False, "hierarchyLevel": 0},
        ]

    def request(self, user_id: str, method: str, url: str, **kwargs) -> Any:
        self.calls.append((method, url, kwargs))
        if method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
            raise AssertionError(f"UNINTENDED JIRA WRITE: {method} {url}")
        return {}

    def get_project_issue_types(self, user_id: str, cloud_id: str, project_id_or_key: str) -> list[dict[str, Any]]:
        self.calls.append(("GET", f"/issue/createmeta/{project_id_or_key}/issuetypes", None))
        return self.issue_types


@pytest.fixture
def test_env():
    repo = FakeConnectionRepo()
    config = JiraConfiguration(
        client_id="test-cid",
        client_secret="test-sec",
        redirect_uri="http://localhost:8000/callback",
        frontend_return_url="http://localhost:5173/return",
    )
    service = JiraOAuthService(
        configuration=config,
        repository=repo,
        state_store=JiraStateStore(),
        client=JiraOAuthClient(),
        clock=lambda: TEST_TIME,
    )
    api_client = TrackingFakeApiClient()

    # Pre-populate connection with site, project, board
    conn = JiraConnectionDocument(
        owner_id=TEST_USER_ID,
        access_token="valid-token",
        refresh_token="valid-refresh",
        expires_at=TEST_TIME,
        connected_at=TEST_TIME,
        updated_at=TEST_TIME,
        scope="read:jira-work",
        status="CONNECTED",
        selected_site=JiraSelectedSite(
            cloud_id="site-001",
            site_name="Alpha Site",
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
            board_id=50,
            board_name="BookEase Scrum Board",
            board_type="scrum",
            selected_at=TEST_TIME,
        ),
    )
    repo.upsert(conn)

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_jira_connection_repository] = lambda: repo
    app.dependency_overrides[get_jira_oauth_service] = lambda: service
    app.dependency_overrides[get_jira_api_client] = lambda: api_client

    client = TestClient(app)

    yield {
        "client": client,
        "repo": repo,
        "service": service,
        "api_client": api_client,
    }

    app.dependency_overrides.clear()


@pytest.fixture
def sample_outputs():
    return {
        "JIRA_PLAN": {
            "epics": [
                {
                    "id": "EPIC-001",
                    "title": "Booking Engine",
                    "outcome": "Users can reserve slots",
                    "priority": "HIGH",
                    "source_refs": ["REQ-001"],
                }
            ],
            "stories": [
                {
                    "id": "STORY-001",
                    "epic_id": "EPIC-001",
                    "feature_id": "FEATURE-001",
                    "actor": "Guest",
                    "goal": "Search available rooms",
                    "benefit": "find matching rooms",
                    "acceptance_criteria": ["Results display in < 1s"],
                    "priority": "HIGH",
                    "estimate_points": 5,
                    "source_refs": ["REQ-002"],
                }
            ],
            "tasks": [
                {
                    "id": "TASK-001",
                    "epic_id": "EPIC-001",
                    "feature_id": "FEATURE-001",
                    "story_id": "STORY-001",
                    "title": "Create room search query API",
                    "description": "SQL query for availability",
                    "required_skills": ["Backend", "SQL"],
                    "estimate_points": 3,
                    "depends_on": [],
                    "source_refs": ["REQ-002"],
                }
            ],
            "sprints": [
                {
                    "id": "SPRINT-001",
                    "name": "Sprint 1",
                    "duration_days": 14,
                    "capacity_points": 20,
                    "item_refs": ["STORY-001", "TASK-001"],
                    "planned_points": 8,
                    "dependency_notes": [],
                }
            ],
            "assignments": [],
            "priorities": [
                {"item_id": "EPIC-001", "priority": "HIGH"},
                {"item_id": "STORY-001", "priority": "HIGH"},
                {"item_id": "TASK-001", "priority": "MEDIUM"},
            ],
            "synchronization": "NOT_PERFORMED",
        },
        "FEATURES": [
            {
                "id": "FEATURE-001",
                "epic_id": "EPIC-001",
                "title": "Room Search & Filter",
                "description": "Filter by date and price",
                "source_refs": ["REQ-002"],
            }
        ],
    }


# ---------------------------------------------------------------------------
# 1. Issue Types Retrieval & Discovery Tests
# ---------------------------------------------------------------------------


def test_get_issue_types_success(test_env):
    """Retrieves and normalizes issue types for the selected project."""
    res = test_env["client"].get("/api/v1/integrations/jira/issue-types")
    assert res.status_code == 200
    types = res.json()
    assert len(types) == 5
    names = [t["name"] for t in types]
    assert "Epic" in names
    assert "Story" in names
    assert "Task" in names
    assert "Sub-task" in names

    epic_type = next(t for t in types if t["name"] == "Epic")
    assert epic_type["hierarchy_level"] == 1
    assert epic_type["subtask"] is False

    subtask_type = next(t for t in types if t["name"] == "Sub-task")
    assert subtask_type["hierarchy_level"] == -1
    assert subtask_type["subtask"] is True


def test_get_issue_types_requires_connection(test_env):
    test_env["repo"].delete_by_owner(TEST_USER_ID)
    res = test_env["client"].get("/api/v1/integrations/jira/issue-types")
    assert res.status_code == 400
    assert "JIRA_NOT_CONNECTED" in res.text


def test_get_issue_types_requires_site(test_env):
    doc = test_env["repo"].find_by_owner(TEST_USER_ID)
    doc["selected_site"] = None
    doc["selected_project"] = None
    test_env["repo"].connections[TEST_USER_ID] = doc

    res = test_env["client"].get("/api/v1/integrations/jira/issue-types")
    assert res.status_code == 400
    assert "JIRA_SITE_NOT_SELECTED" in res.text


def test_get_issue_types_requires_project(test_env):
    doc = test_env["repo"].find_by_owner(TEST_USER_ID)
    doc["selected_project"] = None
    test_env["repo"].connections[TEST_USER_ID] = doc

    res = test_env["client"].get("/api/v1/integrations/jira/issue-types")
    assert res.status_code == 400
    assert "JIRA_PROJECT_NOT_SELECTED" in res.text


# ---------------------------------------------------------------------------
# 2. Mapping Suggestions & Unsupported Feature Tests
# ---------------------------------------------------------------------------


def test_suggest_mappings_unambiguous():
    types = [
        JiraIssueTypeResponse(id="1", name="Epic", subtask=False, hierarchy_level=1),
        JiraIssueTypeResponse(id="2", name="Story", subtask=False, hierarchy_level=0),
        JiraIssueTypeResponse(id="3", name="Task", subtask=False, hierarchy_level=0),
        JiraIssueTypeResponse(id="4", name="Sub-task", subtask=True, hierarchy_level=-1),
    ]
    suggestions = suggest_issue_type_mappings(types)
    assert suggestions["EPIC"] == "Epic"
    assert suggestions["USER_STORY"] == "Story"
    assert suggestions["TASK"] == "Task"
    assert suggestions["FEATURE"] is None  # Feature not in Jira, must be human-selected


def test_suggest_mappings_with_exact_feature():
    types = [
        JiraIssueTypeResponse(id="1", name="Epic", subtask=False, hierarchy_level=1),
        JiraIssueTypeResponse(id="2", name="Feature", subtask=False, hierarchy_level=1),
        JiraIssueTypeResponse(id="3", name="Story", subtask=False, hierarchy_level=0),
        JiraIssueTypeResponse(id="4", name="Task", subtask=False, hierarchy_level=0),
    ]
    suggestions = suggest_issue_type_mappings(types)
    assert suggestions["FEATURE"] == "Feature"


def test_suggest_mappings_ambiguous_returns_none():
    types = [
        JiraIssueTypeResponse(id="1", name="Story", subtask=False, hierarchy_level=0),
        JiraIssueTypeResponse(id="2", name="User Story", subtask=False, hierarchy_level=0),
        JiraIssueTypeResponse(id="3", name="Task", subtask=False, hierarchy_level=0),
    ]
    suggestions = suggest_issue_type_mappings(types)
    assert suggestions["USER_STORY"] is None  # Ambiguous, cannot auto-pick


# ---------------------------------------------------------------------------
# 3. Preview Validation & Error Blocking Tests
# ---------------------------------------------------------------------------


def test_preview_requires_board(test_env, sample_outputs):
    doc = test_env["repo"].find_by_owner(TEST_USER_ID)
    doc["selected_board"] = None
    test_env["repo"].connections[TEST_USER_ID] = doc

    payload = {
        "agent_project_id": "AGP-001",
        "mappings": {"EPIC": "Epic", "FEATURE": "Story", "USER_STORY": "Story", "TASK": "Task"},
        "outputs": sample_outputs,
    }
    res = test_env["client"].post("/api/v1/integrations/jira/preview", json=payload)
    assert res.status_code == 400
    assert "JIRA_BOARD_NOT_SELECTED" in res.text


def test_preview_requires_jira_plan(test_env):
    payload = {
        "agent_project_id": "AGP-001",
        "mappings": {"EPIC": "Epic", "USER_STORY": "Story", "TASK": "Task"},
        "outputs": {"SYSTEM_ARCHITECTURE": {}},
    }
    res = test_env["client"].post("/api/v1/integrations/jira/preview", json=payload)
    assert res.status_code == 400
    assert "JIRA_PLAN_UNAVAILABLE" in res.text


def test_preview_blocks_incomplete_mapping(test_env, sample_outputs):
    payload = {
        "agent_project_id": "AGP-001",
        "mappings": {"EPIC": "Epic", "USER_STORY": "Story"},  # Missing TASK and FEATURE
        "outputs": sample_outputs,
    }
    res = test_env["client"].post("/api/v1/integrations/jira/preview", json=payload)
    assert res.status_code == 422
    assert "JIRA_MAPPING_INCOMPLETE" in res.text


def test_preview_requires_feature_mapping_when_features_exist(test_env, sample_outputs):
    payload = {
        "agent_project_id": "AGP-001",
        "mappings": {
            "EPIC": "Epic",
            "USER_STORY": "Story",
            "TASK": "Task",
            # FEATURE omitted while FEATURES exist in output
        },
        "outputs": sample_outputs,
    }
    res = test_env["client"].post("/api/v1/integrations/jira/preview", json=payload)
    assert res.status_code == 422
    assert "FEATURE" in res.text


def test_preview_rejects_unavailable_jira_issue_type(test_env, sample_outputs):
    payload = {
        "agent_project_id": "AGP-001",
        "mappings": {
            "EPIC": "NonExistentJiraType",
            "FEATURE": "Story",
            "USER_STORY": "Story",
            "TASK": "Task",
        },
        "outputs": sample_outputs,
    }
    res = test_env["client"].post("/api/v1/integrations/jira/preview", json=payload)
    assert res.status_code == 422
    assert "JIRA_ISSUE_TYPE_UNAVAILABLE" in res.text


def test_preview_rejects_broken_hierarchy_reference(test_env, sample_outputs):
    bad_outputs = dict(sample_outputs)
    bad_outputs["JIRA_PLAN"]["stories"][0]["epic_id"] = "EPIC-999"  # Non-existent Epic
    payload = {
        "agent_project_id": "AGP-001",
        "mappings": {"EPIC": "Epic", "FEATURE": "Story", "USER_STORY": "Story", "TASK": "Task"},
        "outputs": bad_outputs,
    }
    res = test_env["client"].post("/api/v1/integrations/jira/preview", json=payload)
    assert res.status_code == 422
    assert "JIRA_HIERARCHY_INVALID" in res.text


# ---------------------------------------------------------------------------
# 4. Preview Generation & Determinism Tests
# ---------------------------------------------------------------------------


def test_preview_generation_success(test_env, sample_outputs):
    payload = {
        "agent_project_id": "AGP-001",
        "mappings": {
            "EPIC": "Epic",
            "FEATURE": "Story",
            "USER_STORY": "Story",
            "TASK": "Task",
        },
        "outputs": sample_outputs,
    }
    res = test_env["client"].post("/api/v1/integrations/jira/preview", json=payload)
    assert res.status_code == 200
    preview = res.json()

    # 1. Target verification
    assert preview["target"]["site"]["name"] == "Alpha Site"
    assert preview["target"]["project"]["key"] == "BOOK"
    assert preview["target"]["board"]["name"] == "BookEase Scrum Board"

    # 2. Status verification
    assert preview["synchronization_status"] == "NOT_PERFORMED"

    # 3. Preserved AgileFlow IDs
    issue_ids = [i["artifact_id"] for i in preview["issues"]]
    assert "EPIC-001" in issue_ids
    assert "FEATURE-001" in issue_ids
    assert "STORY-001" in issue_ids
    assert "TASK-001" in issue_ids

    # 4. Assignee strictly null / unassigned
    for issue in preview["issues"]:
        assert issue["assignee"] is None

    # 5. Sprint planning preserved
    story_issue = next(i for i in preview["issues"] if i["artifact_id"] == "STORY-001")
    assert story_issue["planned_sprint"] == "Sprint 1"
    assert story_issue["jira_issue_type"] == "Story"
    assert story_issue["parent_id"] == "FEATURE-001"

    task_issue = next(i for i in preview["issues"] if i["artifact_id"] == "TASK-001")
    assert task_issue["planned_sprint"] == "Sprint 1"
    assert task_issue["jira_issue_type"] == "Task"
    assert task_issue["parent_id"] == "STORY-001"

    # 6. Sprints
    assert len(preview["sprints"]) == 1
    assert preview["sprints"][0]["name"] == "Sprint 1"
    assert preview["sprints"][0]["planned_points"] == 8

    # 7. Summary metrics
    assert preview["summary"]["total_issues"] == 4
    assert preview["summary"]["total_sprints"] == 1
    assert preview["summary"]["epic_count"] == 1
    assert preview["summary"]["feature_count"] == 1
    assert preview["summary"]["story_count"] == 1
    assert preview["summary"]["task_count"] == 1

    # 8. Non-native Feature warning present
    assert any("Feature mapped to 'Story'" in w for w in preview["warnings"])

    # 9. Verify ZERO writes to Jira
    for method, url, _ in test_env["api_client"].calls:
        assert method.upper() not in ("POST", "PUT", "DELETE", "PATCH")
