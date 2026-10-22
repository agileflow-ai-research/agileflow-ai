import json

import pytest

from app.main import app
from app.modules.agents.implementation.preparation import constants
from app.modules.agents.implementation.preparation.schemas import ChunkingStatus
from app.modules.agents.implementation.preparation.chunking.tokenizer import count_tokens
from test_agent3_document_extraction import (
    PNG,
    create_project,
    docx_bytes,
    extraction_context,
    extract,
    pdf_bytes,
    upload,
    upload_dir,
)


def build(client, project_id, upload_id, *, force=False):
    return client.post(
        f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/chunks",
        params={"force": str(force).lower()},
    )


def get_chunks(client, project_id, upload_id):
    return client.get(
        f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/chunks"
    )


def prepared(client, filename, content):
    project = create_project(client)
    metadata = upload(client, project["agent_project_id"], filename, content)
    extraction = extract(client, project["agent_project_id"], metadata["upload_id"])
    assert extraction.status_code == 200
    return project, metadata, extraction.json()["data"]


def test_chunking_status_enum_and_lexical_counter_are_deterministic():
    assert {item.value for item in ChunkingStatus} == {"SUCCESS", "PARTIAL", "FAILED"}
    sample = "POST /api/bookings uses Node.js 20.1."
    assert count_tokens(sample) == count_tokens(sample)
    assert count_tokens(sample) >= 5


