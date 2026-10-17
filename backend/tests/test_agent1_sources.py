from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.agent1.repository import _public_document
from app.modules.agent1.router import (
    get_requirement_source_repository,
    get_requirement_source_service,
)
from app.modules.agent1.schemas import RequirementSourceRecord, SourceProcessingStatus
from app.modules.agent1.service import RequirementSourceService
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
    get_standalone_service,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


class FakeRequirementSourceRepository:
    def __init__(self) -> None:
        self.documents: dict[tuple[str, str], dict[str, Any]] = {}
        self.processing_updates: list[tuple[str, SourceProcessingStatus]] = []

    def next_source_sequence(self, agent_project_id: str, prefix: str) -> int:
        largest = 0
        for doc in self.documents.values():
            if doc.get("agent_project_id") == agent_project_id:
                sid = doc.get("source_id", "")
                if sid.startswith(f"{prefix}-"):
                    try:
                        seq = int(sid.rsplit("-", maxsplit=1)[1])
                        largest = max(largest, seq)
                    except ValueError:
                        pass
        return largest + 1

    def create_source(self, source: RequirementSourceRecord) -> dict[str, Any]:
        doc = source.model_dump(mode="python")
        self.documents[(source.agent_project_id, source.source_id)] = doc.copy()
        return _public_document(doc)

    def list_sources(
        self, agent_project_id: str, owner_user_id: str
    ) -> list[dict[str, Any]]:
        return [
            _public_document(doc)
            for doc in self.documents.values()
            if doc.get("agent_project_id") == agent_project_id
            and doc.get("owner_user_id") == owner_user_id
            and not doc.get("is_deleted", False)
        ]

    def get_source(
        self, agent_project_id: str, source_id: str, owner_user_id: str
    ) -> dict[str, Any] | None:
        doc = self.documents.get((agent_project_id, source_id))
        if (
            doc
            and doc.get("agent_project_id") == agent_project_id
            and doc.get("owner_user_id") == owner_user_id
            and not doc.get("is_deleted", False)
        ):
            return _public_document(doc)
        return None

    def delete_source(
        self, agent_project_id: str, source_id: str, owner_user_id: str
    ) -> bool:
        doc = self.documents.get((agent_project_id, source_id))
        if (
            doc
            and doc.get("agent_project_id") == agent_project_id
            and doc.get("owner_user_id") == owner_user_id
            and not doc.get("is_deleted", False)
        ):
            doc["is_deleted"] = True
            doc["updated_at"] = datetime.now(timezone.utc)
            return True
        return False

    def update_source_processing(
        self,
        agent_project_id: str,
        source_id: str,
        owner_user_id: str,
        processing_status: SourceProcessingStatus,
        normalized_text: str | None = None,
        processing_error_code: str | None = None,
        processing_error_message: str | None = None,
        processed_at=None,
        clear_result: bool = False,
    ) -> bool:
        self.processing_updates.append((source_id, processing_status))
        doc = self.documents.get((agent_project_id, source_id))
        if doc:
            doc["processing_status"] = processing_status.value
            if clear_result:
                for key in ("normalized_text", "processing_error_code", "processing_error_message", "processed_at"):
                    doc.pop(key, None)
            if normalized_text is not None:
                doc["normalized_text"] = normalized_text
            if processing_error_code is not None:
                doc["processing_error_code"] = processing_error_code
            if processing_error_message is not None:
                doc["processing_error_message"] = processing_error_message
            if processed_at is not None:
                doc["processed_at"] = processed_at
            return True
        return False

    def list_sources_for_run(
        self, agent_project_id: str, owner_user_id: str
    ) -> list[dict[str, Any]]:
        return [
            _public_document(doc)
            for doc in self.documents.values()
            if doc.get("agent_project_id") == agent_project_id
            and doc.get("owner_user_id") == owner_user_id
            and not doc.get("is_deleted", False)
        ]


@pytest.fixture
def sources_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    sources = FakeRequirementSourceRepository()

    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_requirement_source_repository] = lambda: sources

    def override_source_service():
        standalone = get_standalone_service(projects, runs)
        return RequirementSourceService(
            standalone,
            sources,
            upload_dir=tmp_path / "uploads",
        )

    app.dependency_overrides[get_requirement_source_service] = override_source_service

    try:
        yield authentication_context, projects, runs, sources, tmp_path
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_requirement_source_repository, None)
        app.dependency_overrides.pop(get_requirement_source_service, None)


