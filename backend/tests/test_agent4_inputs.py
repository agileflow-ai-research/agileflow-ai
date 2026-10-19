import re

import pytest

from app.main import app
from app.modules.agents.testing_validation.inputs.constants import DOCUMENT_MAX_SIZE
from app.modules.agents.testing_validation.inputs.router import get_agent4_input_storage
from app.modules.agents.testing_validation.inputs.storage import TestGenerationInputStorage
from app.modules.standalone.router import get_agent_project_repository, get_agent_run_repository
from test_standalone_foundation import FakeAgentProjectRepository, FakeAgentRunRepository


AGENT_1_TYPES = [
    "FUNCTIONAL_REQUIREMENTS", "NON_FUNCTIONAL_REQUIREMENTS", "USER_STORIES", "ACCEPTANCE_CRITERIA",
    "PERSONAS", "QUALITY_FINDINGS", "CLARIFICATION_QUESTIONS", "SRS",
]
AGENT_2_TYPES = [
    "SYSTEM_ARCHITECTURE", "UML_DIAGRAMS", "DATABASE_SCHEMA", "API_SPECIFICATION",
    "WIREFRAMES", "UI_FLOW", "FEATURES",
]
PDF = b"%PDF-1.7\nminimal"
PNG = b"\x89PNG\r\n\x1a\nminimal"
SOURCE_ID = re.compile(r"^(LOCAL|A4UP)-[0-9a-f]{32}$")
PUBLIC_KEYS = {
    "source_id", "agent_project_id", "run_mode", "artifact_type", "source_type",
    "normally_supplied_by", "supplied_via", "label", "processing_status", "text_content",
    "original_filename", "mime_type", "size_bytes", "sha256", "created_at",
}


@pytest.fixture
def input_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent4_input_storage] = lambda: TestGenerationInputStorage(tmp_path)
    try:
        yield authentication_context, runs, tmp_path
    finally:
        for dependency in (get_agent_project_repository, get_agent_run_repository, get_agent4_input_storage):
            app.dependency_overrides.pop(dependency, None)


def create_project(client, agent_type="TESTING_VALIDATION", name="Quality Gate"):
    response = client.post("/api/v1/agent-projects", json={
        "agent_type": agent_type, "name": name, "domain": "Fintech",
    })
    assert response.status_code == 201
    return response.json()["data"]["agent_project_id"]


def base(project_id):
    return f"/api/v1/agents/testing-validation/{project_id}/test-generation/sources"


def add_text(client, project_id, artifact_type="ACCEPTANCE_CRITERIA", content="Refund within 14 days", **extra):
    return client.post(f"{base(project_id)}/text", json={"artifact_type": artifact_type, "content": content, **extra})


def add_file(client, project_id, filename, payload, artifact_type="ACCEPTANCE_CRITERIA", source_type="DOCUMENT", **extra):
    return client.post(
        f"{base(project_id)}/files",
        data={"artifact_type": artifact_type, "source_type": source_type, **extra},
        files={"file": (filename, payload, "application/octet-stream")},
    )


