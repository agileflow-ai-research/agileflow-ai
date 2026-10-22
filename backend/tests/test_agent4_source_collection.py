import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.main import app
from app.modules.agents.testing_validation.router import (
    get_agent4_source_storage,
    get_agent4_workflow_storage,
)
from app.modules.agents.testing_validation.sources.constants import (
    TEXT_MAX_CHARACTERS,
)
from app.modules.agents.testing_validation.sources.storage import Agent4SourceStorage
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


PDF = b"%PDF-1.7\nminimal"
PNG = b"\x89PNG\r\n\x1a\nminimal"
JPEG = b"\xff\xd8\xff\xe0minimal\xff\xd9"
WEBP = b"RIFF\x04\x00\x00\x00WEBPminimal"


def docx_bytes():
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


@pytest.fixture
def source_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    source_storage = Agent4SourceStorage(tmp_path)
    workflow_storage = Agent4WorkflowStorage(tmp_path)
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent4_source_storage] = lambda: source_storage
    app.dependency_overrides[get_agent4_workflow_storage] = lambda: workflow_storage
    try:
        yield authentication_context, projects, runs, tmp_path
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent4_source_storage, None)
        app.dependency_overrides.pop(get_agent4_workflow_storage, None)


def create_project(client, agent_type="TESTING_VALIDATION"):
    payload = {
        "agent_type": agent_type,
        "name": "Test source project",
        "domain": "Fintech",
    }
    if agent_type == "TESTING_VALIDATION":
        payload["agent_stage"] = "TEST_GENERATION"
    response = client.post("/api/v1/agent-projects", json=payload)
    assert response.status_code == 201
    return response.json()["data"]


def sources_endpoint(project_id):
    return (
        f"/api/v1/agents/testing-validation/{project_id}"
        "/test-generation/sources"
    )


def add_text(
    client,
    project_id,
    content="Customers can transfer funds.",
    artifact_type="FUNCTIONAL_REQUIREMENTS",
    origin="AGENT_1",
    **extra,
):
    return client.post(
        f"{sources_endpoint(project_id)}/text",
        json={
            "artifact_type": artifact_type,
            "normally_supplied_by": origin,
            "label": " Primary evidence ",
            "content": content,
            **extra,
        },
    )


def upload_file(
    client,
    project_id,
    filename,
    content,
    *,
    source_type="DOCUMENT",
    artifact_type=None,
    origin=None,
    content_type="application/octet-stream",
    **extra,
):
    if artifact_type is None:
        artifact_type = (
            "SYSTEM_ARCHITECTURE"
            if source_type == "IMAGE"
            else "API_SPECIFICATION"
        )
    if origin is None:
        origin = "AGENT_2"
    return client.post(
        f"{sources_endpoint(project_id)}/files",
        data={
            "artifact_type": artifact_type,
            "source_type": source_type,
            "normally_supplied_by": origin,
            "label": " Reference ",
            **extra,
        },
        files={"file": (filename, content, content_type)},
    )


def test_text_create_list_multiple_identity_and_provenance(source_context):
    authentication, _, runs, root = source_context
    client = authentication.client()
    project = create_project(client)
    project_id = project["agent_project_id"]

    first = add_text(client, project_id, "  First line\n  indented line  ")
    second = add_text(client, project_id, "First line\n  indented line")

    assert first.status_code == second.status_code == 201
    first_source = first.json()["data"]
    second_source = second.json()["data"]
    assert first_source["source_id"].startswith("A4SRC-")
    assert len(first_source["source_id"]) == len("A4SRC-") + 32
    assert first_source["source_id"] != second_source["source_id"]
    assert first_source["source_id"] not in "Primary evidence"
    assert first_source["agent_project_id"] == project_id
    assert first_source["source_type"] == "TEXT"
    assert first_source["collection_status"] == "READY"
    assert first_source["label"] == "Primary evidence"
    assert first_source["text_content"] == "First line\n  indented line"
    assert first_source["normally_supplied_by"] == "AGENT_1"
    assert first_source["supplied_via"] == "STANDALONE_MANUAL_INPUT"
    assert first_source["original_filename"] is None
    assert "owner_user_id" not in first_source
    assert "path" not in json.dumps(first_source).lower()

    listed = client.get(sources_endpoint(project_id))
    assert listed.status_code == 200
    assert [item["source_id"] for item in listed.json()["data"]] == [
        first_source["source_id"],
        second_source["source_id"],
    ]
    sidecars = list((root / project_id / "inputs").glob("*.source.json"))
    assert len(sidecars) == 2
    assert runs.documents == {}


