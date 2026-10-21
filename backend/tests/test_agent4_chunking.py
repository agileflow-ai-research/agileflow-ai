import json
from pathlib import Path

import pytest

from app.main import app
from app.modules.agents.testing_validation.preparation.chunking import constants
from app.modules.agents.testing_validation.preparation.chunking.service import (
    Agent4ChunkingNotApplicableError,
    Agent4ChunkingService,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
    Agent4ChunkStorageError,
)
from app.modules.agents.testing_validation.preparation.chunking.tokenizer import (
    TOKEN_PATTERN,
    count_tokens,
)
from app.modules.agents.testing_validation.preparation.extraction import (
    service as extraction_service_module,
)
from app.modules.agents.testing_validation.preparation.extraction.service import (
    Agent4ExtractionGateError,
)
from app.modules.agents.testing_validation.preparation.normalization.service import (
    Agent4NormalizationNotFoundError,
)
from test_agent4_document_extraction import (
    add_text,
    confirm,
    confirmed_document,
    create_project,
    docx_bytes,
    extraction_context,
    pdf_bytes,
    source_url,
)
from test_agent4_normalization import normalization_context
from test_standalone_foundation import user


@pytest.fixture
def chunking_context(normalization_context):
    client, extraction, normalization, root, projects, runs = normalization_context
    chunking = Agent4ChunkingService(normalization, Agent4ChunkStorage(root))
    return client, extraction, normalization, chunking, root, projects, runs


def normalize_text_source(client, normalization, content):
    project_id = create_project(client)
    response = client.post(
        f"{source_url(project_id)}/text",
        json={
            "artifact_type": "FUNCTIONAL_REQUIREMENTS",
            "normally_supplied_by": "AGENT_1",
            "content": content,
        },
    )
    assert response.status_code == 201
    source = response.json()["data"]
    confirm(client, project_id)
    normalized = normalization.normalize(project_id, source["source_id"], user())
    return project_id, source, normalized


def test_short_confirmed_text_produces_one_exact_chunk(chunking_context):
    client, _, normalization, chunking, root, _, _ = chunking_context
    content = "Customer can create an appointment.\nInternal  spacing remains."
    project_id, source, normalized = normalize_text_source(
        client, normalization, content
    )
    result = chunking.build(project_id, source["source_id"], user())
    assert result.metrics.chunk_count == 1
    chunk = result.chunks[0]
    assert chunk.text == normalized.normalized_text == content
    assert chunk.token_count == count_tokens(content)
    assert chunk.source_segment_ids == [
        normalized.normalized_segments[0].segment_id
    ]
    assert chunk.artifact_type.value == "FUNCTIONAL_REQUIREMENTS"
    assert chunk.source_type.value == "TEXT"
    sidecar = (
        root / project_id / "preparation" / f"{source['source_id']}.chunks.json"
    )
    assert sidecar.is_file()


def test_adjacent_text_paragraphs_combine_without_rewriting(
    chunking_context, monkeypatch
):
    client, _, normalization, chunking, _, _, _ = chunking_context
    monkeypatch.setattr(constants, "TARGET_CHUNK_TOKENS", 30)
    monkeypatch.setattr(constants, "MAX_CHUNK_TOKENS", 40)
    content = "First paragraph keeps punctuation!\n\nSecond paragraph keeps  spacing."
    project_id, source, _ = normalize_text_source(client, normalization, content)
    result = chunking.build(project_id, source["source_id"], user())
    assert len(result.chunks) == 1
    assert result.chunks[0].text == content


def test_oversized_text_splits_with_bounded_overlap_and_no_empty_chunks(
    chunking_context, monkeypatch
):
    client, _, normalization, chunking, _, _, _ = chunking_context
    monkeypatch.setattr(constants, "TARGET_CHUNK_TOKENS", 6)
    monkeypatch.setattr(constants, "MAX_CHUNK_TOKENS", 8)
    monkeypatch.setattr(constants, "OVERLAP_TOKENS", 2)
    content = " ".join(f"word{index}" for index in range(25))
    project_id, source, _ = normalize_text_source(client, normalization, content)
    result = chunking.build(project_id, source["source_id"], user())
    assert len(result.chunks) > 1
    assert all(0 < chunk.token_count <= 8 for chunk in result.chunks)
    assert result.chunks[0].overlap_token_count == 0
    assert all(
        0 < chunk.overlap_token_count <= 2 for chunk in result.chunks[1:]
    )
    reconstructed = []
    for chunk in result.chunks:
        tokens = TOKEN_PATTERN.findall(chunk.text)
        reconstructed.extend(tokens[chunk.overlap_token_count :])
    assert reconstructed == TOKEN_PATTERN.findall(content)


