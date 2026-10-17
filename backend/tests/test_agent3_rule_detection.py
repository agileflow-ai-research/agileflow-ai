import json

import pytest

from app.main import app
from app.modules.agents.implementation.extraction.schemas import DocumentType
from app.modules.agents.implementation.semantic_discovery import constants
from app.modules.agents.implementation.semantic_discovery.rule_detector import (
    detect_chunk,
    strength_for_score,
)
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
    ChunkContext,
    ChunkProvenance,
    RuleStrength,
    SemanticChunk,
)
from app.modules.agents.implementation.semantic_discovery import service as service_module
from test_agent3_document_extraction import (
    PNG,
    create_project,
    extraction_context,
    extract,
    upload,
    upload_dir,
)
from test_agent3_semantic_chunking import build as build_chunks


def chunk(text, *, heading=None, path=None):
    import hashlib
    normalized = text.strip()
    return SemanticChunk(
        chunk_id="CHK-0123456789ABCDEF0123",
        chunk_index=0,
        text=normalized,
        text_hash=hashlib.sha256(normalized.encode()).hexdigest(),
        token_count=max(1, len(normalized.split())),
        character_count=len(normalized),
        context=ChunkContext(
            heading_path=[heading] if heading else [],
            section_title=heading,
            heading_depth=1 if heading else 0,
            structure_type="STRUCTURED" if path else "PARAGRAPH",
        ),
        provenance=ChunkProvenance(
            upload_id="A3UP-0123456789abcdef0123456789abcdef",
            agent_project_id="AGP-003",
            original_filename="spec.txt",
            source_sha256="a" * 64,
            document_type=DocumentType.JSON if path else DocumentType.TXT,
            structured_path=path,
        ),
    )


def labels(text, **kwargs):
    return {prediction.label: prediction for prediction in detect_chunk(chunk(text, **kwargs)).predictions}


@pytest.mark.parametrize(("text", "expected"), [
    ("FR-001 Users can book.", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS),
    ("The system shall create a booking.", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS),
    ("The user shall cancel a booking.", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS),
    ("NFR001 Availability requirement.", ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS),
    ("The response time shall be below 2 seconds.", ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS),
    ("As a guest, I want to reserve a room so that I can plan my trip.", ArtifactDetectionLabel.USER_STORIES),
    ("AC-001 A booking is confirmed.", ArtifactDetectionLabel.ACCEPTANCE_CRITERIA),
    ("Given an open slot When I book Then the booking is confirmed", ArtifactDetectionLabel.ACCEPTANCE_CRITERIA),
    ("POST /api/bookings", ArtifactDetectionLabel.API_SPECIFICATION),
    ("HTTP 201 and HTTP 409", ArtifactDetectionLabel.API_SPECIFICATION),
    ("CREATE TABLE bookings (id BIGINT PRIMARY KEY)", ArtifactDetectionLabel.DATABASE_SCHEMA),
    ("PRIMARY KEY id FOREIGN KEY user_id REFERENCES users", ArtifactDetectionLabel.DATABASE_SCHEMA),
    ("Client -> API -> Database", ArtifactDetectionLabel.SYSTEM_ARCHITECTURE),
    ("presentation layer and service layer", ArtifactDetectionLabel.SYSTEM_ARCHITECTURE),
    ("Login -> Dashboard -> Booking Form", ArtifactDetectionLabel.UI_FLOW),
    ("Frontend: React\nBackend: FastAPI\nDatabase: PostgreSQL", ArtifactDetectionLabel.TECHNOLOGY_STACK),
    ("The project must use Python 3.12.", ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS),
    ("Do not use MongoDB.", ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS),
    ("TASK-001 Create booking controller", ArtifactDetectionLabel.IMPLEMENTATION_TASKS),
    ("- Create booking controller\n- Implement slot service", ArtifactDetectionLabel.IMPLEMENTATION_TASKS),
    ("TC-001 Verify booking creation", ArtifactDetectionLabel.TEST_CASES),
])
def test_expected_rules(text, expected):
    assert expected in labels(text)


def test_heading_and_structured_path_rules():
    assert ArtifactDetectionLabel.SYSTEM_ARCHITECTURE in labels("Components", heading="System Architecture")
    assert ArtifactDetectionLabel.UI_FLOW in labels("Screens", heading="UI Flow")
    assert ArtifactDetectionLabel.DATABASE_SCHEMA in labels('{"id":"uuid"}', path="$.tables.bookings")
    assert ArtifactDetectionLabel.TECHNOLOGY_STACK in labels('{"frontend":"React"}', path="$.technology_stack.frontend")
    assert ArtifactDetectionLabel.TEST_CASES in labels('[{"name":"create"}]', path="$.api_tests[0:5]")


def test_false_positive_protection_and_other_context():
    assert set(labels("The application should be secure.")) == {ArtifactDetectionLabel.OTHER_CONTEXT}
    assert ArtifactDetectionLabel.USER_STORIES not in labels("As a manager, I review reports.")
    assert ArtifactDetectionLabel.API_SPECIFICATION not in labels("See https://example.com/docs")
    negated = labels("Database: Do not use MongoDB")
    assert ArtifactDetectionLabel.TECHNOLOGY_STACK not in negated
    assert ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS in negated
    unavailable = labels("The API documentation is not available.")
    assert ArtifactDetectionLabel.API_SPECIFICATION not in unavailable