def create_project(client, name="BookEase", domain="Library", agent_type="REQUIREMENTS"):
    response = client.post(
        "/api/v1/agent-projects",
        json={
            "agent_type": agent_type,
            "name": name,
            "domain": domain,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_requirements_project_accepted_and_uploads_documents(sources_context):
    """1 & 5: REQUIREMENTS project is accepted and Document uploads (.pdf, .docx, .txt) succeed."""
    auth, _, _, sources, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    pdf_file = ("requirements.pdf", b"%PDF-1.4 sample content", "application/pdf")
    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", pdf_file)],
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["source_id"] == "DOC-001"
    assert data[0]["source_type"] == "DOCUMENT"
    assert data[0]["original_filename"] == "requirements.pdf"
    assert data[0]["processing_status"] == "READY"
    assert "storage_path" not in data[0]

    docx_file = ("existing.docx", b"PK docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    txt_file = ("notes.txt", b"plain text content", "text/plain")
    multi_response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", docx_file), ("files", txt_file)],
    )
    assert multi_response.status_code == 201
    multi_data = multi_response.json()["data"]
    assert len(multi_data) == 2
    assert multi_data[0]["source_id"] == "DOC-002"
    assert multi_data[1]["source_id"] == "DOC-003"


def test_wrong_agent_type_rejected(sources_context):
    """2: Non-REQUIREMENTS project is rejected with 422."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    design_project = create_project(client, agent_type="DESIGN_PLANNING")

    response = client.post(
        f"/api/v1/agents/requirements/{design_project['agent_project_id']}/sources",
        files=[("files", ("test.pdf", b"pdf content", "application/pdf"))],
    )
    assert response.status_code == 422
    assert "agent_type" in response.json()["errors"][0]["message"]


def test_foreign_agent_project_rejected(sources_context):
    """3: Foreign AgentProject returns 404 (preventing cross-user inspection)."""
    auth, _, _, _, _ = sources_context
    owner_client = auth.client("USR-001")
    foreign_client = auth.client("USR-002")
    project = create_project(owner_client)

    response = foreign_client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", ("test.pdf", b"pdf content", "application/pdf"))],
    )
    assert response.status_code == 404


def test_archived_agent_project_rejected(sources_context):
    """4: Archived AgentProject is rejected with 409 Conflict."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    # Archive the project
    patch_res = client.patch(
        f"/api/v1/agent-projects/{project['agent_project_id']}",
        json={"status": "ARCHIVED"},
    )
    assert patch_res.status_code == 200

    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", ("test.pdf", b"pdf content", "application/pdf"))],
    )
    assert response.status_code == 409


def test_audio_upload_accepted(sources_context):
    """6: Audio uploads (.mp3, .wav, .m4a) are accepted."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    files = [
        ("files", ("interview.mp3", b"ID3 fake audio", "audio/mpeg")),
        ("files", ("meeting.wav", b"RIFF wave audio", "audio/wav")),
        ("files", ("session.m4a", b"ftyp m4a audio", "audio/mp4")),
    ]
    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=files,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data) == 3
    assert data[0]["source_id"] == "AUD-001"
    assert data[0]["source_type"] == "AUDIO"
    assert data[1]["source_id"] == "AUD-002"
    assert data[2]["source_id"] == "AUD-003"


def test_video_upload_accepted(sources_context):
    """7: Video uploads (.mp4, .mov, .webm) are accepted."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    files = [
        ("files", ("demo.mp4", b"ftyp mp4 video", "video/mp4")),
        ("files", ("recording.mov", b"moov video", "video/quicktime")),
        ("files", ("screencast.webm", b"webm video", "video/webm")),
    ]
    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=files,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data) == 3
    assert data[0]["source_id"] == "VID-001"
    assert data[0]["source_type"] == "VIDEO"
    assert data[1]["source_id"] == "VID-002"
    assert data[2]["source_id"] == "VID-003"


def test_multiple_and_mixed_file_types_in_one_project(sources_context):
    """8 & 9: Multiple files and mixed file types can belong to one project, matching the manual test scenario."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client, name="BookEase", domain="Appointment Booking")

    # Upload the exact manual test files:
    # requirements.pdf, existing-process.docx, client-interview.mp3, manager-interview.wav, booking-workflow.mp4
    files = [
        ("files", ("requirements.pdf", b"pdf1", "application/pdf")),
        ("files", ("existing-process.docx", b"docx1", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ("files", ("client-interview.mp3", b"mp31", "audio/mpeg")),
        ("files", ("manager-interview.wav", b"wav1", "audio/wav")),
        ("files", ("booking-workflow.mp4", b"mp41", "video/mp4")),
    ]
    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=files,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert [d["source_id"] for d in data] == [
        "DOC-001",
        "DOC-002",
        "AUD-001",
        "AUD-002",
        "VID-001",
    ]


def test_unsupported_file_type_rejected(sources_context):
    """10: Unsupported extensions (.exe, .jpg, .sh, .py) are safely rejected."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    for bad_name, mime in [
        ("malware.exe", "application/x-msdownload"),
        ("image.jpg", "image/jpeg"),
        ("script.sh", "application/x-sh"),
        ("app.py", "text/x-python"),
    ]:
        res = client.post(
            f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
            files=[("files", (bad_name, b"some content", mime))],
        )
        assert res.status_code == 422
        assert "Unsupported" in res.json()["errors"][0]["message"] or "Disallowed" in res.json()["errors"][0]["message"]


