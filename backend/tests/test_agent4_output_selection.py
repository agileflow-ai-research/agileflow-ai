import json

import pytest

from app.main import app
from app.modules.agents.testing_validation.router import (
    get_agent4_source_storage,
    get_agent4_workflow_storage,
)
from app.modules.agents.testing_validation.schemas import (
    TestGenerationOutputCode as OutputCode,
)
from app.modules.agents.testing_validation.sources.storage import Agent4SourceStorage
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
    AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
)
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


OUTPUTS = [output.value for output in OutputCode]


@pytest.fixture
def output_selection_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent4_workflow_storage] = (
        lambda: Agent4WorkflowStorage(tmp_path)
    )
    app.dependency_overrides[get_agent4_source_storage] = (
        lambda: Agent4SourceStorage(tmp_path)
    )
    try:
        yield authentication_context, projects, runs, tmp_path
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent4_workflow_storage, None)
        app.dependency_overrides.pop(get_agent4_source_storage, None)


def create_project(client, agent_type="TESTING_VALIDATION"):
    payload = {
        "agent_type": agent_type,
        "name": "Output selection project",
        "domain": "Fintech",
    }
    if agent_type == "TESTING_VALIDATION":
        payload["agent_stage"] = "TEST_GENERATION"
    response = client.post("/api/v1/agent-projects", json=payload)
    assert response.status_code == 201
    return response.json()["data"]


def workflow_url(project_id):
    return (
        f"/api/v1/agents/testing-validation/{project_id}"
        "/test-generation/workflow"
    )


def outputs_url(project_id):
    return f"{workflow_url(project_id)}/outputs"


def update_outputs(client, project_id, outputs, **extra):
    return client.put(
        outputs_url(project_id),
        json={"selected_outputs": outputs, **extra},
    )


def assert_waiting_workflow(workflow):
    assert workflow["pipeline_status"] == "WAITING_FOR_HUMAN"
    assert workflow["current_node_id"] == "INPUT_OUTPUT_SETUP"
    assert [node["status"] for node in workflow["nodes"]] == [
        "WAITING_FOR_HUMAN",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
    ]


def test_initial_selection_is_empty_without_automatic_defaults(
    output_selection_context,
):
    authentication, _, runs, _ = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = client.get(workflow_url(project_id))

    assert response.status_code == 200
    workflow = response.json()["data"]
    assert workflow["selected_outputs"] == []
    assert workflow["selection_revision"] == 0
    assert workflow["selection_updated_at"] is None
    assert_waiting_workflow(workflow)
    assert runs.documents == {}


def test_all_nine_outputs_are_accepted_and_returned_in_product_order(
    output_selection_context,
):
    authentication, _, _, _ = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = update_outputs(client, project_id, list(reversed(OUTPUTS)))

    assert response.status_code == 200
    workflow = response.json()["data"]
    assert workflow["selected_outputs"] == OUTPUTS
    assert workflow["selection_revision"] == 1
    assert workflow["selection_updated_at"] is not None
    assert_waiting_workflow(workflow)
    assert "path" not in json.dumps(workflow).lower()


@pytest.mark.parametrize("output", ["UNKNOWN", "TEST_EXECUTION_REPORT"])
def test_unknown_and_validation_outputs_are_rejected(
    output_selection_context, output
):
    authentication, _, _, _ = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = update_outputs(client, project_id, [output])
    assert response.status_code == 422


def test_duplicate_outputs_are_rejected_strictly(output_selection_context):
    authentication, _, _, _ = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = update_outputs(
        client, project_id, ["API_TEST_CASES", "API_TEST_CASES"]
    )
    assert response.status_code == 422
    assert "duplicates" in response.text


def test_one_and_multiple_outputs_persist_across_service_recreation(
    output_selection_context,
):
    authentication, _, _, _ = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]

    one = update_outputs(client, project_id, ["SECURITY_TEST_CASES"])
    assert one.json()["data"]["selected_outputs"] == ["SECURITY_TEST_CASES"]
    multiple = update_outputs(
        client,
        project_id,
        ["TEST_TRACEABILITY", "UNIT_TEST_CASES", "API_TEST_CASES"],
    )
    assert multiple.json()["data"]["selected_outputs"] == [
        "UNIT_TEST_CASES",
        "API_TEST_CASES",
        "TEST_TRACEABILITY",
    ]
    assert multiple.json()["data"]["selection_revision"] == 2

    reloaded = client.get(workflow_url(project_id))
    assert reloaded.json()["data"] == multiple.json()["data"]


def test_reordered_same_set_is_idempotent_and_meaningful_changes_increment(
    output_selection_context,
):
    authentication, _, _, root = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    first = update_outputs(
        client, project_id, ["API_TEST_CASES", "UNIT_TEST_CASES"]
    ).json()["data"]
    workflow_path = root / project_id / "workflow.json"
    first_bytes = workflow_path.read_bytes()

    same = update_outputs(
        client, project_id, ["UNIT_TEST_CASES", "API_TEST_CASES"]
    ).json()["data"]
    assert same == first
    assert same["selection_revision"] == 1
    assert workflow_path.read_bytes() == first_bytes

    changed = update_outputs(client, project_id, ["API_TEST_CASES"]).json()[
        "data"
    ]
    assert changed["selection_revision"] == 2
    assert changed["selection_updated_at"] >= first["selection_updated_at"]


