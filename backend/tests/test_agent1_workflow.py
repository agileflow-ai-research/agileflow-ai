from datetime import datetime, timezone

import pytest

from app.main import app
from app.modules.agents.requirements.api.dependencies import (
    get_requirement_source_storage,
    get_requirement_workflow_storage,
)
from app.modules.agents.requirements.contracts.schemas import (
    RequirementSourceMetadata,
    RequirementSourceType,
)
from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.workflow.schemas import RequirementOutputCode
from app.modules.agents.requirements.workflow.service import (
    selection_digest,
    source_set_digest,
)
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import FakeAgentProjectRepository, FakeAgentRunRepository


TXT = b"Stakeholders need secure appointment booking."


@pytest.fixture
def workflow_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    source_storage = RequirementSourceStorage(tmp_path)
    workflow_storage = RequirementWorkflowStorage(tmp_path)
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_requirement_source_storage] = lambda: source_storage
    app.dependency_overrides[get_requirement_workflow_storage] = lambda: workflow_storage
    try:
        yield authentication_context, projects, runs, tmp_path
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_requirement_source_storage, None)
        app.dependency_overrides.pop(get_requirement_workflow_storage, None)


def create_project(client, agent_type="REQUIREMENTS"):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": agent_type, "name": "Discovery", "domain": "Health"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def upload_source(client, project_id, name="requirements.txt", content=TXT):
    response = client.post(
        f"/api/v1/agents/requirements/{project_id}/sources",
        data={"source_type": "DOCUMENT"},
        files={"file": (name, content, "text/plain")},
    )
    assert response.status_code == 201
    return response.json()["data"]


def workflow_url(project_id):
    return f"/api/v1/agents/requirements/{project_id}/workflow"


def update_outputs(client, project_id, outputs):
    return client.put(
        f"{workflow_url(project_id)}/outputs",
        json={"selected_outputs": outputs},
    )


def test_output_contract_rejects_empty_unknown_and_duplicate_values(workflow_context):
    authentication, _, _, _ = workflow_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]

    assert update_outputs(client, project_id, []).status_code == 422
    assert update_outputs(client, project_id, ["QUALITY_FINDINGS"]).status_code == 422
    assert update_outputs(
        client,
        project_id,
        ["SRS", "SRS"],
    ).status_code == 422


def test_selection_digest_is_deterministic_and_contract_versioned():
    left = selection_digest(
        [RequirementOutputCode.SRS, RequirementOutputCode.FUNCTIONAL_REQUIREMENTS]
    )
    right = selection_digest(
        [RequirementOutputCode.FUNCTIONAL_REQUIREMENTS, RequirementOutputCode.SRS]
    )
    changed = selection_digest([RequirementOutputCode.SRS])

    assert left == right
    assert left != changed
    assert len(left) == 64


def test_source_set_digest_is_order_independent_and_checksum_sensitive():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    first = RequirementSourceMetadata(
        source_id="DOC-001",
        source_type=RequirementSourceType.DOCUMENT,
        original_filename="one.txt",
        mime_type="text/plain",
        extension=".txt",
        size_bytes=3,
        sha256="a" * 64,
        created_at=now,
    )
    second = first.model_copy(
        update={"source_id": "AUD-001", "source_type": RequirementSourceType.AUDIO}
    )

    assert source_set_digest([first, second]) == source_set_digest([second, first])
    assert source_set_digest([first]) != source_set_digest(
        [first.model_copy(update={"sha256": "b" * 64})]
    )


def test_selection_persists_sorted_and_revision_changes_only_for_real_change(workflow_context):
    authentication, _, _, tmp_path = workflow_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]

    first = update_outputs(
        client, project_id, ["SRS", "FUNCTIONAL_REQUIREMENTS"]
    )
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["selected_outputs"] == ["FUNCTIONAL_REQUIREMENTS", "SRS"]
    assert first_data["selection_revision"] == 1

    same = update_outputs(
        client, project_id, ["FUNCTIONAL_REQUIREMENTS", "SRS"]
    ).json()["data"]
    assert same["selection_revision"] == 1
    assert same["selection_digest"] == first_data["selection_digest"]

    app.dependency_overrides[get_requirement_workflow_storage] = lambda: RequirementWorkflowStorage(tmp_path)
    reloaded = client.get(workflow_url(project_id))
    assert reloaded.status_code == 200
    assert reloaded.json()["data"]["selected_outputs"] == ["FUNCTIONAL_REQUIREMENTS", "SRS"]


def test_continue_requires_sources_and_outputs(workflow_context):
    authentication, _, _, _ = workflow_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    continue_url = f"{workflow_url(project_id)}/n1/continue"

    update_outputs(client, project_id, ["SRS"])
    without_source = client.post(continue_url)
    assert without_source.status_code == 409
    upload_source(client, project_id)
    update_outputs(client, project_id, ["SRS"])
    # A fresh project verifies the complementary missing-output gate.
    other_id = create_project(client)["agent_project_id"]
    upload_source(client, other_id)
    without_output = client.post(f"{workflow_url(other_id)}/n1/continue")
    assert without_output.status_code == 409


def test_continue_is_idempotent_and_input_changes_make_confirmation_stale(workflow_context):
    authentication, _, runs, _ = workflow_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    upload_source(client, project_id)
    waiting = update_outputs(client, project_id, ["SRS"]).json()["data"]
    assert waiting["n1_state"] == "WAITING_FOR_HUMAN"

    first = client.post(f"{workflow_url(project_id)}/n1/continue")
    second = client.post(f"{workflow_url(project_id)}/n1/continue")
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["n1_state"] == "COMPLETE"
    assert first.json()["data"]["confirmed_at"] == second.json()["data"]["confirmed_at"]
    assert runs.documents == {}

    upload_source(client, project_id, "more.txt", b"More evidence")
    source_changed = client.get(workflow_url(project_id)).json()["data"]
    assert source_changed["n1_state"] == "WAITING_FOR_HUMAN"
    assert source_changed["n1_confirmation_current"] is False

    client.post(f"{workflow_url(project_id)}/n1/continue")
    selection_changed = update_outputs(
        client, project_id, ["FUNCTIONAL_REQUIREMENTS"]
    ).json()["data"]
    assert selection_changed["n1_state"] == "WAITING_FOR_HUMAN"
    assert selection_changed["n1_confirmation_current"] is False


def test_workflow_enforces_owner_active_project_and_agent_type(workflow_context):
    authentication, _, _, _ = workflow_context
    owner = authentication.client()
    foreign = authentication.client("USR-002")
    project = create_project(owner)
    project_id = project["agent_project_id"]

    assert foreign.get(workflow_url(project_id)).status_code == 404

    wrong_id = create_project(owner, "IMPLEMENTATION")["agent_project_id"]
    assert owner.get(workflow_url(wrong_id)).status_code == 422

    archived = owner.patch(
        f"/api/v1/agent-projects/{project_id}", json={"status": "ARCHIVED"}
    )
    assert archived.status_code == 200
    assert owner.get(workflow_url(project_id)).status_code == 409
