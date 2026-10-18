from io import BytesIO

import fitz
import pytest
from docx import Document

from app.main import app
from app.modules.standalone.artifact_inputs import storage as artifact_storage
from app.modules.standalone.artifact_inputs.router import get_artifact_upload_storage
from app.modules.standalone.artifact_inputs.storage import ArtifactUploadStorage
from app.modules.standalone.router import get_agent_project_repository, get_agent_run_repository
from test_standalone_foundation import FakeAgentProjectRepository, FakeAgentRunRepository


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def artifact_context(authentication_context, tmp_path, monkeypatch):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    storage_root = tmp_path / "artifacts"
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_artifact_upload_storage] = lambda: ArtifactUploadStorage(storage_root)
    try:
        yield authentication_context, storage_root
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_artifact_upload_storage, None)


def create_project(client, agent_type="TESTING_VALIDATION") -> str:
    response = client.post("/api/v1/agent-projects", json={
        "agent_type": agent_type, "name": "Quality Gate", "domain": "Fintech",
    })
    assert response.status_code == 201
    return response.json()["data"]["agent_project_id"]


def uploads_url(project_id: str) -> str:
    return f"/api/v1/agent-projects/{project_id}/artifact-uploads"


def upload(client, project_id, *, filename, content, source_type="DOCUMENT", artifact_type="ACCEPTANCE_CRITERIA", label=None, mime="application/octet-stream"):
    data = {"source_type": source_type, "artifact_type": artifact_type}
    if label is not None:
        data["label"] = label
    return client.post(uploads_url(project_id), data=data, files={"file": (filename, content, mime)})


def test_owner_uploads_supported_document_as_pending_extraction(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="acceptance-criteria.pdf", content=pdf_bytes("AC-001"), label="  Checkout  ")
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["upload_id"].startswith("SAUP-")
    assert data["source_type"] == "DOCUMENT"
    assert data["artifact_type"] == "ACCEPTANCE_CRITERIA"
    assert data["label"] == "Checkout"
    assert data["original_filename"] == "acceptance-criteria.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["processing_status"] == "PENDING_EXTRACTION"
    assert any(storage_root.rglob("*.pdf"))


def test_owner_uploads_image_that_is_preserved_as_pending_analysis(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="registration-wireframe.png", content=PNG_BYTES,
                      source_type="IMAGE", artifact_type="UI_SPECIFICATION", mime="image/png")
    assert response.status_code == 201
    assert response.json()["data"]["processing_status"] == "PENDING_ANALYSIS"


def test_document_metadata_returned_is_safe_and_complete(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="srs.docx", content=docx_bytes("Spec"), artifact_type="SRS")
    data = response.json()["data"]
    assert set(data) == {
        "upload_id", "source_type", "artifact_type", "label", "original_filename", "mime_type",
        "size_bytes", "created_at", "processing_status",
    }
    assert str(storage_root) not in response.text
    assert "sha256" not in response.text
    assert "extension" not in data


def test_foreign_project_is_rejected(artifact_context):
    authentication, _ = artifact_context
    other_user_project = create_project(authentication.client("USR-002"))
    response = upload(authentication.client("USR-001"), other_user_project, filename="x.txt", content=b"text")
    assert response.status_code == 404


def test_wrong_agent_type_is_rejected(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    requirements_project = create_project(client, agent_type="REQUIREMENTS")
    response = upload(client, requirements_project, filename="x.txt", content=b"text")
    assert response.status_code == 422
    assert "not supported" in response.text


def test_unknown_artifact_type_is_rejected(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="x.txt", content=b"text", artifact_type="FUNCTIONAL_REQUIREMENTS")
    assert response.status_code == 422


def test_text_is_not_an_uploadable_source(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="x.txt", content=b"text", source_type="TEXT")
    assert response.status_code == 422


def test_unsupported_extension_is_rejected(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="payload.exe", content=b"MZ")
    assert response.status_code == 422
    assert ".exe" in response.text


def test_content_must_match_declared_type(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="fake.pdf", content=b"not a pdf at all")
    assert response.status_code == 422
    assert "does not match" in response.text


def test_oversized_upload_is_rejected(artifact_context, monkeypatch):
    authentication, _ = artifact_context
    monkeypatch.setattr(artifact_storage, "DOCUMENT_MAX_SIZE", 1024)
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="big.txt", content=b"a" * 2048)
    assert response.status_code == 422
    assert "must not exceed" in response.text