def test_empty_draft_can_clear_selection(output_selection_context):
    authentication, _, _, _ = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    update_outputs(client, project_id, ["REGRESSION_TEST_CASES"])
    cleared = update_outputs(client, project_id, [])
    assert cleared.status_code == 200
    assert cleared.json()["data"]["selected_outputs"] == []
    assert cleared.json()["data"]["selection_revision"] == 2
    assert_waiting_workflow(cleared.json()["data"])


@pytest.mark.parametrize(
    "extra",
    [
        {"selection_revision": 99},
        {"selection_updated_at": "2026-10-21T00:00:00Z"},
        {"confirmation": True},
    ],
)
def test_client_cannot_control_server_selection_state(
    output_selection_context, extra
):
    authentication, _, _, _ = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    assert update_outputs(
        client, project_id, ["UNIT_TEST_CASES"], **extra
    ).status_code == 422


def test_f03_record_without_selection_fields_remains_readable(
    output_selection_context,
):
    authentication, _, _, root = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    assert client.get(workflow_url(project_id)).status_code == 200
    path = root / project_id / "workflow.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("selected_outputs")
    payload.pop("selection_revision")
    payload.pop("selection_updated_at")
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    before = path.read_bytes()

    response = client.get(workflow_url(project_id))

    assert response.status_code == 200
    workflow = response.json()["data"]
    assert workflow["selected_outputs"] == []
    assert workflow["selection_revision"] == 0
    assert workflow["selection_updated_at"] is None
    assert workflow["schema_version"] == AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION
    assert workflow["workflow_version"] == AGENT4_TEST_GENERATION_WORKFLOW_VERSION
    assert path.read_bytes() == before


def test_selection_update_does_not_rewrite_sources_or_advance_workflow(
    output_selection_context,
):
    authentication, _, runs, root = output_selection_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_response = client.post(
        f"/api/v1/agents/testing-validation/{project_id}/test-generation/sources/text",
        json={
            "artifact_type": "FUNCTIONAL_REQUIREMENTS",
            "normally_supplied_by": "AGENT_1",
            "content": "Customers can transfer funds.",
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["data"]["source_id"]
    sidecar_path = root / project_id / "inputs" / f"{source_id}.source.json"
    before_source = sidecar_path.read_bytes()
    before = client.get(workflow_url(project_id)).json()["data"]
    before_nodes = before["nodes"]

    response = update_outputs(
        client, project_id, ["E2E_TEST_CASES", "TEST_TRACEABILITY"]
    )

    assert response.status_code == 200
    workflow = response.json()["data"]
    assert sidecar_path.read_bytes() == before_source
    assert workflow["nodes"] == before_nodes
    assert_waiting_workflow(workflow)
    assert workflow["n1_confirmation"] is None
    assert "digest" not in json.dumps(workflow).lower()
    assert runs.documents == {}


def test_foreign_missing_malformed_wrong_agent_and_stage_are_rejected(
    output_selection_context,
):
    authentication, projects, runs, root = output_selection_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project_id = create_project(owner)["agent_project_id"]

    assert update_outputs(
        foreign, project_id, ["UNIT_TEST_CASES"]
    ).status_code == 404
    assert update_outputs(
        owner, "AGP-999", ["UNIT_TEST_CASES"]
    ).status_code == 404
    assert update_outputs(
        owner, "invalid", ["UNIT_TEST_CASES"]
    ).status_code == 422
    for agent_type in ("REQUIREMENTS", "DESIGN_PLANNING", "IMPLEMENTATION"):
        wrong_id = create_project(owner, agent_type)["agent_project_id"]
        assert update_outputs(
            owner, wrong_id, ["UNIT_TEST_CASES"]
        ).status_code == 422

    projects.documents[project_id]["agent_stage"] = None
    assert update_outputs(owner, project_id, ["UNIT_TEST_CASES"]).status_code == 409
    projects.documents[project_id]["agent_stage"] = "VALIDATION"
    assert update_outputs(owner, project_id, ["UNIT_TEST_CASES"]).status_code == 409
    projects.documents[project_id]["agent_stage"] = "TEST_GENERATION"
    projects.documents[project_id]["status"] = "ARCHIVED"
    assert update_outputs(owner, project_id, ["UNIT_TEST_CASES"]).status_code == 409
    assert runs.documents == {}
    assert not (root / project_id / "workflow.json").exists()


def test_openapi_exposes_update_and_n1_confirmation_without_processing_routes():
    paths = app.openapi()["paths"]
    path = (
        "/api/v1/agents/testing-validation/{agent_project_id}"
        "/test-generation/workflow/outputs"
    )
    assert set(paths[path]) == {"put"}
    agent4_paths = [
        item for item in paths if item.startswith("/api/v1/agents/testing-validation")
    ]
    confirmation_path = (
        "/api/v1/agents/testing-validation/{agent_project_id}"
        "/test-generation/workflow/n1/confirm"
    )
    assert set(paths[confirmation_path]) == {"post"}
    assert not any(
        token in item
        for item in agent4_paths
        for token in ("continue", "readiness")
    )