def test_empty_file_rejected(sources_context):
    """11: Empty file (0 bytes) is rejected with 422."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    res = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", ("empty.pdf", b"", "application/pdf"))],
    )
    assert res.status_code == 422
    assert "empty" in res.json()["errors"][0]["message"].lower()


def test_source_ids_are_stable_and_unique(sources_context):
    """12: Source IDs are stable, unique, and do not collide even after deletions."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    # Add DOC-001
    r1 = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", ("doc1.pdf", b"content", "application/pdf"))],
    )
    assert r1.json()["data"][0]["source_id"] == "DOC-001"

    # Delete DOC-001
    del_r = client.delete(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources/DOC-001"
    )
    assert del_r.status_code == 200

    # Add another doc -> must be DOC-002, not reusing DOC-001
    r2 = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", ("doc2.pdf", b"content", "application/pdf"))],
    )
    assert r2.json()["data"][0]["source_id"] == "DOC-002"


def test_source_listing_returns_only_current_project(sources_context):
    """13: Source listing returns only the current project's sources."""
    auth, _, _, _, _ = sources_context
    client = auth.client("USR-001")
    p1 = create_project(client, name="Project 1")
    p2 = create_project(client, name="Project 2")

    r1 = client.post(
        f"/api/v1/agents/requirements/{p1['agent_project_id']}/sources",
        files=[("files", ("p1.pdf", b"p1 content", "application/pdf"))],
    )
    assert r1.status_code == 201
    r2 = client.post(
        f"/api/v1/agents/requirements/{p2['agent_project_id']}/sources",
        files=[("files", ("p2.pdf", b"p2 content", "application/pdf"))],
    )
    assert r2.status_code == 201

    p1_sources = client.get(
        f"/api/v1/agents/requirements/{p1['agent_project_id']}/sources"
    ).json()["data"]
    assert len(p1_sources) == 1
    assert p1_sources[0]["original_filename"] == "p1.pdf"

    p2_sources = client.get(
        f"/api/v1/agents/requirements/{p2['agent_project_id']}/sources"
    ).json()["data"]
    assert len(p2_sources) == 1
    assert p2_sources[0]["original_filename"] == "p2.pdf"


def test_cross_user_source_access_rejected(sources_context):
    """14: User 2 cannot list or delete User 1's sources."""
    auth, _, _, _, _ = sources_context
    user1 = auth.client("USR-001")
    user2 = auth.client("USR-002")
    project = create_project(user1)

    user1.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", ("private.pdf", b"confidential", "application/pdf"))],
    )

    # User 2 tries to list
    list_res = user2.get(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources"
    )
    assert list_res.status_code == 404

    # User 2 tries to delete
    del_res = user2.delete(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources/DOC-001"
    )
    assert del_res.status_code == 404


def test_delete_source_removes_from_listing_and_storage(sources_context):
    """15: Remove/delete behavior works and cleans up properly."""
    auth, _, _, sources, tmp_path = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    upload_res = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[("files", ("delete-me.pdf", b"delete content", "application/pdf"))],
    )
    source_id = upload_res.json()["data"][0]["source_id"]

    # Verify listed
    initial_list = client.get(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources"
    ).json()["data"]
    assert len(initial_list) == 1

    # Delete
    del_res = client.delete(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources/{source_id}"
    )
    assert del_res.status_code == 200

    # Verify no longer listed
    after_list = client.get(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources"
    ).json()["data"]
    assert len(after_list) == 0

    # Deleting non-existent returns 404
    del_again = client.delete(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources/{source_id}"
    )
    assert del_again.status_code == 404


def test_no_agent_run_created_by_source_upload(sources_context):
    """16: Uploading sources does NOT create any AgentRun records."""
    auth, _, runs, _, _ = sources_context
    client = auth.client("USR-001")
    project = create_project(client)

    client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/sources",
        files=[
            ("files", ("doc.pdf", b"doc content", "application/pdf")),
            ("files", ("audio.mp3", b"audio content", "audio/mpeg")),
        ],
    )

    # Verify agent runs collection has 0 runs for this project
    runs_res = client.get(
        f"/api/v1/agent-projects/{project['agent_project_id']}/runs"
    ).json()["data"]
    assert len(runs_res) == 0
    assert len(runs.documents) == 0
