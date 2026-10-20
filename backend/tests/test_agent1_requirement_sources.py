from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.main import app
from app.modules.agents.requirements.api.dependencies import (
    get_requirement_source_storage,
)
from app.modules.agents.requirements.infrastructure.storage import (
    RequirementSourceStorage,
)
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


PDF = b"%PDF-1.7\nminimal"
TXT = b"Stakeholders need secure appointment booking."
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00audio"
WAV = b"RIFF\x10\x00\x00\x00WAVEfmt audio"
M4A = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00audio"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00video"
MOV = b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00video"
WEBM = b"\x1aE\xdf\xa3webm-video"


def docx_bytes() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


@pytest.fixture
def source_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    storage = RequirementSourceStorage(tmp_path)
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_requirement_source_storage] = lambda: storage
    try:
        yield authentication_context, projects, runs, tmp_path
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_requirement_source_storage, None)


def create_project(client, agent_type="REQUIREMENTS"):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": agent_type, "name": "Discovery", "domain": "Health"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def upload(client, project_id, source_type, filename, content, mime="application/octet-stream"):
    return client.post(
        f"/api/v1/agents/requirements/{project_id}/sources",
        data={"source_type": source_type},
        files={"file": (filename, content, mime)},
    )


@pytest.mark.parametrize(
    "source_type,filename,content,expected_id,expected_mime",
    [
        ("DOCUMENT", "requirements.pdf", PDF, "DOC-001", "application/pdf"),
        ("DOCUMENT", "existing.docx", docx_bytes(), "DOC-001", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("DOCUMENT", "notes.txt", TXT, "DOC-001", "text/plain"),
        ("AUDIO", "interview.mp3", MP3, "AUD-001", "audio/mpeg"),
        ("AUDIO", "meeting.wav", WAV, "AUD-001", "audio/wav"),
        ("AUDIO", "voice.m4a", M4A, "AUD-001", "audio/mp4"),
        ("VIDEO", "workflow.mp4", MP4, "VID-001", "video/mp4"),
        ("VIDEO", "demo.mov", MOV, "VID-001", "video/quicktime"),
        ("VIDEO", "walkthrough.webm", WEBM, "VID-001", "video/webm"),
    ],
)
def test_requirements_project_accepts_each_supported_source(
    source_context, source_type, filename, content, expected_id, expected_mime
):
    authentication, _, runs, _ = source_context
    client = authentication.client()
    project = create_project(client)

    response = upload(client, project["agent_project_id"], source_type, filename, content)

    assert response.status_code == 201
    assert response.json()["data"] == {
        **response.json()["data"],
        "source_id": expected_id,
        "source_type": source_type,
        "original_filename": filename,
        "mime_type": expected_mime,
        "status": "READY",
    }
    assert "path" not in str(response.json()).lower()
    assert runs.documents == {}


def test_multiple_and_mixed_sources_have_independent_stable_ids(source_context):
    authentication, _, runs, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    fixtures = [
        ("DOCUMENT", "one.pdf", PDF),
        ("DOCUMENT", "two.txt", TXT),
        ("AUDIO", "one.mp3", MP3),
        ("AUDIO", "two.wav", WAV),
        ("VIDEO", "one.mp4", MP4),
        ("VIDEO", "two.webm", WEBM),
    ]
    ids = [
        upload(client, project_id, source_type, name, content).json()["data"]["source_id"]
        for source_type, name, content in fixtures
    ]

    assert ids == ["DOC-001", "DOC-002", "AUD-001", "AUD-002", "VID-001", "VID-002"]
    listed = client.get(f"/api/v1/agents/requirements/{project_id}/sources")
    assert listed.status_code == 200
    assert [item["source_id"] for item in listed.json()["data"]] == ids
    assert runs.documents == {}


def test_delete_removes_only_the_requested_source_and_ids_are_not_reused(source_context):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    first = upload(client, project_id, "DOCUMENT", "one.pdf", PDF).json()["data"]
    second = upload(client, project_id, "DOCUMENT", "two.txt", TXT).json()["data"]

    response = client.delete(
        f"/api/v1/agents/requirements/{project_id}/sources/{first['source_id']}"
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"source_id": "DOC-001"}
    assert [item["source_id"] for item in client.get(
        f"/api/v1/agents/requirements/{project_id}/sources"
    ).json()["data"]] == [second["source_id"]]
    replacement = upload(client, project_id, "DOCUMENT", "three.txt", TXT)
    assert replacement.json()["data"]["source_id"] == "DOC-003"


def test_deleted_last_source_id_is_not_reused(source_context):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    first = upload(client, project_id, "AUDIO", "one.mp3", MP3).json()["data"]
    client.delete(
        f"/api/v1/agents/requirements/{project_id}/sources/{first['source_id']}"
    )

    replacement = upload(client, project_id, "AUDIO", "two.mp3", MP3)

    assert replacement.json()["data"]["source_id"] == "AUD-002"


@pytest.mark.parametrize(
    "source_type,filename,content,mime",
    [
        ("DOCUMENT", "archive.zip", b"PK data", "application/zip"),
        ("DOCUMENT", "fake.pdf", b"not pdf", "application/pdf"),
        ("AUDIO", "fake.mp3", b"not audio", "audio/mpeg"),
        ("VIDEO", "fake.mp4", b"not video", "video/mp4"),
        ("AUDIO", "interview.mp3", MP3, "video/mp4"),
    ],
)
def test_unsupported_mismatched_and_spoofed_sources_are_rejected(
    source_context, source_type, filename, content, mime
):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    response = upload(client, project_id, source_type, filename, content, mime)
    assert response.status_code == 422
    upload_dir = root / project_id / "inputs"
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_empty_source_is_rejected(source_context):
    authentication, _, _, _ = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    assert upload(client, project_id, "DOCUMENT", "empty.txt", b"").status_code == 422


def test_owner_type_archive_authentication_and_list_isolation(source_context):
    authentication, _, _, _ = source_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project_id = create_project(owner)["agent_project_id"]
    source = upload(owner, project_id, "DOCUMENT", "requirements.pdf", PDF).json()["data"]

    assert foreign.get(f"/api/v1/agents/requirements/{project_id}/sources").status_code == 404
    assert upload(foreign, project_id, "AUDIO", "interview.mp3", MP3).status_code == 404
    assert foreign.delete(
        f"/api/v1/agents/requirements/{project_id}/sources/{source['source_id']}"
    ).status_code == 404

    wrong_id = create_project(owner, "IMPLEMENTATION")["agent_project_id"]
    assert owner.get(f"/api/v1/agents/requirements/{wrong_id}/sources").status_code == 422
    assert upload(owner, wrong_id, "VIDEO", "demo.mp4", MP4).status_code == 422

    owner.patch(f"/api/v1/agent-projects/{project_id}", json={"status": "ARCHIVED"})
    assert owner.get(f"/api/v1/agents/requirements/{project_id}/sources").status_code == 409
    assert upload(owner, project_id, "AUDIO", "next.mp3", MP3).status_code == 409
    assert owner.delete(
        f"/api/v1/agents/requirements/{project_id}/sources/{source['source_id']}"
    ).status_code == 409

    anonymous = authentication.anonymous_client()
    assert anonymous.get(f"/api/v1/agents/requirements/{project_id}/sources").status_code == 401


def test_source_metadata_persists_across_storage_instances(source_context):
    authentication, _, _, root = source_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    upload(client, project_id, "VIDEO", "workflow.mp4", MP4)

    replacement_storage = RequirementSourceStorage(root)
    app.dependency_overrides[get_requirement_source_storage] = lambda: replacement_storage
    response = client.get(f"/api/v1/agents/requirements/{project_id}/sources")

    assert response.status_code == 200
    assert response.json()["data"][0]["source_id"] == "VID-001"
    assert "path" not in str(response.json()).lower()