def test_get_is_read_only_and_build_is_stable_with_hashes(extraction_context):
    authentication, _, _ = extraction_context
    client = authentication.client()
    project, metadata, _ = prepared(
        client, "requirements.md", b"# Requirements\n\nUsers create bookings."
    )
    assert get_chunks(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    first = build(client, project["agent_project_id"], metadata["upload_id"])
    second = build(client, project["agent_project_id"], metadata["upload_id"])
    assert first.status_code == second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    chunk = first.json()["data"]["chunks"][0]
    assert chunk["chunk_id"].startswith("CHK-")
    assert len(chunk["text_hash"]) == 64
    assert chunk["context"]["heading_path"] == ["Requirements"]
    assert "file_path" not in json.dumps(first.json())


@pytest.mark.parametrize("change", ["source_sha256", "extraction_version", "chunker_version", "malformed"])
def test_stale_or_malformed_chunk_cache_is_rebuilt(extraction_context, change):
    authentication, _, root = extraction_context
    client = authentication.client()
    project, metadata, _ = prepared(client, "notes.txt", b"Useful deterministic content.")
    expected = build(client, project["agent_project_id"], metadata["upload_id"]).json()["data"]
    sidecar = upload_dir(root, project["agent_project_id"]) / f'{metadata["upload_id"]}.chunks.json'
    if change == "malformed":
        sidecar.write_text("not-json", encoding="utf-8")
    else:
        cached = json.loads(sidecar.read_text(encoding="utf-8"))
        cached[change] = "0" * 64 if change == "source_sha256" else "999"
        sidecar.write_text(json.dumps(cached), encoding="utf-8")
    assert get_chunks(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    rebuilt = build(client, project["agent_project_id"], metadata["upload_id"])
    assert rebuilt.status_code == 200
    assert rebuilt.json()["data"]["chunks"] == expected["chunks"]


def test_failed_and_partial_extractions_have_correct_chunk_status(extraction_context):
    authentication, _, _ = extraction_context
    client = authentication.client()
    project = create_project(client)
    empty = upload(client, project["agent_project_id"], "empty.txt", b" \n")
    assert extract(client, project["agent_project_id"], empty["upload_id"]).json()["data"]["status"] == "FAILED"
    assert build(client, project["agent_project_id"], empty["upload_id"]).status_code == 422

    partial = upload(client, project["agent_project_id"], "partial.pdf", pdf_bytes("Useful", ""))
    extract(client, project["agent_project_id"], partial["upload_id"])
    result = build(client, project["agent_project_id"], partial["upload_id"]).json()["data"]
    assert result["status"] == "PARTIAL"
    assert "SOURCE_EXTRACTION_PARTIAL" in result["warnings"]
    assert result["chunks"][0]["provenance"]["page_start"] == 1


def test_pdf_sections_pages_and_bounded_overlap(extraction_context, monkeypatch):
    authentication, _, _ = extraction_context
    client = authentication.client()
    monkeypatch.setattr(constants, "TARGET_CHUNK_TOKENS", 8)
    monkeypatch.setattr(constants, "MAX_CHUNK_TOKENS", 12)
    monkeypatch.setattr(constants, "OVERLAP_TOKENS", 3)
    project, metadata, _ = prepared(
        client,
        "spec.pdf",
        pdf_bytes("1. Requirements\n" + "word " * 18, "word " * 10, "2. Database\nshort section"),
    )
    result = build(client, project["agent_project_id"], metadata["upload_id"]).json()["data"]
    assert result["metrics"]["max_chunk_tokens"] <= 12
    assert any(chunk["provenance"]["page_end"] >= chunk["provenance"]["page_start"] for chunk in result["chunks"])
    assert {chunk["context"]["section_title"] for chunk in result["chunks"]} >= {"1. Requirements", "2. Database"}


def test_docx_heading_hierarchy_blocks_and_table_header(extraction_context, monkeypatch):
    authentication, _, _ = extraction_context
    client = authentication.client()
    monkeypatch.setattr(constants, "MAX_CHUNK_TOKENS", 18)
    monkeypatch.setattr(constants, "TARGET_CHUNK_TOKENS", 12)
    rows = [["Method", "Endpoint"], *[["POST", f"/api/items/{index}"] for index in range(12)]]
    project, metadata, _ = prepared(client, "api.docx", docx_bytes([
        ("heading", "Requirements", 1), ("heading", "Booking", 2),
        ("paragraph", "Create and update bookings."), ("table", rows),
    ]))
    result = build(client, project["agent_project_id"], metadata["upload_id"]).json()["data"]
    assert all(chunk["context"]["heading_path"] == ["Requirements", "Booking"] for chunk in result["chunks"])
    assert all(chunk["provenance"]["block_start"] is not None for chunk in result["chunks"])
    table_chunks = [chunk for chunk in result["chunks"] if chunk["context"]["structure_type"] == "TABLE"]
    assert len(table_chunks) > 1
    assert all("Method | Endpoint" in chunk["text"] for chunk in table_chunks)


def test_markdown_txt_and_structured_provenance(extraction_context):
    authentication, _, _ = extraction_context
    client = authentication.client()
    markdown = b"# API\n\nIntro paragraph.\n\n## Calls\n\n```js\nfetch('/api')\n```"
    project, metadata, _ = prepared(client, "api.md", markdown)
    md_result = build(client, project["agent_project_id"], metadata["upload_id"]).json()["data"]
    assert ["API", "Calls"] in [chunk["context"]["heading_path"] for chunk in md_result["chunks"]]
    assert any(chunk["context"]["structure_type"] == "CODE_BLOCK" for chunk in md_result["chunks"])
    assert all(chunk["provenance"]["line_start"] for chunk in md_result["chunks"])

    for filename, payload in (
        ("model.json", b'{"tables":{"users":{"id":"uuid"},"bookings":{"id":"uuid"}}}'),
        ("model.yaml", b"tables:\n  users:\n    id: uuid\n  bookings:\n    id: uuid\n"),
    ):
        project, metadata, _ = prepared(client, filename, payload)
        result = build(client, project["agent_project_id"], metadata["upload_id"]).json()["data"]
        paths = [chunk["provenance"]["structured_path"] for chunk in result["chunks"]]
        assert paths and all(path.startswith("$.") for path in paths)
        assert "tables" in result["chunks"][0]["text"]


def test_security_guards_image_and_deletion_cleanup(extraction_context):
    authentication, _, root = extraction_context
    owner, foreign = authentication.client("USR-001"), authentication.client("USR-002")
    project, metadata, _ = prepared(owner, "notes.txt", b"Delete semantic chunks.")
    build(owner, project["agent_project_id"], metadata["upload_id"])
    assert build(foreign, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    directory = upload_dir(root, project["agent_project_id"])
    assert (directory / f'{metadata["upload_id"]}.chunks.json').exists()
    response = owner.delete(f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}')
    assert response.status_code == 200
    assert not (directory / f'{metadata["upload_id"]}.chunks.json').exists()

    image_project = create_project(owner)
    image = upload(owner, image_project["agent_project_id"], "wireframe.png", PNG, "IMAGE")
    assert build(owner, image_project["agent_project_id"], image["upload_id"]).status_code == 422


def test_maximum_chunk_count_is_bounded_and_reported(extraction_context, monkeypatch):
    authentication, _, _ = extraction_context
    client = authentication.client()
    monkeypatch.setattr(constants, "MAX_CHUNKS_PER_DOCUMENT", 2)
    source = "\n\n".join(f"{index}. Section {index}\ncontent {index}" for index in range(6))
    project, metadata, _ = prepared(client, "many.txt", source.encode())
    result = build(client, project["agent_project_id"], metadata["upload_id"]).json()["data"]
    assert result["status"] == "PARTIAL"
    assert result["metrics"]["chunk_count"] == 2
    assert "CONTENT_TRUNCATED" in result["warnings"]


def test_openapi_has_only_chunk_preparation_routes_for_this_stage():
    paths = app.openapi()["paths"]
    path = "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/chunks"
    assert set(paths[path]) == {"get", "post"}
    assert not any("classification" in route or "agent-run" in route for route in paths if route.startswith("/api/v1/agents/implementation"))