def test_chunk_ids_order_and_fingerprint_are_deterministic_on_force(
    chunking_context, monkeypatch
):
    client, _, normalization, chunking, _, _, _ = chunking_context
    monkeypatch.setattr(constants, "MAX_CHUNK_TOKENS", 5)
    monkeypatch.setattr(constants, "OVERLAP_TOKENS", 1)
    content = "one two three four five six seven eight nine ten"
    project_id, source, _ = normalize_text_source(client, normalization, content)
    first = chunking.build(project_id, source["source_id"], user())
    second = chunking.build(project_id, source["source_id"], user(), force=True)
    assert second.chunk_ids == first.chunk_ids
    assert second.chunk_set_fingerprint == first.chunk_set_fingerprint
    assert second.input_fingerprint == first.input_fingerprint
    assert [chunk.sequence for chunk in second.chunks] == list(
        range(1, len(second.chunks) + 1)
    )


def test_policy_change_invalidates_cache_and_chunk_identity(
    chunking_context, monkeypatch
):
    client, _, normalization, chunking, _, _, _ = chunking_context
    content = " ".join(f"item{index}" for index in range(30))
    project_id, source, _ = normalize_text_source(client, normalization, content)
    first = chunking.build(project_id, source["source_id"], user())
    monkeypatch.setattr(constants, "MAX_CHUNK_TOKENS", 10)
    monkeypatch.setattr(constants, "TARGET_CHUNK_TOKENS", 8)
    monkeypatch.setattr(constants, "CHUNKER_VERSION", "C2-test")
    second = chunking.build(project_id, source["source_id"], user())
    assert second.policy_fingerprint != first.policy_fingerprint
    assert second.input_fingerprint != first.input_fingerprint
    assert second.chunk_ids != first.chunk_ids


def test_pdf_pages_and_oversized_page_retain_page_provenance(
    chunking_context, monkeypatch
):
    client, extraction, normalization, chunking, _, _, _ = chunking_context
    monkeypatch.setattr(constants, "MAX_CHUNK_TOKENS", 7)
    monkeypatch.setattr(constants, "OVERLAP_TOKENS", 2)
    project_id, source = confirmed_document(
        client,
        "requirements.pdf",
        pdf_bytes(" ".join(f"first{i}" for i in range(15)), "second page"),
        "application/pdf",
    )
    extraction.extract(project_id, source["source_id"], user())
    normalization.normalize(project_id, source["source_id"], user())
    result = chunking.build(project_id, source["source_id"], user())
    pages = [chunk.source_spans[0].page_number for chunk in result.chunks]
    assert pages == sorted(pages)
    assert pages.count(1) > 1
    assert 2 in pages
    assert all(chunk.source_segment_ids for chunk in result.chunks)


