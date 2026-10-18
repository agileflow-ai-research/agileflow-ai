import fitz
from pathlib import Path

from app.modules.standalone.artifact_inputs import service as artifact_service
from app.modules.standalone.artifact_inputs.extraction.schemas import (
    ExtractionStatus,
    PDFContent,
    PDFMetrics,
)
from test_standalone_artifact_uploads import (  # noqa: F401  (fixtures)
    PNG_BYTES,
    artifact_context,
    create_project,
    pdf_bytes,
    upload,
    uploads_url,
)


def pdf_with_blank_second_page(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.new_page()
    data = document.tobytes()
    document.close()
    return data


def upload_id_of(response) -> str:
    return response.json()["data"]["upload_id"]


# ---- Partial extraction ------------------------------------------------------------------------


def test_partial_pdf_with_usable_text_is_usable_and_keeps_partial_status(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="srs.pdf", content=pdf_with_blank_second_page("REQ-001 Login"), artifact_type="SRS"))
    data = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction").json()["data"]
    assert data["status"] == "PARTIAL"
    assert data["usable_as_context"] is True
    assert "REQ-001 Login" in data["extracted_text"]


def test_partial_extraction_with_empty_text_is_not_usable(artifact_context, monkeypatch):
    def partial_without_text(path):
        return (
            ExtractionStatus.PARTIAL,
            PDFContent(pages=[], combined_text=""),
            PDFMetrics(page_count=1, processed_page_count=1, pages_with_text=0, pages_without_text=1, extracted_character_count=0),
            [],
        )

    monkeypatch.setattr(artifact_service, "extract_pdf", partial_without_text)
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="srs.pdf", content=pdf_bytes("x"), artifact_type="SRS"))
    data = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction").json()["data"]
    assert data["status"] == "PARTIAL"
    assert data["usable_as_context"] is False
    assert data["extracted_text"] == ""


def test_pending_document_has_no_extraction_result_to_use(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="srs.pdf", content=pdf_bytes("REQ"), artifact_type="SRS"))
    assert client.get(f"{uploads_url(project_id)}/{upload_id}/extraction").status_code == 404


def test_failed_extraction_is_not_usable_and_says_failed(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="broken.pdf", content=b"%PDF-1.4 broken", artifact_type="SRS"))
    data = client.post(f"{uploads_url(project_id)}/{upload_id}/extraction").json()["data"]
    assert data["status"] == "FAILED"
    assert data["usable_as_context"] is False


# ---- Upload deletion ---------------------------------------------------------------------------


def test_owner_deletes_own_unreferenced_upload(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="ac.txt", content=b"AC-010", artifact_type="ACCEPTANCE_CRITERIA"))
    response = client.delete(f"{uploads_url(project_id)}/{upload_id}")
    assert response.status_code == 200
    assert response.json()["data"] == {"upload_id": upload_id, "deleted": True}
    assert not any(storage_root.rglob(f"{upload_id}*"))


def test_deleting_an_image_removes_the_stored_artifact(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="wire.png", content=PNG_BYTES,
                                    source_type="IMAGE", artifact_type="UI_SPECIFICATION", mime="image/png"))
    assert any(storage_root.rglob(f"{upload_id}*"))
    assert client.delete(f"{uploads_url(project_id)}/{upload_id}").status_code == 200
    assert not any(storage_root.rglob(f"{upload_id}*"))


def test_delete_removes_metadata_and_extraction_sidecars(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="srs.pdf", content=pdf_bytes("REQ-020"), artifact_type="SRS"))
    client.post(f"{uploads_url(project_id)}/{upload_id}/extraction")
    project_dir = storage_root / project_id / "inputs"
    assert (project_dir / f"{upload_id}.extracted.json").exists()
    assert client.delete(f"{uploads_url(project_id)}/{upload_id}").status_code == 200
    for suffix in (".pdf", ".metadata.json", ".extracted.json", ".extracted.json.part"):
        assert not (project_dir / f"{upload_id}{suffix}").exists()
    assert client.get(f"{uploads_url(project_id)}/{upload_id}/extraction").status_code == 404


def test_second_delete_of_the_same_upload_is_a_safe_not_found(artifact_context):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    upload_id = upload_id_of(upload(client, project_id, filename="ac.txt", content=b"AC-011"))
    assert client.delete(f"{uploads_url(project_id)}/{upload_id}").status_code == 200
    second = client.delete(f"{uploads_url(project_id)}/{upload_id}")
    assert second.status_code == 404
    assert second.json()["message"] == "Artifact upload not found"


def test_foreign_user_cannot_delete_another_users_upload(artifact_context):
    authentication, storage_root = artifact_context
    owner = authentication.client("USR-001")
    intruder = authentication.client("USR-002")
    project_id = create_project(owner)
    upload_id = upload_id_of(upload(owner, project_id, filename="ac.txt", content=b"AC-012"))
    response = intruder.delete(f"/api/v1/agent-projects/{project_id}/artifact-uploads/{upload_id}")
    assert response.status_code == 404
    assert any(storage_root.rglob(f"{upload_id}.txt"))


def test_upload_cannot_be_deleted_through_another_project(artifact_context):
    authentication, storage_root = artifact_context
    owner = authentication.client()
    project_a = create_project(owner)
    project_b = create_project(owner)
    upload_id = upload_id_of(upload(owner, project_a, filename="ac.txt", content=b"AC-013"))
    response = owner.delete(f"{uploads_url(project_b)}/{upload_id}")
    assert response.status_code == 404
    assert any((storage_root / project_a / "inputs").glob(f"{upload_id}*"))


def test_unknown_upload_delete_is_a_safe_not_found_without_paths(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = client.delete(f"{uploads_url(project_id)}/SAUP-0123456789abcdef0123456789abcdef")
    assert response.status_code == 404
    assert str(storage_root) not in response.text
    assert "/" not in response.json()["errors"][0]["message"]


def test_traversal_and_arbitrary_path_deletion_is_impossible(artifact_context, tmp_path):
    authentication, _ = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me", encoding="utf-8")
    for candidate in ("../../victim", "SAUP-../../victim", "..%2F..%2Fvictim.txt", "victim.txt"):
        response = client.delete(f"{uploads_url(project_id)}/{candidate}")
        assert response.status_code in {404, 405}
    assert Path(victim).read_text(encoding="utf-8") == "keep me"


def test_delete_errors_never_expose_filesystem_paths(artifact_context):
    authentication, storage_root = artifact_context
    client = authentication.client()
    project_id = create_project(client)
    response = client.delete(f"{uploads_url(project_id)}/SAUP-ffffffffffffffffffffffffffffffff")
    assert str(storage_root) not in response.text
    assert str(storage_root.parent) not in response.text