def test_server_controls_identity_supplied_via_and_status(source_context):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = add_text(
        client,
        project_id,
        source_id="A4SRC-" + "a" * 32,
        supplied_via="GENERATED_BY_AGENT_1",
        collection_status="COMPLETED",
    )
    assert response.status_code == 422

    uploaded = upload_file(
        client,
        project_id,
        "flow.png",
        PNG,
        source_type="IMAGE",
        source_id="A4SRC-" + "a" * 32,
        supplied_via="GENERATED_BY_AGENT_2",
        collection_status="UNDERSTOOD",
    )
    assert uploaded.status_code == 201
    data = uploaded.json()["data"]
    assert data["source_id"] != "A4SRC-" + "a" * 32
    assert data["supplied_via"] == "STANDALONE_MANUAL_INPUT"
    assert data["collection_status"] == "PENDING_ANALYSIS"


@pytest.mark.parametrize("content", ["", "   \n\t"])
def test_blank_text_is_rejected(source_context, content):
    authentication, _, _, _ = source_context
    client = authentication.client()
    response = add_text(client, create_project(client)["agent_project_id"], content)
    assert response.status_code == 422


def test_text_size_and_aggregate_limits(source_context, monkeypatch):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    assert add_text(client, project_id, "a" * (TEXT_MAX_CHARACTERS + 1)).status_code == 422

    monkeypatch.setattr(
        "app.modules.agents.testing_validation.sources.storage.PROJECT_TEXT_MAX_CHARACTERS",
        10,
    )
    assert add_text(client, project_id, "123456").status_code == 201
    capacity = add_text(client, project_id, "12345")
    assert capacity.status_code == 409
    assert capacity.json()["errors"][0]["field"] == "sources"


