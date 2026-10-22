import io
import pytest
from docx import Document
from pypdf import PdfWriter

from app.common.document_extractor import (
    DocumentExtractionFailedError,
    DocumentTextNotFoundError,
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
    extract_document_text,
)
from app.main import app
from app.modules.agents.design_planning.router import get_agent2_engine
from app.modules.standalone.router import get_agent_project_repository, get_agent_run_repository
from test_standalone_foundation import FakeAgentProjectRepository, FakeAgentRunRepository


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    # Add an annotation or text if possible, or use blank
    # For text in pypdf, creating text directly without reportlab can be done via writer or mock,
    # or write a minimal valid PDF with a text stream:
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class CountingEngine:
    def __init__(self):
        self.calls = 0

    def execute_with_metadata(self, *args, **kwargs):
        self.calls += 1
        raise RuntimeError("Engine should not be called")


@pytest.fixture
def extraction_context(authentication_context):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    engine = CountingEngine()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent2_engine] = lambda: engine
    try:
        yield authentication_context, projects, runs, engine
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent2_engine, None)


def create_project(client, agent_type="DESIGN_PLANNING"):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": agent_type, "name": "BookEase", "domain": "Hospitality"},
    )
    assert response.status_code == 201
    return response.json()["data"]


# --- Unit Tests for extract_document_text ---

def test_extract_docx_valid():
    content = _make_docx_bytes(["Software Requirements Specification", "User can login to BookEase."])
    text, mime, char_count, sha = extract_document_text(content, "sample.docx")
    assert "Software Requirements Specification" in text
    assert "User can login to BookEase." in text
    assert "openxmlformats" in mime
    assert char_count == len(text)
    assert len(sha) == 64


def test_extract_txt_valid():
    content = b"Simple requirement text in UTF-8 format."
    text, mime, char_count, sha = extract_document_text(content, "specs.txt", "text/plain")
    assert text == "Simple requirement text in UTF-8 format."
    assert mime == "text/plain"
    assert char_count == len(text)


def test_extract_md_valid():
    content = b"# SRS Title\n\n- Requirement 1\n- Requirement 2"
    text, mime, char_count, sha = extract_document_text(content, "spec.md")
    assert "# SRS Title" in text
    assert mime == "text/markdown"
    assert char_count == len(text)


def test_unsupported_extension_rejected():
    with pytest.raises(UnsupportedDocumentTypeError, match="Unsupported file extension"):
        extract_document_text(b"some content", "file.exe")


def test_oversized_file_rejected():
    oversized = b"a" * (10 * 1024 * 1024 + 1)
    with pytest.raises(DocumentTooLargeError, match="maximum allowed size"):
        extract_document_text(oversized, "huge.txt")


def test_empty_document_rejected():
    with pytest.raises(DocumentTextNotFoundError, match="empty"):
        extract_document_text(b"", "empty.txt")


def test_blank_pdf_rejected_as_no_extractable_text():
    pdf_bytes = _make_pdf_bytes("")
    with pytest.raises(DocumentTextNotFoundError, match="No extractable text found"):
        extract_document_text(pdf_bytes, "blank.pdf")


# --- Endpoint Integration Tests ---

def test_extract_endpoint_success_docx(extraction_context):
    auth, _, _, engine = extraction_context
    client = auth.client()
    project = create_project(client)

    docx_bytes = _make_docx_bytes(["System requirements for BookEase", "Guest can book a slot."])

    files = {"file": ("BookEase.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"source_type": "SRS"}

    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/specification/extract",
        files=files,
        data=data,
    )
    assert response.status_code == 200
    res = response.json()["data"]
    assert res["source_type"] == "SRS"
    assert res["original_filename"] == "BookEase.docx"
    assert "System requirements for BookEase" in res["extracted_text"]
    assert res["extraction_status"] == "COMPLETED"
    assert res["character_count"] > 0
    assert engine.calls == 0  # Does NOT call Agent2Engine!


def test_extract_endpoint_success_txt(extraction_context):
    auth, _, _, engine = extraction_context
    client = auth.client()
    project = create_project(client)

    files = {"file": ("requirements.txt", b"User can register and cancel appointments.", "text/plain")}
    data = {"source_type": "REQUIREMENTS"}

    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/specification/extract",
        files=files,
        data=data,
    )
    assert response.status_code == 200
    res = response.json()["data"]
    assert res["source_type"] == "REQUIREMENTS"
    assert res["extracted_text"] == "User can register and cancel appointments."
    assert engine.calls == 0


def test_extract_endpoint_unsupported_file_type(extraction_context):
    auth, _, _, _ = extraction_context
    client = auth.client()
    project = create_project(client)

    files = {"file": ("malicious.bat", b"echo evil", "application/x-bat")}
    data = {"source_type": "SRS"}

    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/specification/extract",
        files=files,
        data=data,
    )
    assert response.status_code == 422
    assert "UNSUPPORTED_DOCUMENT_TYPE" in response.json()["errors"][0]["message"]


def test_extract_endpoint_invalid_source_type(extraction_context):
    auth, _, _, _ = extraction_context
    client = auth.client()
    project = create_project(client)

    files = {"file": ("spec.txt", b"content", "text/plain")}
    data = {"source_type": "INVALID_TYPE"}

    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/specification/extract",
        files=files,
        data=data,
    )
    assert response.status_code == 422
    assert "source_type must be one of" in response.json()["errors"][0]["message"]


def test_extract_endpoint_wrong_agent_project_type(extraction_context):
    auth, _, _, _ = extraction_context
    client = auth.client()
    wrong_project = create_project(client, agent_type="REQUIREMENTS")

    files = {"file": ("spec.txt", b"content", "text/plain")}
    data = {"source_type": "SRS"}

    response = client.post(
        f"/api/v1/agents/design-planning/{wrong_project['agent_project_id']}/specification/extract",
        files=files,
        data=data,
    )
    assert response.status_code == 422
    assert "DESIGN_PLANNING" in response.json()["errors"][0]["message"]


def test_extract_endpoint_archived_project_rejected(extraction_context):
    auth, _, _, _ = extraction_context
    client = auth.client()
    project = create_project(client)
    client.patch(f"/api/v1/agent-projects/{project['agent_project_id']}", json={"status": "ARCHIVED"})

    files = {"file": ("spec.txt", b"content", "text/plain")}
    data = {"source_type": "SRS"}

    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/specification/extract",
        files=files,
        data=data,
    )
    assert response.status_code == 409
    assert "archived" in response.json()["message"]


def test_extract_real_bookease_sample_docx(extraction_context):
    auth, _, _, engine = extraction_context
    client = auth.client()
    project = create_project(client)

    import os
    docx_path = r"C:\Users\hp\Downloads\BookEase_Sample_SRS_Agent2_Full_Workflow.docx"
    if os.path.exists(docx_path):
        with open(docx_path, "rb") as f:
            docx_bytes = f.read()

        files = {"file": ("BookEase_Sample_SRS_Agent2_Full_Workflow.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {"source_type": "SRS"}

        response = client.post(
            f"/api/v1/agents/design-planning/{project['agent_project_id']}/specification/extract",
            files=files,
            data=data,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["original_filename"] == "BookEase_Sample_SRS_Agent2_Full_Workflow.docx"
        assert data["character_count"] > 10000
        assert "BookEase" in data["extracted_text"]
        assert engine.calls == 0
