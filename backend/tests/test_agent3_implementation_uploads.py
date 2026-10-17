import hashlib
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.main import app
from app.modules.agents.implementation.router import (
    get_implementation_upload_storage,
)
from app.modules.agents.implementation.storage import (
    DOCUMENT_MAX_SIZE,
    IMAGE_MAX_SIZE,
    ImplementationUploadStorage,
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
def upload_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    storage = ImplementationUploadStorage(tmp_path)
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_implementation_upload_storage] = lambda: storage
    try:
        yield authentication_context, projects, tmp_path
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_implementation_upload_storage, None)


def create_project(client, agent_type="IMPLEMENTATION"):
    response = client.post(
        "/api/v1/agent-projects",
        json={
            "agent_type": agent_type,
            "name": "Builder",
            "domain": "Hospitality",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def upload(client, project_id, filename, content, source_type="DOCUMENT"):
    return client.post(
        f"/api/v1/agents/implementation/{project_id}/input-files",
        data={
            "source_type": source_type,
            "artifact_type": (
                "UI_WIREFRAMES"
                if source_type == "IMAGE"
                else "API_SPECIFICATION"
            ),
            "label": "Reference",
        },
        files={"file": (filename, content, "application/octet-stream")},
    )


@pytest.mark.parametrize(
    "filename,content,source_type,mime_type",
    [
        ("spec.pdf", PDF, "DOCUMENT", "application/pdf"),
        (
            "spec.docx",
            docx_bytes(),
            "DOCUMENT",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("notes.txt", b"Plain UTF-8 requirements", "DOCUMENT", "text/plain"),
        ("notes.md", b"# Requirements", "DOCUMENT", "text/markdown"),
        ("flow.png", PNG, "IMAGE", "image/png"),
        ("flow.jpg", JPEG, "IMAGE", "image/jpeg"),
        ("flow.webp", WEBP, "IMAGE", "image/webp"),
    ],
)
def test_valid_uploads_return_real_safe_metadata(
    upload_context, filename, content, source_type, mime_type
):
    authentication, _, root = upload_context
    client = authentication.client()
    project = create_project(client)

    response = upload(
        client, project["agent_project_id"], filename, content, source_type
    )

    assert response.status_code == 201
    metadata = response.json()["data"]
    assert metadata["upload_id"].startswith("A3UP-")
    assert metadata["original_filename"] == filename
    assert metadata["mime_type"] == mime_type
    assert metadata["size_bytes"] == len(content)
    assert metadata["sha256"] == hashlib.sha256(content).hexdigest()
    assert "path" not in str(response.json()).lower()
    stored = list((root / project["agent_project_id"] / "inputs").iterdir())
    assert all(filename not in path.name for path in stored)
    assert any(path.name == f'{metadata["upload_id"]}{metadata["extension"]}' for path in stored)


@pytest.mark.parametrize(
    "filename,content,source_type",
    [
        ("archive.zip", b"PK contents", "DOCUMENT"),
        ("file.pdf.exe", PDF, "DOCUMENT"),
        ("fake.pdf", b"not a pdf", "DOCUMENT"),
        ("fake.png", JPEG, "IMAGE"),
        ("binary.txt", b"hello\x00binary", "DOCUMENT"),
        ("invalid.json", b"{not-json}", "DOCUMENT"),
    ],
)
def test_unsupported_or_mismatched_files_are_rejected_and_cleaned(
    upload_context, filename, content, source_type
):
    authentication, _, root = upload_context
    client = authentication.client()
    project = create_project(client)

    response = upload(
        client, project["agent_project_id"], filename, content, source_type
    )

    assert response.status_code == 422
    upload_dir = root / project["agent_project_id"] / "inputs"
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


@pytest.mark.parametrize(
    "filename,content,source_type",
    [
        ("large.txt", b"a" * (DOCUMENT_MAX_SIZE + 1), "DOCUMENT"),
        ("large.png", PNG + b"a" * IMAGE_MAX_SIZE, "IMAGE"),
    ],
    ids=["oversized-document", "oversized-image"],
)
def test_size_limits_are_server_enforced_without_partial_files(
    upload_context, filename, content, source_type
):
    authentication, _, root = upload_context
    client = authentication.client()
    project = create_project(client)
    response = upload(
        client, project["agent_project_id"], filename, content, source_type
    )
    assert response.status_code == 422
    upload_dir = root / project["agent_project_id"] / "inputs"
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


@pytest.mark.parametrize("filename", ["../../evil.pdf", "..\\..\\evil.pdf"])
def test_traversal_names_are_display_only_and_cannot_escape(
    upload_context, filename
):
    authentication, _, root = upload_context
    client = authentication.client()
    project = create_project(client)
    response = upload(client, project["agent_project_id"], filename, PDF)
    assert response.status_code == 201
    assert response.json()["data"]["original_filename"] == "evil.pdf"
    assert not (root / "evil.pdf").exists()


def test_valid_upload_and_sidecar_are_deleted_together(upload_context):
    authentication, _, root = upload_context
    client = authentication.client()
    project = create_project(client)
    metadata = upload(
        client, project["agent_project_id"], "spec.pdf", PDF
    ).json()["data"]
    upload_dir = root / project["agent_project_id"] / "inputs"
    assert len(list(upload_dir.iterdir())) == 2

    response = client.delete(
        f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}'
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"upload_id": metadata["upload_id"]}
    assert list(upload_dir.iterdir()) == []
    missing = client.delete(
        f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}'
    )
    assert missing.status_code == 404


def test_owner_archive_and_agent_type_guards(upload_context):
    authentication, _, _ = upload_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project = create_project(owner)

    assert upload(foreign, project["agent_project_id"], "spec.pdf", PDF).status_code == 404
    metadata = upload(owner, project["agent_project_id"], "spec.pdf", PDF).json()["data"]
    assert foreign.delete(
        f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}'
    ).status_code == 404

    owner.patch(
        f'/api/v1/agent-projects/{project["agent_project_id"]}',
        json={"status": "ARCHIVED"},
    )
    assert upload(owner, project["agent_project_id"], "next.pdf", PDF).status_code == 409

    wrong = create_project(owner, "DESIGN_PLANNING")
    assert upload(owner, wrong["agent_project_id"], "spec.pdf", PDF).status_code == 422


def test_text_cannot_use_upload_endpoint(upload_context):
    authentication, _, _ = upload_context
    client = authentication.client()
    project = create_project(client)
    response = upload(
        client, project["agent_project_id"], "notes.txt", b"text", "TEXT"
    )
    assert response.status_code == 422


def test_upload_routes_require_authentication(upload_context):
    authentication, _, _ = upload_context
    client = authentication.anonymous_client()
    assert upload(client, "AGP-001", "spec.pdf", PDF).status_code == 401
    assert client.delete(
        "/api/v1/agents/implementation/AGP-001/input-files/"
        "A3UP-0123456789abcdef0123456789abcdef"
    ).status_code == 401


def test_openapi_exposes_upload_and_delete_input_file_routes():
    paths = app.openapi()["paths"]
    agent3 = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith("/api/v1/agents/implementation")
        and "/input-files" in path
        and not path.endswith("/extract")
        and not path.endswith("/extraction")
        for method in operations
    }
    assert agent3 == {
        ("POST", "/api/v1/agents/implementation/{agent_project_id}/input-files"),
        (
            "DELETE",
            "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}",
        ),
    }
    assert "/api/v1/agents/implementation/{agent_project_id}/run" not in paths