def test_multi_label_limit_scores_strength_and_evidence_are_deterministic(monkeypatch):
    text = (
        "AC-001 Given a request When POST /api/bookings returns HTTP 201 "
        "Then the booking exists. CREATE TABLE bookings. TASK-001. TC-001."
    )
    first = detect_chunk(chunk(text))
    second = detect_chunk(chunk(text))
    assert first == second
    assert {p.label for p in first.predictions} >= {
        ArtifactDetectionLabel.API_SPECIFICATION,
        ArtifactDetectionLabel.ACCEPTANCE_CRITERIA,
    }
    assert len(first.predictions) == constants.MAX_LABELS_PER_CHUNK
    assert all(prediction.evidence for prediction in first.predictions)
    serialized = json.dumps(first.model_dump(mode="json")).lower()
    assert "file_path" not in serialized
    assert "agileflow-ai" not in serialized
    assert strength_for_score(.80) is RuleStrength.STRONG
    assert strength_for_score(.55) is RuleStrength.MODERATE
    assert strength_for_score(.35) is RuleStrength.WEAK


def prepare(client, filename="rules.txt", content=None):
    project = create_project(client)
    source = content or b"POST /api/bookings\n\nGiven a request When submitted Then HTTP 201 is returned."
    metadata = upload(client, project["agent_project_id"], filename, source)
    assert extract(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    assert build_chunks(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    return project, metadata


def run_detector(client, project_id, upload_id, *, force=False):
    return client.post(
        f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/rule-detections",
        params={"force": str(force).lower()},
    )


def get_detector(client, project_id, upload_id):
    return client.get(
        f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/rule-detections"
    )


def test_api_is_read_only_cache_hit_and_metrics(extraction_context, monkeypatch):
    authentication, _, _ = extraction_context
    client = authentication.client()
    project, metadata = prepare(client)
    assert get_detector(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    first = run_detector(client, project["agent_project_id"], metadata["upload_id"])
    assert first.status_code == 200
    result = first.json()["data"]
    assert result["rule_detector_version"] == "1"
    assert result["score_semantics"] == "HEURISTIC_NOT_PROBABILITY"
    assert result["metrics"]["chunk_count"] == len(result["detections"])
    assert result["metrics"]["prediction_count"] >= 2
    assert "accuracy" not in result["metrics"]

    def should_not_run(_):
        raise AssertionError("detector reran")

    monkeypatch.setattr(service_module, "detect_chunk", should_not_run)
    cached = run_detector(client, project["agent_project_id"], metadata["upload_id"])
    assert cached.status_code == 200
    assert cached.json()["data"] == result


@pytest.mark.parametrize("change", ["text_hash", "version", "malformed"])
def test_invalid_detection_cache_rebuilds(extraction_context, monkeypatch, change):
    authentication, _, root = extraction_context
    client = authentication.client()
    project, metadata = prepare(client)
    expected = run_detector(client, project["agent_project_id"], metadata["upload_id"]).json()["data"]
    sidecar = upload_dir(root, project["agent_project_id"]) / f'{metadata["upload_id"]}.rule-detections.json'
    if change == "malformed":
        sidecar.write_text("not-json", encoding="utf-8")
    else:
        cached = json.loads(sidecar.read_text(encoding="utf-8"))
        if change == "text_hash":
            cached["detections"][0]["text_hash"] = "0" * 64
        else:
            cached["rule_detector_version"] = "999"
        sidecar.write_text(json.dumps(cached), encoding="utf-8")
    assert get_detector(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    rebuilt = run_detector(client, project["agent_project_id"], metadata["upload_id"])
    assert rebuilt.status_code == 200
    assert rebuilt.json()["data"]["detections"] == expected["detections"]


def test_security_missing_chunks_image_archive_foreign_and_deletion(extraction_context):
    authentication, _, root = extraction_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project, metadata = prepare(owner)
    assert run_detector(foreign, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    assert run_detector(owner, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    wrong = create_project(owner, "DESIGN_PLANNING")
    assert run_detector(owner, wrong["agent_project_id"], metadata["upload_id"]).status_code == 422
    directory = upload_dir(root, project["agent_project_id"])
    sidecar = directory / f'{metadata["upload_id"]}.rule-detections.json'
    assert sidecar.exists()
    owner.patch(f'/api/v1/agent-projects/{project["agent_project_id"]}', json={"status": "ARCHIVED"})
    assert run_detector(owner, project["agent_project_id"], metadata["upload_id"]).status_code == 409

    active = create_project(owner)
    missing = upload(owner, active["agent_project_id"], "missing.txt", b"FR-001")
    extract(owner, active["agent_project_id"], missing["upload_id"])
    assert run_detector(owner, active["agent_project_id"], missing["upload_id"]).status_code == 409
    image = upload(owner, active["agent_project_id"], "wire.png", PNG, "IMAGE")
    assert run_detector(owner, active["agent_project_id"], image["upload_id"]).status_code == 422

    owner.patch(f'/api/v1/agent-projects/{project["agent_project_id"]}', json={"status": "ACTIVE"})
    assert owner.delete(f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}').status_code == 200
    assert not sidecar.exists()


def test_rule_detection_openapi_routes_only():
    paths = app.openapi()["paths"]
    route = "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/rule-detections"
    assert set(paths[route]) == {"get", "post"}
    forbidden = ("deberta", "model-classification", "semantic-extraction", "agent-run", "code-generation", "image-analysis")
    assert not any(any(term in path for term in forbidden) for path in paths if path.startswith("/api/v1/agents/implementation"))
