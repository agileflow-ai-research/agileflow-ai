import json
from pathlib import Path

import pytest

from app.common.status import AgentStage
from app.main import app
from app.modules.agents.testing_validation.router import (
    get_agent4_workflow_storage,
)
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
    AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    AGENT4_TEST_GENERATION_NODE_ORDER,
)
from app.modules.agents.testing_validation.workflow.storage import (
    Agent4WorkflowStorage,
)
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


@pytest.fixture
def agent4_workflow_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    storage = Agent4WorkflowStorage(tmp_path)
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent4_workflow_storage] = lambda: storage
    try:
        yield authentication_context, projects, runs, tmp_path
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent4_workflow_storage, None)


def create_project(client, agent_type="TESTING_VALIDATION"):
    payload = {
        "agent_type": agent_type,
        "name": f"{agent_type} Project",
        "domain": "Fintech",
    }
    if agent_type == "TESTING_VALIDATION":
        payload["agent_stage"] = "TEST_GENERATION"
    response = client.post("/api/v1/agent-projects", json=payload)
    assert response.status_code == 201
    return response.json()["data"]


def workflow_endpoint(project_id):
    return (
        f"/api/v1/agents/testing-validation/{project_id}"
        "/test-generation/workflow"
    )


def test_initializes_and_projects_the_exact_six_node_workflow(agent4_workflow_context):
    authentication, _, runs, root = agent4_workflow_context
    client = authentication.client()
    project = create_project(client)

    response = client.get(workflow_endpoint(project["agent_project_id"]))

    assert response.status_code == 200
    workflow = response.json()["data"]
    assert workflow["schema_version"] == AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION
    assert workflow["workflow_version"] == AGENT4_TEST_GENERATION_WORKFLOW_VERSION
    assert workflow["agent_project_id"] == project["agent_project_id"]
    assert workflow["agent_stage"] == "TEST_GENERATION"
    assert workflow["pipeline_status"] == "WAITING_FOR_HUMAN"
    assert workflow["current_node_id"] == "INPUT_OUTPUT_SETUP"
    assert workflow["selected_outputs"] == []
    assert workflow["selection_revision"] == 0
    assert workflow["selection_updated_at"] is None
    assert workflow["n1_confirmation"] is None
    assert [node["node_id"] for node in workflow["nodes"]] == [
        node_id.value for node_id in AGENT4_TEST_GENERATION_NODE_ORDER
    ]
    assert [node["status"] for node in workflow["nodes"]] == [
        "WAITING_FOR_HUMAN", "LOCKED", "LOCKED", "LOCKED", "LOCKED", "LOCKED",
    ]
    assert len(workflow["nodes"]) == 6
    assert "owner_user_id" not in workflow
    assert "path" not in json.dumps(workflow).lower()
    assert runs.documents == {}

    workflow_path = root / project["agent_project_id"] / "workflow.json"
    persisted = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION
    assert persisted["workflow_version"] == AGENT4_TEST_GENERATION_WORKFLOW_VERSION
    assert set(persisted) == {
        "schema_version", "workflow_version", "agent_project_id", "owner_user_id",
        "agent_stage", "pipeline_status", "current_node_id", "nodes", "created_at",
        "updated_at", "selected_outputs", "selection_revision",
        "selection_updated_at", "n1_confirmation",
    }
    assert all(set(node) == {"node_id", "status", "updated_at"} for node in persisted["nodes"])
    assert not workflow_path.with_suffix(".json.part").exists()


def test_repeated_reads_are_idempotent_and_survive_service_recreation(agent4_workflow_context):
    authentication, _, runs, root = agent4_workflow_context
    client = authentication.client()
    project = create_project(client)
    endpoint = workflow_endpoint(project["agent_project_id"])

    first = client.get(endpoint)
    first_bytes = (root / project["agent_project_id"] / "workflow.json").read_bytes()
    second = client.get(endpoint)
    second_bytes = (root / project["agent_project_id"] / "workflow.json").read_bytes()

    assert first.status_code == second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    assert first_bytes == second_bytes
    assert runs.documents == {}