def test_create_and_list_text_source_preserves_formatting_and_identity(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    content = "Step 1:\n    Enter the booking code\n\nStep 2: confirm"

    created = add_text(client, project_id, content=f"  {content}  ", label=" Booking AC ")
    assert created.status_code == 201
    source = created.json()["data"]
    assert source["text_content"] == content
    assert source["label"] == "Booking AC"
    assert SOURCE_ID.fullmatch(source["source_id"]) and source["source_id"].startswith("LOCAL-")
    assert source["processing_status"] == "COLLECTED"

    listed = client.get(base(project_id)).json()["data"]
    assert [item["source_id"] for item in listed] == [source["source_id"]]


def test_multiple_same_type_sources_remain_distinct(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    first = add_text(client, project_id, label="checkout").json()["data"]
    second = add_text(client, project_id, label="refund").json()["data"]
    upload = add_file(client, project_id, "booking-ac.pdf", PDF).json()["data"]

    listed = client.get(base(project_id)).json()["data"]
    assert len({item["source_id"] for item in listed}) == 3
    assert {first["source_id"], second["source_id"], upload["source_id"]} == {item["source_id"] for item in listed}
    assert {item["artifact_type"] for item in listed} == {"ACCEPTANCE_CRITERIA"}


def test_blank_text_is_rejected(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    assert add_text(client, project_id, content="   \n\t ").status_code == 422
    assert client.get(base(project_id)).json()["data"] == []


def test_wrong_project_type_is_rejected_for_reads_and_writes(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client, agent_type="REQUIREMENTS")
    assert client.get(base(project_id)).status_code == 422
    assert add_text(client, project_id).status_code == 422


def test_foreign_user_cannot_read_write_or_delete(input_context):
    auth, _, _ = input_context
    owner = auth.client("USR-001")
    foreign = auth.client("USR-002")
    project_id = create_project(owner)
    source = add_text(owner, project_id).json()["data"]
    assert foreign.get(base(project_id)).status_code == 404
    assert add_text(foreign, project_id).status_code == 404
    assert foreign.delete(f"{base(project_id)}/{source['source_id']}").status_code == 404
    assert len(owner.get(base(project_id)).json()["data"]) == 1


def test_archived_project_keeps_reads_but_rejects_changes(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    add_text(client, project_id)
    client.patch(f"/api/v1/agent-projects/{project_id}", json={"status": "ARCHIVED"})
    assert len(client.get(base(project_id)).json()["data"]) == 1
    assert add_text(client, project_id).status_code == 409


@pytest.mark.parametrize("artifact_type", AGENT_1_TYPES + AGENT_2_TYPES)
def test_canonical_agent_1_and_agent_2_artifact_types_are_accepted(input_context, artifact_type):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    origin = {"origin_agent": "AGENT_2"} if artifact_type == "USER_STORIES" else {}
    response = add_text(client, project_id, artifact_type=artifact_type, **origin)
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("artifact_type", ["PRODUCT_BACKLOG", "EPICS", "TASKS", "SPRINT_PLAN", "UI_WIREFRAMES", "IMPLEMENTATION_TASKS", "requirements"])
def test_unsupported_or_other_agents_artifact_names_are_rejected(input_context, artifact_type):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    assert add_text(client, project_id, artifact_type=artifact_type).status_code == 422


def test_source_type_is_validated_and_image_is_limited_to_visual_artifacts(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    assert add_file(client, project_id, "ac.png", PNG, artifact_type="ACCEPTANCE_CRITERIA", source_type="IMAGE").status_code == 422
    assert add_file(client, project_id, "ac.pdf", PDF, source_type="TEXT").status_code == 422
    assert add_file(client, project_id, "ac.pdf", PDF, source_type="AUDIO").status_code == 422
    assert add_file(client, project_id, "wire.png", PNG, artifact_type="WIREFRAMES", source_type="IMAGE").status_code == 201


def test_provenance_is_honest_and_user_stories_require_an_explicit_origin(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)

    agent_1 = add_text(client, project_id, artifact_type="ACCEPTANCE_CRITERIA").json()["data"]
    agent_2 = add_text(client, project_id, artifact_type="API_SPECIFICATION").json()["data"]
    assert agent_1["normally_supplied_by"] == "AGENT_1"
    assert agent_2["normally_supplied_by"] == "AGENT_2"
    assert agent_1["supplied_via"] == agent_2["supplied_via"] == "STANDALONE_MANUAL_INPUT"
    assert set(agent_1) == PUBLIC_KEYS
    assert not {"generated_by_agent_1", "traceability_link", "run_id"} & set(agent_1)

    assert add_text(client, project_id, artifact_type="USER_STORIES").status_code == 422
    stories = add_text(client, project_id, artifact_type="USER_STORIES", origin_agent="AGENT_2").json()["data"]
    assert stories["normally_supplied_by"] == "AGENT_2"
    assert add_text(client, project_id, artifact_type="ACCEPTANCE_CRITERIA", origin_agent="AGENT_2").status_code == 422


def test_image_is_stored_with_pending_analysis_and_no_understood_text(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    response = add_file(client, project_id, "checkout-wireframe.png", PNG, artifact_type="WIREFRAMES", source_type="IMAGE")
    assert response.status_code == 201
    source = response.json()["data"]
    assert source["source_type"] == "IMAGE"
    assert source["processing_status"] == "PENDING_ANALYSIS"
    assert source["text_content"] is None


def test_uploaded_filename_never_becomes_storage_identity_and_paths_are_not_returned(input_context):
    auth, _, storage_root = input_context
    client = auth.client()
    project_id = create_project(client)
    response = add_file(client, project_id, "../../secret/booking-ac.pdf", PDF)
    assert response.status_code == 201
    source = response.json()["data"]

    assert source["original_filename"] == "booking-ac.pdf"
    assert "booking-ac" not in source["source_id"]
    assert (next(storage_root.rglob(f"{source['source_id']}.pdf"))).is_file()
    assert str(storage_root) not in response.text
    assert "storage" not in response.text.lower()


def test_file_size_type_and_content_are_enforced(input_context):
    auth, _, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    assert add_file(client, project_id, "ac.pdf", PDF).status_code == 201
    assert add_file(client, project_id, "ac.exe", PDF).status_code == 422
    assert add_file(client, project_id, "ac.pdf", b"not a pdf at all").status_code == 422
    oversized = b"%PDF-" + b"0" * DOCUMENT_MAX_SIZE
    assert add_file(client, project_id, "huge.pdf", oversized).status_code == 422
    assert len(client.get(base(project_id)).json()["data"]) == 1


def test_delete_removes_record_and_file_and_cross_project_ids_are_rejected(input_context):
    auth, _, storage_root = input_context
    client = auth.client()
    project_a = create_project(client, name="Project A")
    project_b = create_project(client, name="Project B")
    upload = add_file(client, project_a, "ac.pdf", PDF).json()["data"]

    assert client.delete(f"{base(project_b)}/{upload['source_id']}").status_code == 404
    assert len(client.get(base(project_a)).json()["data"]) == 1

    assert client.delete(f"{base(project_a)}/{upload['source_id']}").status_code == 200
    assert client.get(base(project_a)).json()["data"] == []
    assert not list(storage_root.rglob(f"{upload['source_id']}*"))


def test_input_operations_never_create_agent_runs(input_context):
    auth, runs, _ = input_context
    client = auth.client()
    project_id = create_project(client)
    text = add_text(client, project_id).json()["data"]
    add_file(client, project_id, "ac.pdf", PDF)
    client.delete(f"{base(project_id)}/{text['source_id']}")
    assert runs.documents == {}
