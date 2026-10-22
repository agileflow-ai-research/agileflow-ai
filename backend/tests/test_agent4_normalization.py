import hashlib
import json
from pathlib import Path

import pytest

from app.main import app
from app.modules.agents.testing_validation.preparation.extraction import (
    service as extraction_service_module,
)
from app.modules.agents.testing_validation.preparation.extraction.service import (
    Agent4ExtractionGateError,
    Agent4ExtractionNotFoundError,
)
from app.modules.agents.testing_validation.preparation.normalization import constants
from app.modules.agents.testing_validation.preparation.normalization.schemas import (
    NormalizationStatus,
)
from app.modules.agents.testing_validation.preparation.normalization.service import (
    Agent4NormalizationService,
)
from app.modules.agents.testing_validation.preparation.normalization.storage import (
    Agent4NormalizationStorage,
    Agent4NormalizationStorageError,
)
from app.modules.agents.testing_validation.sources.storage import (
    Agent4SourceNotFoundError,
)
from app.modules.agents.testing_validation.workflow.service import (
    Agent4WorkflowStageError,
)
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
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
from test_standalone_foundation import user


@pytest.fixture
def normalization_context(extraction_context):
    client, extraction, root, projects, runs = extraction_context
    normalizer = Agent4NormalizationService(
        extraction, Agent4NormalizationStorage(root)
    )
    return client, extraction, normalizer, root, projects, runs


def test_confirmed_text_preserves_exact_content_and_provenance(
    normalization_context,
):
    client, _, normalizer, root, _, _ = normalization_context
    project_id = create_project(client)
    source = add_text(client, project_id)
    confirm(client, project_id)
    source_sidecar = (
        root / project_id / "inputs" / f"{source['source_id']}.source.json"
    )
    source_before = source_sidecar.read_bytes()

    artifact = normalizer.normalize(project_id, source["source_id"], user())

    assert artifact.normalization_status is NormalizationStatus.READY
    assert artifact.textual_context_usable is True
    assert artifact.normalized_text == source["text_content"]
    assert artifact.source_evidence_sha256 == hashlib.sha256(
        source["text_content"].encode("utf-8")
    ).hexdigest()
    assert artifact.artifact_type.value == "FUNCTIONAL_REQUIREMENTS"
    assert artifact.source_type.value == "TEXT"
    assert artifact.normally_supplied_by.value == "AGENT_1"
    assert artifact.supplied_via.value == "STANDALONE_MANUAL_INPUT"
    assert artifact.original_filename is None
    assert artifact.source_sha256 is None
    assert len(artifact.normalized_segments) == 1
    assert artifact.normalized_segments[0].text == source["text_content"]
    extraction_path = (
        root
        / project_id
        / "preparation"
        / f"{source['source_id']}.extraction.json"
    )
    assert not extraction_path.exists()
    assert source_sidecar.read_bytes() == source_before


def test_text_internal_formatting_is_not_normalized(normalization_context):
    client, _, normalizer, _, _, _ = normalization_context
    project_id = create_project(client)
    content = "Heading\n\n  indented  value\nLine with  two spaces"
    response = client.post(
        f"{source_url(project_id)}/text",
        json={
            "artifact_type": "SRS",
            "normally_supplied_by": "AGENT_1",
            "content": f"  {content}  ",
        },
    )
    source = response.json()["data"]
    confirm(client, project_id)
    artifact = normalizer.normalize(project_id, source["source_id"], user())
    assert artifact.normalized_text == content


def test_pdf_success_and_page_segments_preserve_order(normalization_context):
    client, extraction, normalizer, _, _, _ = normalization_context
    project_id, source = confirmed_document(
        client, "requirements.pdf", pdf_bytes("First", "Second"), "application/pdf"
    )
    extracted = extraction.extract(project_id, source["source_id"], user())
    artifact = normalizer.normalize(project_id, source["source_id"], user())
    assert artifact.normalization_status is NormalizationStatus.READY
    assert artifact.normalized_text == extracted.extracted_text
    assert [segment.page_number for segment in artifact.normalized_segments] == [1, 2]
    assert [segment.text for segment in artifact.normalized_segments] == [
        "First",
        "Second",
    ]
    assert artifact.extraction.extraction_id == extracted.extraction_id