def test_foreign_owner_and_missing_project_are_hidden(agent4_workflow_context):
    authentication, _, _, root = agent4_workflow_context
    owner_client = authentication.client("USR-001")
    foreign_client = authentication.client("USR-002")
    project = create_project(owner_client)

    foreign = foreign_client.get(workflow_endpoint(project["agent_project_id"]))
    missing = owner_client.get(workflow_endpoint("AGP-999"))

    assert foreign.status_code == 404
    assert missing.status_code == 404
    assert not (root / project["agent_project_id"] / "workflow.json").exists()
    assert not (root / "AGP-999" / "workflow.json").exists()


def test_malformed_project_id_is_rejected_without_storage_access(
    agent4_workflow_context
):
    authentication, _, _, root = agent4_workflow_context
    response = authentication.client().get(workflow_endpoint("not-an-id"))

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "agent_project_id"
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("agent_type", ["REQUIREMENTS", "DESIGN_PLANNING", "IMPLEMENTATION"])
def test_rejects_other_agent_projects_without_creating_state(
    agent4_workflow_context, agent_type
):
    authentication, _, _, root = agent4_workflow_context
    client = authentication.client()
    project = create_project(client, agent_type)

    response = client.get(workflow_endpoint(project["agent_project_id"]))

    assert response.status_code == 422
    assert not (root / project["agent_project_id"] / "workflow.json").exists()


@pytest.mark.parametrize("stage", [None, AgentStage.VALIDATION])
def test_rejects_legacy_and_validation_projects_without_initializing(
    agent4_workflow_context, stage
):
    authentication, projects, runs, root = agent4_workflow_context
    client = authentication.client()
    project = create_project(client)
    projects.documents[project["agent_project_id"]]["agent_stage"] = stage

    response = client.get(workflow_endpoint(project["agent_project_id"]))

    assert response.status_code == 409
    assert response.json()["errors"][0]["field"] == "agent_stage"
    assert not (root / project["agent_project_id"] / "workflow.json").exists()
    assert runs.documents == {}


def test_archived_project_does_not_materialize_missing_workflow(agent4_workflow_context):
    authentication, projects, _, root = agent4_workflow_context
    client = authentication.client()
    project = create_project(client)
    projects.documents[project["agent_project_id"]]["status"] = "ARCHIVED"

    response = client.get(workflow_endpoint(project["agent_project_id"]))

    assert response.status_code == 409
    assert not (root / project["agent_project_id"] / "workflow.json").exists()


@pytest.mark.parametrize(
    ("field", "unsupported_value"),
    [("schema_version", "999"), ("workflow_version", "W999")],
)
def test_unknown_workflow_version_fails_safely(
    agent4_workflow_context, field, unsupported_value
):
    authentication, _, _, root = agent4_workflow_context
    client = authentication.client()
    project = create_project(client)
    endpoint = workflow_endpoint(project["agent_project_id"])
    assert client.get(endpoint).status_code == 200
    workflow_path = root / project["agent_project_id"] / "workflow.json"
    persisted = json.loads(workflow_path.read_text(encoding="utf-8"))
    persisted[field] = unsupported_value
    workflow_path.write_text(json.dumps(persisted), encoding="utf-8")

    response = client.get(endpoint)

    assert response.status_code == 503
    assert response.json()["errors"] == [{
        "field": "workflow",
        "message": "The Agent 4 workflow could not be loaded",
    }]


def test_atomic_save_failure_cleans_partial_state(
    agent4_workflow_context, monkeypatch
):
    authentication, _, runs, root = agent4_workflow_context
    client = authentication.client()
    project = create_project(client)
    original_replace = Path.replace

    def fail_workflow_replace(path, target):
        if path.name == "workflow.json.part":
            raise OSError("simulated atomic replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_workflow_replace)
    response = client.get(workflow_endpoint(project["agent_project_id"]))

    workflow_path = root / project["agent_project_id"] / "workflow.json"
    assert response.status_code == 503
    assert not workflow_path.exists()
    assert not workflow_path.with_suffix(".json.part").exists()
    assert runs.documents == {}