def test_unsafe_filename_never_escapes_the_project_storage(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = upload(client, project_id, filename="../../../etc/evil.txt", content=b"plain text")
    assert response.status_code == 201
    assert response.json()["data"]["original_filename"] == "evil.txt"
    root = storage_root.resolve()
    written = [path.resolve() for path in storage_root.rglob("*") if path.is_file()]
    assert written
    assert all(path.is_relative_to(root) for path in written)
    assert all(path.name.startswith("SAUP-") for path in written)


def test_pdf_extraction_returns_trusted_text_and_is_usable(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload(client, project_id, filename="acceptance-criteria.pdf", content=pdf_bytes("AC-001: Email must be unique")).json()["data"]["upload_id"]
    response = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "SUCCESS"
    assert data["document_type"] == "PDF"
    assert data["usable_as_context"] is True
    assert "AC-001" in data["extracted_text"]
    assert data["artifact_type"] == "ACCEPTANCE_CRITERIA"


def test_docx_extraction_succeeds(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload(client, project_id, filename="srs.docx", content=docx_bytes("Login requires MFA"), artifact_type="SRS").json()["data"]["upload_id"]
    data = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction").json()["data"]
    assert data["status"] == "SUCCESS"
    assert data["document_type"] == "DOCX"
    assert "Login requires MFA" in data["extracted_text"]
    assert data["usable_as_context"] is True


def test_failed_extraction_is_reported_honestly_and_not_usable(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload(client, project_id, filename="broken.pdf", content=b"%PDF-1.4 truncated and invalid").json()["data"]["upload_id"]
    response = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "FAILED"
    assert data["usable_as_context"] is False
    assert data["extracted_text"] == ""
    assert data["warnings"]


def test_cached_extraction_is_returned_without_recomputing(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload(client, project_id, filename="ac.txt", content=b"AC-002 refunds").json()["data"]["upload_id"]
    first = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction").json()["data"]
    cached = client.get(f"{uploads_url(project_id)}/{upload_id}/extraction").json()["data"]
    assert cached == first
    assert cached["extracted_text"] == "AC-002 refunds"


def test_image_stays_pending_and_no_content_is_fabricated(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload(client, project_id, filename="wireframe.png", content=PNG_BYTES,
                       source_type="IMAGE", artifact_type="UI_SPECIFICATION", mime="image/png").json()["data"]["upload_id"]
    extract = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction")
    assert extract.status_code == 422
    assert "Image understanding is not implemented" in extract.text
    assert "extracted_text" not in extract.text
    cached = client.get(f"{uploads_url(project_id)}/{upload_id}/extraction")
    assert cached.status_code == 422


def test_upload_ids_cannot_be_used_across_users_or_projects(artifact_context):
    authentication, _ = artifact_context
    owner = authentication.client("USR-001")
    intruder = authentication.client("USR-002")
    project_a = create_project(owner)
    project_b = create_project(owner)
    upload_id = upload(owner, project_a, filename="ac.txt", content=b"AC-003").json()["data"]["upload_id"]

    assert intruder.post(f"{uploads_url(project_a)}/{upload_id}/extraction").status_code == 404
    assert intruder.delete(f"{uploads_url(project_a)}/{upload_id}").status_code == 404
    assert owner.post(f"{uploads_url(project_b)}/{upload_id}/extraction").status_code == 404
    assert owner.get(f"{uploads_url(project_b)}/{upload_id}/extraction").status_code == 404


def test_malformed_upload_id_is_not_found(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    assert client.post(f"{uploads_url(project_id)}/SAUP-not-a-real-id/extraction").status_code == 404
    assert client.delete(f"{uploads_url(project_id)}/SAUP-not-a-real-id").status_code == 404


def test_delete_removes_stored_file_and_extraction(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload(client, project_id, filename="ac.txt", content=b"AC-004").json()["data"]["upload_id"]
    client.post(f"{uploads_url(project_id)}/{upload_id}/extraction")
    response = client.delete(f"{uploads_url(project_id)}/{upload_id}")
    assert response.status_code == 200
    assert response.json()["data"] == {"upload_id": upload_id, "deleted": True}
    assert not any(storage_root.rglob(f"{upload_id}*"))
    assert client.get(f"{uploads_url(project_id)}/{upload_id}/extraction").status_code == 404


def test_archived_project_refuses_new_uploads(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    archived = client.patch(f"/api/v1/agent-projects/{project_id}", json={"status": "ARCHIVED"})
    assert archived.status_code == 200
    response = upload(client, project_id, filename="ac.txt", content=b"AC")
    assert response.status_code == 409