@pytest.mark.parametrize(
    "filename,content,mime_type",
    [
        ("spec.pdf", PDF, "application/pdf"),
        (
            "spec.docx",
            docx_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("notes.txt", b"Plain UTF-8 requirements", "text/plain"),
        ("notes.md", b"# Requirements", "text/markdown"),
        ("data.json", b'{"requirement": true}', "application/json"),
        ("data.yaml", b"requirement: true", "application/yaml"),
        ("data.yml", b"requirement: true", "application/yaml"),
    ],
)
def test_document_formats_are_collected_without_extraction(
    source_context, filename, content, mime_type
):
    authentication, _, runs, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = upload_file(
        client, project_id, filename, content, content_type=mime_type
    )

    assert response.status_code == 201
    source = response.json()["data"]
    assert source["source_type"] == "DOCUMENT"
    assert source["collection_status"] == "UPLOADED"
    assert source["mime_type"] == mime_type
    assert source["size_bytes"] == len(content)
    assert source["sha256"] == hashlib.sha256(content).hexdigest()
    assert source["text_content"] is None
    files = {path.name for path in (root / project_id / "inputs").iterdir()}
    assert files == {
        f'{source["source_id"]}{source["extension"]}',
        f'{source["source_id"]}.source.json',
    }
    assert not any("extract" in name or "chunk" in name for name in files)
    assert runs.documents == {}


@pytest.mark.parametrize(
    "filename,content,mime_type",
    [
        ("flow.png", PNG, "image/png"),
        ("flow.jpg", JPEG, "image/jpeg"),
        ("flow.jpeg", JPEG, "image/jpeg"),
        ("flow.webp", WEBP, "image/webp"),
    ],
)
def test_image_formats_are_pending_analysis_only(
    source_context, filename, content, mime_type
):
    authentication, _, runs, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = upload_file(
        client,
        project_id,
        filename,
        content,
        source_type="IMAGE",
        content_type=mime_type,
    )
    assert response.status_code == 201
    source = response.json()["data"]
    assert source["collection_status"] == "PENDING_ANALYSIS"
    files = {path.name for path in (root / project_id / "inputs").iterdir()}
    assert not any("analysis" in name or "ocr" in name for name in files)
    assert runs.documents == {}


def test_policy_rejects_image_for_non_visual_artifact(source_context):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = upload_file(
        client,
        project_id,
        "requirements.png",
        PNG,
        source_type="IMAGE",
        artifact_type="FUNCTIONAL_REQUIREMENTS",
        origin="AGENT_1",
    )
    assert response.status_code == 422
    assert "cannot be supplied as IMAGE" in response.json()["errors"][0]["message"]


@pytest.mark.parametrize(
    "filename,content,source_type",
    [
        ("archive.zip", b"PK contents", "DOCUMENT"),
        ("fake.pdf", b"not a pdf", "DOCUMENT"),
        ("fake.png", JPEG, "IMAGE"),
        ("binary.txt", b"hello\x00binary", "DOCUMENT"),
        ("invalid.json", b"{not-json}", "DOCUMENT"),
    ],
)
def test_unsupported_or_mismatched_files_are_rejected_and_cleaned(
    source_context, filename, content, source_type
):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = upload_file(
        client, project_id, filename, content, source_type=source_type
    )
    assert response.status_code == 422
    inputs = root / project_id / "inputs"
    assert not inputs.exists() or list(inputs.iterdir()) == []


def test_mime_mismatch_and_oversize_are_rejected_without_partials(
    source_context, monkeypatch
):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    mismatch = upload_file(
        client,
        project_id,
        "spec.pdf",
        PDF,
        content_type="image/png",
    )
    assert mismatch.status_code == 422

    monkeypatch.setattr(
        "app.modules.agents.testing_validation.sources.storage.DOCUMENT_MAX_SIZE", 8
    )
    oversized = upload_file(client, project_id, "notes.txt", b"123456789")
    assert oversized.status_code == 422
    inputs = root / project_id / "inputs"
    assert not inputs.exists() or list(inputs.iterdir()) == []


@pytest.mark.parametrize("filename", ["../../evil.pdf", "..\\..\\evil.pdf"])
def test_filename_is_sanitized_and_storage_is_server_owned(source_context, filename):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = upload_file(client, project_id, filename, PDF)
    assert response.status_code == 201
    source = response.json()["data"]
    assert source["original_filename"] == "evil.pdf"
    assert not (root / "evil.pdf").exists()
    assert "path" not in json.dumps(source).lower()


def test_duplicate_hashes_remain_distinct_sources(source_context):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    first = upload_file(client, project_id, "one.pdf", PDF).json()["data"]
    second = upload_file(client, project_id, "two.pdf", PDF).json()["data"]
    assert first["sha256"] == second["sha256"]
    assert first["source_id"] != second["source_id"]
    assert len(client.get(sources_endpoint(project_id)).json()["data"]) == 2


def test_list_ignores_partials_and_future_sidecars(source_context):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source = add_text(client, project_id).json()["data"]
    inputs = root / project_id / "inputs"
    (inputs / f'{source["source_id"]}.chunks.json').write_text("{}")
    (inputs / f'{source["source_id"]}.source.json.part').write_text("partial")
    listed = client.get(sources_endpoint(project_id))
    assert listed.status_code == 200
    assert [item["source_id"] for item in listed.json()["data"]] == [
        source["source_id"]
    ]


def test_text_document_and_image_delete_remove_metadata_and_file(source_context):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    sources = [
        add_text(client, project_id).json()["data"],
        upload_file(client, project_id, "spec.pdf", PDF).json()["data"],
        upload_file(
            client, project_id, "flow.png", PNG, source_type="IMAGE"
        ).json()["data"],
    ]
    inputs = root / project_id / "inputs"
    for source in sources:
        response = client.delete(
            f'{sources_endpoint(project_id)}/{source["source_id"]}'
        )
        assert response.status_code == 200
        assert response.json()["data"] == {"source_id": source["source_id"]}
        assert not any(source["source_id"] in path.name for path in inputs.iterdir())
        assert client.delete(
            f'{sources_endpoint(project_id)}/{source["source_id"]}'
        ).status_code == 404


def test_cross_project_delete_and_foreign_owner_are_hidden(source_context):
    authentication, _, _, _ = source_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    first_project = create_project(owner)["agent_project_id"]
    second_project = create_project(owner)["agent_project_id"]
    source = add_text(owner, first_project).json()["data"]

    assert foreign.get(sources_endpoint(first_project)).status_code == 404
    assert add_text(foreign, first_project).status_code == 404
    assert foreign.delete(
        f'{sources_endpoint(first_project)}/{source["source_id"]}'
    ).status_code == 404
    assert owner.delete(
        f'{sources_endpoint(second_project)}/{source["source_id"]}'
    ).status_code == 404


@pytest.mark.parametrize("agent_type", ["REQUIREMENTS", "DESIGN_PLANNING", "IMPLEMENTATION"])
def test_wrong_agent_types_are_rejected(source_context, agent_type):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client, agent_type)["agent_project_id"]
    assert client.get(sources_endpoint(project_id)).status_code == 422
    assert add_text(client, project_id).status_code == 422