def test_partial_pdf_propagates_warning_and_truncation(normalization_context, monkeypatch):
    client, extraction, normalizer, _, _, _ = normalization_context
    project_id, source = confirmed_document(
        client, "requirements.pdf", pdf_bytes("long content"), "application/pdf"
    )
    monkeypatch.setattr(extraction_service_module, "MAX_EXTRACTED_CHARACTERS", 4)
    extracted = extraction.extract(project_id, source["source_id"], user(), force=True)
    artifact = normalizer.normalize(project_id, source["source_id"], user())
    assert artifact.normalization_status is NormalizationStatus.READY_WITH_WARNINGS
    assert artifact.textual_context_usable is True
    assert artifact.truncated is True
    assert [warning.code for warning in artifact.extraction_warnings] == [
        "CONTENT_TRUNCATED"
    ]
    assert artifact.normalized_text == "long"


def test_docx_block_segments_preserve_structure(normalization_context):
    client, extraction, normalizer, _, _, _ = normalization_context
    project_id, source = confirmed_document(
        client,
        "requirements.docx",
        docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    extraction.extract(project_id, source["source_id"], user())
    artifact = normalizer.normalize(project_id, source["source_id"], user())
    assert [segment.kind.value for segment in artifact.normalized_segments] == [
        "DOCX_HEADING",
        "DOCX_PARAGRAPH",
        "DOCX_TABLE",
    ]
    assert [segment.block_index for segment in artifact.normalized_segments] == [
        1,
        2,
        3,
    ]
    assert artifact.normalized_segments[0].heading_level == 1
    assert artifact.normalized_segments[2].table_rows[1] == [
        "Customer",
        "Transfer funds",
    ]


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "kind"),
    [
        ("requirements.txt", b"Line one\nLine two", "text/plain", "DOCUMENT_TEXT"),
        ("requirements.md", b"# Title\n\n- item", "text/markdown", "DOCUMENT_TEXT"),
        ("requirements.json", b'{"z":1,"a":2}', "application/json", "STRUCTURED_DOCUMENT"),
        ("requirements.yaml", b"z: 1\na: 2\n", "application/yaml", "STRUCTURED_DOCUMENT"),
        ("requirements.yml", b"z: 1\na: 2\n", "application/yaml", "STRUCTURED_DOCUMENT"),
    ],
)
def test_document_formats_converge_on_normalized_text(
    normalization_context, filename, content, content_type, kind
):
    client, extraction, normalizer, _, _, _ = normalization_context
    project_id, source = confirmed_document(client, filename, content, content_type)
    extracted = extraction.extract(project_id, source["source_id"], user())
    artifact = normalizer.normalize(project_id, source["source_id"], user())
    assert artifact.normalized_text == extracted.extracted_text
    assert artifact.normalized_segments[0].kind.value == kind
    if filename.endswith((".json", ".yaml", ".yml")):
        assert artifact.structured_content == {"z": 1, "a": 2}


def test_failed_extraction_produces_unusable_failed_artifact(normalization_context):
    client, extraction, normalizer, _, _, _ = normalization_context
    project_id, source = confirmed_document(
        client, "broken.pdf", b"%PDF-not-valid", "application/pdf"
    )
    extracted = extraction.extract(project_id, source["source_id"], user())
    assert extracted.status.value == "FAILED"
    artifact = normalizer.normalize(project_id, source["source_id"], user())
    assert artifact.normalization_status is NormalizationStatus.FAILED
    assert artifact.textual_context_usable is False
    assert artifact.normalized_text is None
    assert artifact.normalized_segments == []
    assert artifact.failure.code.value == "DOCUMENT_EXTRACTION_FAILED"