def test_docx_heading_table_and_block_provenance_are_retained(chunking_context):
    client, extraction, normalization, chunking, _, _, _ = chunking_context
    project_id, source = confirmed_document(
        client,
        "requirements.docx",
        docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    extraction.extract(project_id, source["source_id"], user())
    normalization.normalize(project_id, source["source_id"], user())
    result = chunking.build(project_id, source["source_id"], user())
    assert result.chunks[0].heading_path == ["Functional Requirements"]
    assert result.chunks[0].text.startswith("Functional Requirements\n\n")
    table = next(chunk for chunk in result.chunks if chunk.structure_type == "DOCX_TABLE")
    assert "Customer\tTransfer funds" in table.text
    assert {span.block_index for span in table.source_spans} >= {3}


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("requirements.json", b'{"z":1,"a":{"value":2}}', "application/json"),
        ("requirements.yaml", b"z: 1\na:\n  value: 2\n", "application/yaml"),
    ],
)
def test_structured_normalized_content_chunks_without_raw_reparse(
    chunking_context, filename, content, content_type
):
    client, extraction, normalization, chunking, root, _, _ = chunking_context
    project_id, source = confirmed_document(client, filename, content, content_type)
    extraction.extract(project_id, source["source_id"], user())
    normalized = normalization.normalize(project_id, source["source_id"], user())
    raw = root / project_id / "inputs" / f"{source['source_id']}{source['extension']}"
    raw_before = raw.read_bytes()
    result = chunking.build(project_id, source["source_id"], user())
    assert result.chunks[0].text == normalized.normalized_text
    assert result.chunks[0].source_spans[0].structured_path == "$"
    assert raw.read_bytes() == raw_before


def test_partial_warnings_and_truncation_propagate(
    chunking_context, monkeypatch
):
    client, extraction, normalization, chunking, _, _, _ = chunking_context
    project_id, source = confirmed_document(
        client, "requirements.pdf", pdf_bytes("long content"), "application/pdf"
    )
    monkeypatch.setattr(extraction_service_module, "MAX_EXTRACTED_CHARACTERS", 4)
    extraction.extract(project_id, source["source_id"], user(), force=True)
    normalization.normalize(project_id, source["source_id"], user())
    result = chunking.build(project_id, source["source_id"], user())
    warnings = result.chunks[0].inherited_warning_codes
    assert "CONTENT_TRUNCATED" in warnings
    assert "NORMALIZED_INPUT_TRUNCATED" in warnings
    assert "NORMALIZED_INPUT_READY_WITH_WARNINGS" in warnings


def test_cache_reuse_corruption_and_normalization_change(
    chunking_context,
):
    client, _, normalization, chunking, root, _, _ = chunking_context
    project_id, source, _ = normalize_text_source(
        client, normalization, "cache remains deterministic"
    )
    first = chunking.build(project_id, source["source_id"], user())
    cached = chunking.build(project_id, source["source_id"], user())
    assert cached == first
    assert cached.created_at == first.created_at
    sidecar = root / project_id / "preparation" / f"{source['source_id']}.chunks.json"
    sidecar.write_text("{bad", encoding="utf-8")
    rebuilt = chunking.build(project_id, source["source_id"], user())
    assert rebuilt.chunk_ids == first.chunk_ids

    normalized_sidecar = (
        root
        / project_id
        / "preparation"
        / f"{source['source_id']}.normalized.json"
    )
    payload = json.loads(normalized_sidecar.read_text(encoding="utf-8"))
    payload["normalizer_version"] = "stale"
    normalized_sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Agent4NormalizationNotFoundError):
        chunking.build(project_id, source["source_id"], user())


def test_current_normalization_change_invalidates_chunk_cache(
    chunking_context, monkeypatch
):
    client, extraction, normalization, chunking, _, _, _ = chunking_context
    project_id, source = confirmed_document(
        client, "requirements.txt", b"stable evidence", "text/plain"
    )
    extraction.extract(project_id, source["source_id"], user())
    normalization.normalize(project_id, source["source_id"], user())
    first = chunking.build(project_id, source["source_id"], user())

    monkeypatch.setattr(
        extraction_service_module, "AGENT4_EXTRACTION_VERSION", "E2-test"
    )
    extraction.extract(project_id, source["source_id"], user(), force=True)
    normalization.normalize(project_id, source["source_id"], user(), force=True)
    second = chunking.build(project_id, source["source_id"], user())

    assert second.normalized_artifact_id != first.normalized_artifact_id
    assert second.normalization_fingerprint != first.normalization_fingerprint
    assert second.input_fingerprint != first.input_fingerprint
    assert second.chunk_ids != first.chunk_ids


def test_unconfirmed_source_cannot_be_chunked(chunking_context):
    client, _, _, chunking, root, _, _ = chunking_context
    project_id = create_project(client)
    source = add_text(client, project_id)
    with pytest.raises(Agent4ExtractionGateError):
        chunking.build(project_id, source["source_id"], user())
    assert not (
        root / project_id / "preparation" / f"{source['source_id']}.chunks.json"
    ).exists()