@pytest.mark.parametrize("stage", [None, "VALIDATION"])
def test_legacy_and_validation_stage_projects_are_rejected(source_context, stage):
    authentication, projects, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    projects.documents[project_id]["agent_stage"] = stage
    assert client.get(sources_endpoint(project_id)).status_code == 409
    assert add_text(client, project_id).status_code == 409


def test_archived_and_unknown_projects_fail_safely(source_context):
    authentication, projects, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    projects.documents[project_id]["status"] = "ARCHIVED"
    assert client.get(sources_endpoint(project_id)).status_code == 409
    assert client.get(sources_endpoint("AGP-999")).status_code == 404
    assert client.get(sources_endpoint("invalid")).status_code == 422


def test_source_mutations_do_not_change_workflow_or_create_runs(source_context):
    authentication, _, runs, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    workflow_url = (
        f"/api/v1/agents/testing-validation/{project_id}"
        "/test-generation/workflow"
    )
    workflow = client.get(workflow_url).json()["data"]
    workflow_path = root / project_id / "workflow.json"
    before = workflow_path.read_bytes()

    source = add_text(client, project_id).json()["data"]
    after_add = client.get(workflow_url).json()["data"]
    client.delete(f'{sources_endpoint(project_id)}/{source["source_id"]}')
    after_delete = client.get(workflow_url).json()["data"]

    assert workflow_path.read_bytes() == before
    assert after_add == after_delete == workflow
    assert workflow["pipeline_status"] == "WAITING_FOR_HUMAN"
    assert [node["status"] for node in workflow["nodes"]] == [
        "WAITING_FOR_HUMAN",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
    ]
    assert runs.documents == {}


def test_atomic_sidecar_failure_cleans_file_and_partial(source_context, monkeypatch):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    original_replace = Path.replace

    def fail_source_sidecar(path, target):
        if path.name.endswith(".source.json.part"):
            raise OSError("simulated atomic replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_source_sidecar)
    response = upload_file(client, project_id, "spec.pdf", PDF)
    assert response.status_code == 503
    inputs = root / project_id / "inputs"
    assert not inputs.exists() or list(inputs.iterdir()) == []


def test_openapi_exposes_only_n12_source_crud_routes():
    paths = app.openapi()["paths"]
    source_paths = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith("/api/v1/agents/testing-validation/")
        and "/test-generation/sources" in path
        for method in operations
    }
    assert source_paths == {
        (
            "GET",
            "/api/v1/agents/testing-validation/{agent_project_id}/test-generation/sources",
        ),
        (
            "POST",
            "/api/v1/agents/testing-validation/{agent_project_id}/test-generation/sources/text",
        ),
        (
            "POST",
            "/api/v1/agents/testing-validation/{agent_project_id}/test-generation/sources/files",
        ),
        (
            "DELETE",
            "/api/v1/agents/testing-validation/{agent_project_id}/test-generation/sources/{source_id}",
        ),
    }
    assert not any(
        suffix in path
        for _, path in source_paths
        for suffix in ("extract", "normalize", "chunk", "confirm", "continue")
    )