def test_image_produces_metadata_only_pending_artifact(normalization_context):
    client, _, normalizer, root, _, _ = normalization_context
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
    artifact = normalizer.normalize(project_id, image["source_id"], user())
    assert artifact.normalization_status is NormalizationStatus.PENDING_ANALYSIS
    assert artifact.textual_context_usable is False
    assert artifact.normalized_text is None
    assert artifact.structured_content is None
    assert artifact.normalized_segments == []
    assert artifact.source_sha256 == image["sha256"]
    assert artifact.original_filename == "wireframe.png"
    extraction_path = (
        root
        / project_id
        / "preparation"
        / f"{image['source_id']}.extraction.json"
    )
    assert not extraction_path.exists()


def test_segment_and_artifact_identities_are_deterministic_on_force(
    normalization_context,
):
    client, extraction, normalizer, _, _, _ = normalization_context
    project_id, source = confirmed_document(
        client, "requirements.pdf", pdf_bytes("One", "Two"), "application/pdf"
    )
    extraction.extract(project_id, source["source_id"], user())
    first = normalizer.normalize(project_id, source["source_id"], user())
    second = normalizer.normalize(
        project_id, source["source_id"], user(), force=True
    )
    assert second.normalized_artifact_id == first.normalized_artifact_id
    assert second.input_fingerprint == first.input_fingerprint
    assert [item.segment_id for item in second.normalized_segments] == [
        item.segment_id for item in first.normalized_segments
    ]
    assert "chunk" not in second.model_dump_json().lower()
    assert "token" not in second.model_dump_json().lower()


def test_cache_reuse_and_version_or_extraction_change_rebuilds(
    normalization_context, monkeypatch
):
    client, extraction, normalizer, root, _, _ = normalization_context
    project_id, source = confirmed_document(
        client, "requirements.txt", b"cached", "text/plain"
    )
    extraction.extract(project_id, source["source_id"], user())
    first = normalizer.normalize(project_id, source["source_id"], user())
    cached = normalizer.normalize(project_id, source["source_id"], user())
    assert cached == first
    assert cached.normalized_at == first.normalized_at

    normalized_sidecar = (
        root
        / project_id
        / "preparation"
        / f"{source['source_id']}.normalized.json"
    )
    payload = json.loads(normalized_sidecar.read_text(encoding="utf-8"))
    payload["input_fingerprint"] = "0" * 64
    normalized_sidecar.write_text(json.dumps(payload), encoding="utf-8")
    repaired = normalizer.normalize(project_id, source["source_id"], user())
    assert repaired.input_fingerprint == first.input_fingerprint
    assert json.loads(normalized_sidecar.read_text(encoding="utf-8"))[
        "input_fingerprint"
    ] == first.input_fingerprint

    rebuilt_extraction = extraction.extract(
        project_id, source["source_id"], user(), force=True
    )
    second = normalizer.normalize(project_id, source["source_id"], user())
    assert second.extraction.extraction_id == rebuilt_extraction.extraction_id
    assert second.normalized_artifact_id != first.normalized_artifact_id

    monkeypatch.setattr(constants, "NORMALIZER_VERSION", "N2-test")
    third = normalizer.normalize(project_id, source["source_id"], user())
    assert third.normalized_artifact_id != second.normalized_artifact_id
    assert third.normalizer_version == "N2-test"


def test_stale_extraction_is_not_normalized(normalization_context):
    client, extraction, normalizer, root, _, _ = normalization_context
    project_id, source = confirmed_document(
        client, "requirements.txt", b"stale", "text/plain"
    )
    extraction.extract(project_id, source["source_id"], user())
    sidecar = root / project_id / "preparation" / f"{source['source_id']}.extraction.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["extractor_version"] = "stale"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Agent4ExtractionNotFoundError):
        normalizer.normalize(project_id, source["source_id"], user())