def test_atomic_failure_cleans_partial(chunking_context, monkeypatch):
    client, _, normalization, chunking, root, _, _ = chunking_context
    project_id, source, _ = normalize_text_source(client, normalization, "atomic")
    original_replace = Path.replace

    def fail_replace(path, target):
        if str(path).endswith(".chunks.json.part"):
            raise OSError("injected")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(Agent4ChunkStorageError):
        chunking.build(project_id, source["source_id"], user())
    preparation = root / project_id / "preparation"
    assert not list(preparation.glob("*.chunks.json.part"))
    assert not list(preparation.glob("*.chunks.json"))


def test_image_and_failed_artifact_produce_no_fake_chunk_sidecar(chunking_context):
    client, extraction, normalization, chunking, root, _, _ = chunking_context
    project_id = create_project(client)
    add_text(client, project_id)
    response = client.post(
        f"{source_url(project_id)}/files",
        data={
            "artifact_type": "WIREFRAMES",
            "source_type": "IMAGE",
            "normally_supplied_by": "AGENT_2",
        },
        files={"file": ("wireframe.png", b"\x89PNG\r\n\x1a\nminimal", "image/png")},
    )
    image = response.json()["data"]
    confirm(client, project_id)
    normalization.normalize(project_id, image["source_id"], user())
    with pytest.raises(Agent4ChunkingNotApplicableError):
        chunking.build(project_id, image["source_id"], user())
    image_chunks = (
        root / project_id / "preparation" / f"{image['source_id']}.chunks.json"
    )
    assert not image_chunks.exists()

    project_id, source = confirmed_document(
        client, "broken.pdf", b"%PDF-not-valid", "application/pdf"
    )
    extraction.extract(project_id, source["source_id"], user())
    normalization.normalize(project_id, source["source_id"], user())
    with pytest.raises(Agent4ChunkingNotApplicableError):
        chunking.build(project_id, source["source_id"], user())
    failed_chunks = (
        root / project_id / "preparation" / f"{source['source_id']}.chunks.json"
    )
    assert not failed_chunks.exists()


def test_chunking_preserves_all_upstream_state_and_workflow(chunking_context):
    client, extraction, normalization, chunking, root, _, runs = chunking_context
    project_id, source = confirmed_document(
        client, "requirements.pdf", pdf_bytes("Approved"), "application/pdf"
    )
    extraction.extract(project_id, source["source_id"], user())
    normalization.normalize(project_id, source["source_id"], user())
    paths = [
        root / project_id / "workflow.json",
        root / project_id / "inputs" / f"{source['source_id']}.pdf",
        root / project_id / "inputs" / f"{source['source_id']}.source.json",
        root / project_id / "preparation" / f"{source['source_id']}.extraction.json",
        root / project_id / "preparation" / f"{source['source_id']}.normalized.json",
    ]
    before = {path: path.read_bytes() for path in paths}
    result = chunking.build(project_id, source["source_id"], user())
    assert all(path.read_bytes() == value for path, value in before.items())
    workflow = json.loads(paths[0].read_text(encoding="utf-8"))
    assert workflow["pipeline_status"] == "RUNNING"
    assert workflow["current_node_id"] == "INPUT_PREPARATION"
    assert [node["status"] for node in workflow["nodes"]] == [
        "COMPLETED",
        "NOT_STARTED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
    ]
    assert workflow["n1_confirmation"] is not None
    assert workflow["selected_outputs"] == ["UNIT_TEST_CASES"]
    assert runs.documents == {}
    serialized = result.model_dump_json().lower()
    assert "classification" not in serialized
    assert "testing_fact" not in serialized
    assert "filesystem_path" not in serialized
    assert "storage_path" not in serialized
    assert str(root).lower().replace("\\", "\\\\") not in serialized


def test_no_agent4_chunking_route_or_frontend_execution_contract():
    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path") and "testing-validation" in route.path
    }
    assert not any("chunk" in path or "prepare" in path for path in paths)