def test_atomic_persistence_and_part_cleanup(normalization_context, monkeypatch):
    client, _, normalizer, root, _, _ = normalization_context
    project_id = create_project(client)
    source = add_text(client, project_id)
    confirm(client, project_id)
    original_replace = Path.replace

    def fail_replace(path, target):
        if str(path).endswith(".normalized.json.part"):
            raise OSError("injected")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(Agent4NormalizationStorageError):
        normalizer.normalize(project_id, source["source_id"], user())
    preparation = root / project_id / "preparation"
    assert not list(preparation.glob("*.normalized.json.part"))
    assert not list(preparation.glob("*.normalized.json"))


def test_confirmation_security_boundaries_are_reused(normalization_context):
    client, _, normalizer, _, projects, _ = normalization_context
    project_id = create_project(client)
    source = add_text(client, project_id)
    with pytest.raises(Agent4ExtractionGateError):
        normalizer.normalize(project_id, source["source_id"], user())
    confirm(client, project_id)
    with pytest.raises(Agent4SourceNotFoundError):
        normalizer.normalize(project_id, "A4SRC-" + "f" * 32, user())
    with pytest.raises(AgentProjectNotFoundError):
        normalizer.normalize(project_id, source["source_id"], user("USR-002"))
    projects.documents[project_id]["agent_stage"] = "VALIDATION"
    with pytest.raises(Agent4WorkflowStageError):
        normalizer.normalize(project_id, source["source_id"], user())
    projects.documents[project_id]["agent_stage"] = None
    with pytest.raises(Agent4WorkflowStageError):
        normalizer.normalize(project_id, source["source_id"], user())
    projects.documents[project_id]["agent_stage"] = "TEST_GENERATION"
    projects.documents[project_id]["status"] = "ARCHIVED"
    with pytest.raises(ArchivedAgentProjectError):
        normalizer.normalize(project_id, source["source_id"], user())


def test_n1_source_digest_mutation_is_rejected(normalization_context):
    client, _, normalizer, root, _, _ = normalization_context
    project_id = create_project(client)
    source = add_text(client, project_id)
    confirm(client, project_id)
    sidecar = root / project_id / "inputs" / f"{source['source_id']}.source.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["label"] = "mutated after confirmation"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Agent4ExtractionGateError, match="confirmed setup"):
        normalizer.normalize(project_id, source["source_id"], user())


def test_normalization_preserves_every_upstream_sidecar_and_workflow_state(
    normalization_context,
):
    client, extraction, normalizer, root, _, runs = normalization_context
    project_id, source = confirmed_document(
        client, "requirements.pdf", pdf_bytes("Approved"), "application/pdf"
    )
    extraction.extract(project_id, source["source_id"], user())
    raw = root / project_id / "inputs" / f"{source['source_id']}.pdf"
    source_sidecar = raw.with_name(f"{source['source_id']}.source.json")
    workflow = root / project_id / "workflow.json"
    extraction_sidecar = (
        root
        / project_id
        / "preparation"
        / f"{source['source_id']}.extraction.json"
    )
    before = {
        path: path.read_bytes()
        for path in (raw, source_sidecar, workflow, extraction_sidecar)
    }
    artifact = normalizer.normalize(project_id, source["source_id"], user())
    assert all(path.read_bytes() == value for path, value in before.items())
    state = json.loads(workflow.read_text(encoding="utf-8"))
    assert state["pipeline_status"] == "RUNNING"
    assert state["current_node_id"] == "INPUT_PREPARATION"
    assert [node["status"] for node in state["nodes"]] == [
        "COMPLETED",
        "NOT_STARTED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
    ]
    assert state["n1_confirmation"] is not None
    assert state["selected_outputs"] == ["UNIT_TEST_CASES"]
    assert runs.documents == {}
    assert not list((root / project_id).rglob("*chunk*"))
    assert not list((root / project_id).rglob("*classification*"))
    assert "path" not in artifact.model_dump_json().lower()


def test_agent4_router_has_no_normalization_execution_route():
    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path") and "testing-validation" in route.path
    }
    assert not any("normalize" in path or "prepare" in path for path in paths)
