import hashlib
import json

import pytest
from pydantic import ValidationError

from app.main import app
from app.modules.agents.implementation.semantic_discovery.canonical import constants
from app.modules.agents.implementation.semantic_discovery.canonical.extractors import (
    api, architecture, database, other, requirements, tasks, technology, tests, ui_flow,
)
from app.modules.agents.implementation.semantic_discovery.canonical.schemas import (
    CanonicalSourceRef, CanonicalStatus, RequirementItem,
)
from test_agent3_document_extraction import create_project, extraction_context, upload_dir
from test_agent3_human_review import accept, prepare_hybrid, put, state, zero_context


def source(path=None):
    return CanonicalSourceRef(
        upload_id="A3UP-0123456789abcdef0123456789abcdef",
        chunk_id="CHK-0123456789ABCDEF0123",
        text_hash="a" * 64,
        original_filename="spec.md",
        line_start=1,
        line_end=3,
        structured_path=path,
    )


def canonical_url(project_id, upload_id):
    return f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/canonical-artifacts"


def test_functional_and_non_functional_requirement_extraction():
    ref = source()
    functional = requirements.functional(
        "FR001: The system shall display slots.\n1. The user shall cancel a booking.", ref
    )
    assert functional.status is CanonicalStatus.COMPLETE
    assert [(item.id, item.statement) for item in functional.data.requirements] == [
        ("FR-001", "The system shall display slots."),
        (None, "The user shall cancel a booking."),
    ]
    nfr = requirements.non_functional(
        "NFR-2: Response time shall be below 2 seconds.", ref
    )
    item = nfr.data.requirements[0]
    assert item.id == "NFR-002"
    assert item.category == "PERFORMANCE"
    assert item.measurable_target == "below 2 seconds"


def test_user_story_and_acceptance_criteria_complete_and_partial():
    ref = source()
    story = requirements.user_stories(
        "US-1: As a guest, I want to reserve a room so that I can plan my trip.", ref
    )
    assert story.status is CanonicalStatus.COMPLETE
    assert story.data.stories[0].model_dump(exclude={"source_refs"}) == {
        "id": "US-001", "role": "guest", "goal": "to reserve a room",
        "benefit": "I can plan my trip", "raw_statement": "As a guest, I want to reserve a room so that I can plan my trip.",
    }
    criterion = requirements.acceptance(
        "AC-001: Given an open slot When I book Then HTTP 201 is returned", ref
    )
    assert criterion.status is CanonicalStatus.COMPLETE
    assert criterion.data.criteria[0].then == "HTTP 201 is returned"
    partial = requirements.user_stories("As a guest, I want to reserve a room", ref)
    assert partial.status is CanonicalStatus.PARTIAL
    assert partial.unresolved_items[0].reason == "USER_STORY_BENEFIT_NOT_EXPLICIT"


def test_api_method_path_status_and_partial_extraction():
    ref = source()
    complete = api.extract(
        "POST /api/bookings\nRequest fields: slot_id, user_id\nHTTP 201", ref
    )
    endpoint = complete.data.endpoints[0]
    assert complete.status is CanonicalStatus.COMPLETE
    assert (endpoint.method, endpoint.path) == ("POST", "/api/bookings")
    assert endpoint.request_fields == ["slot_id", "user_id"]
    assert endpoint.response_statuses == [201]
    partial = api.extract("POST /api/bookings accepts booking data.", ref)
    assert partial.status is CanonicalStatus.PARTIAL
    assert {item.reason for item in partial.unresolved_items} == {
        "API_REQUEST_STRUCTURE_NOT_EXPLICIT", "API_RESPONSE_STATUS_NOT_EXPLICIT",
    }


def test_sql_structured_and_markdown_database_extraction():
    ref = source()
    sql = database.extract(
        "CREATE TABLE bookings (id BIGINT PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id));",
        ref,
    )
    assert sql.status is CanonicalStatus.COMPLETE
    entity = sql.data.entities[0]
    assert entity.name == "bookings"
    assert entity.fields[0].primary_key is True
    assert entity.fields[1].foreign_key == "users(id)"
    structured = database.extract(json.dumps({
        "tables": {"users": {"fields": {"id": {"type": "UUID", "primary_key": True}}}}
    }), source("$.tables"))
    assert structured.data.entities[0].fields[0].type == "UUID"
    yaml_result = database.extract(
        "tables:\n  audit_log:\n    fields:\n      id:\n        type: BIGINT", source("$.tables")
    )
    assert yaml_result.data.entities[0].name == "audit_log"
    markdown = database.extract(
        "Table: slots\n| Field | Type | Key |\n|---|---|---|\n| id | UUID | Primary |", ref
    )
    assert markdown.data.entities[0].fields[0].primary_key is True


def test_architecture_ui_flow_and_technology_declarations():
    ref = source()
    architecture_result = architecture.extract("Client -> API -> Database", ref)
    assert architecture_result.status is CanonicalStatus.COMPLETE
    assert len(architecture_result.data.components) == 3
    assert architecture_result.data.relationships[0].model_dump(by_alias=True)["from"] == "Client"
    flow = ui_flow.extract("Home -> Slots -> Booking Form -> Success", ref)
    assert [step.screen_or_action for step in flow.data.flows[0].steps] == [
        "Home", "Slots", "Booking Form", "Success",
    ]
    stack = technology.extract(
        "Frontend: React\nStyling: Tailwind CSS\nBackend: FastAPI\nDatabase: PostgreSQL\nLanguages: Python, JavaScript\nAPI Style: REST",
        ref,
    )
    assert stack.data.frontend == ["React"]
    assert stack.data.database == ["PostgreSQL"]
    assert stack.data.api_styles == ["REST"]
    yaml_stack = technology.extract("frontend:\n  - Vue\nbackend:\n  - FastAPI", ref)
    assert yaml_stack.data.frontend == ["Vue"]


def test_constraints_tasks_and_test_cases():
    ref = source()
    constraint = requirements.constraints("TC-01: The project must not use MongoDB.", ref)
    assert constraint.data.constraints[0].constraint_type == "PROHIBITION"
    task_result = tasks.extract("TASK-1: Create booking controller\n- Implement slot service", ref)
    assert [item.title for item in task_result.data.tasks] == [
        "Create booking controller", "Implement slot service",
    ]
    test_result = tests.extract(
        "API-T-001: Create booking\nGiven an open slot When POST is sent Then HTTP 201 is returned",
        ref,
    )
    assert test_result.status is CanonicalStatus.COMPLETE
    assert test_result.data.test_cases[0].expected_result == "HTTP 201 is returned"
    structured_test = tests.extract(
        "tests:\n  - id: TC-002\n    steps: [submit]\n    expected: booking created", ref
    )
    assert structured_test.data.test_cases[0].id == "TC-002"


def test_other_context_and_unresolved_are_explicit():
    ref = source()
    context = other.extract("Company background and stakeholder notes.", ref)
    assert context.data.usable_for_generation is False
    assert context.status is CanonicalStatus.COMPLETE
    unresolved = database.extract("The system stores customer information.", ref)
    assert unresolved.status is CanonicalStatus.UNRESOLVED
    assert unresolved.unresolved_items[0].reason == "NO_EXPLICIT_DATABASE_STRUCTURE"
    with pytest.raises(ValidationError):
        RequirementItem(id="FR-001", statement="Required", source_refs=[])


def test_conservative_deduplication():
    ref = source()
    result = api.extract("POST /api/bookings\nPOST /api/bookings", ref)
    assert len(result.data.endpoints) == 1
    requirements_result = requirements.functional(
        "FR-001: The system shall book.\nFR-001: The system shall book.\nFR-002: The system shall book.", ref
    )
    assert len(requirements_result.data.requirements) == 2


def _complete_review(client, project, metadata):
    initial = state(client, project, metadata)
    decisions = [accept(candidate["label"])
                 for candidate in initial["review_queue"][0]["hybrid"]["candidates"]]
    response = put(
        client, project, metadata,
        initial["review_queue"][0]["chunk"]["chunk_id"],
        initial["review"]["review_fingerprint"], decisions,
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_api_requires_complete_human_review_and_get_is_read_only(zero_context):
    authentication, _, _, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    url = canonical_url(project["agent_project_id"], metadata["upload_id"])
    assert client.get(url).status_code == 409
    missing = client.post(url)
    assert missing.status_code == 409
    assert missing.json()["errors"][0]["message"] == "HUMAN_VERIFICATION_REQUIRED"
    _complete_review(client, project, metadata)
    assert client.get(url).status_code == 404


def test_canonical_api_sidecar_cache_ids_provenance_and_machine_immutability(zero_context):
    authentication, _, root, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    _complete_review(client, project, metadata)
    directory = upload_dir(root, project["agent_project_id"])
    protected = [directory / f'{metadata["upload_id"]}.{suffix}.json' for suffix in (
        "chunks", "rule-detections", "zero-shot-detections", "hybrid-detections", "human-reviews",
    )]
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in protected]
    url = canonical_url(project["agent_project_id"], metadata["upload_id"])
    first_response = client.post(url)
    assert first_response.status_code == 200
    result = first_response.json()["data"]
    assert result["canonical_schema_version"] == constants.CANONICAL_SCHEMA_VERSION
    assert result["extractor_version"] == constants.DETERMINISTIC_EXTRACTOR_VERSION
    assert result["metrics"]["verified_chunk_count"] == 1
    assert result["metrics"]["canonical_artifact_count"] >= 1
    assert all(item["artifact_id"].startswith("CA-") for item in result["artifacts"])
    assert all(item["source_refs"] for item in result["artifacts"])
    assert all("file_path" not in json.dumps(item).lower() for item in result["artifacts"])
    assert client.post(url).json()["data"] == result
    assert client.get(url).json()["data"] == result
    after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in protected]
    assert after == before


def test_changed_labels_invalidate_cache_and_malformed_cache_rebuilds(zero_context):
    authentication, _, root, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    completed = _complete_review(client, project, metadata)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    url = canonical_url(project_id, upload_id)
    first = client.post(url).json()["data"]
    directory = upload_dir(root, project_id)
    cache = directory / f"{upload_id}.canonical-artifacts.json"
    cache.write_text("not-json", encoding="utf-8")
    assert client.get(url).status_code == 404
    rebuilt = client.post(url)
    assert rebuilt.status_code == 200
    rebuilt_artifacts = rebuilt.json()["data"]["artifacts"]
    assert [item["artifact_id"] for item in rebuilt_artifacts] == [item["artifact_id"] for item in first["artifacts"]]
    assert [item["data"] for item in rebuilt_artifacts] == [item["data"] for item in first["artifacts"]]

    review_state = state(client, project, metadata)
    item = review_state["review_queue"][0]
    candidates = item["hybrid"]["candidates"]
    decisions = [{
        "action": "RELABEL", "source_candidate_label": candidates[0]["label"],
        "final_label": "DATABASE_SCHEMA", "note": None,
    }] + [accept(candidate["label"]) for candidate in candidates[1:]]
    changed = put(client, project, metadata, item["chunk"]["chunk_id"],
                  completed["review"]["review_fingerprint"], decisions)
    assert changed.status_code == 200
    assert client.get(url).status_code == 404
    updated = client.post(url).json()["data"]
    assert updated["human_review_digest"] != first["human_review_digest"]
    assert any(item["artifact_type"] == "DATABASE_SCHEMA" for item in updated["artifacts"])


def test_stale_review_security_deletion_and_openapi(zero_context):
    authentication, _, root, _ = zero_context
    owner, foreign = authentication.client("USR-001"), authentication.client("USR-002")
    project, metadata = prepare_hybrid(owner)
    _complete_review(owner, project, metadata)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    url = canonical_url(project_id, upload_id)
    assert foreign.post(url).status_code == 404
    wrong = create_project(owner, "DESIGN_PLANNING")
    assert owner.post(canonical_url(wrong["agent_project_id"], upload_id)).status_code == 422
    directory = upload_dir(root, project_id)
    hybrid = directory / f"{upload_id}.hybrid-detections.json"
    payload = json.loads(hybrid.read_text(encoding="utf-8"))
    payload["created_at"] = "2026-10-18T18:00:00Z"
    hybrid.write_text(json.dumps(payload), encoding="utf-8")
    stale = owner.post(url)
    assert stale.status_code == 409
    assert stale.json()["errors"][0]["message"] == "STALE_HUMAN_VERIFICATION"

    # Restore the trusted hybrid digest by rebuilding, then re-verify and build.
    owner.post(f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/hybrid-detections", params={"force": "true"})
    current = state(owner, project, metadata)
    decisions = [accept(candidate["label"]) for candidate in current["review_queue"][0]["hybrid"]["candidates"]]
    put(owner, project, metadata, current["review_queue"][0]["chunk"]["chunk_id"],
        current["review"]["review_fingerprint"], decisions)
    assert owner.post(url).status_code == 200
    sidecar = directory / f"{upload_id}.canonical-artifacts.json"
    assert sidecar.exists()
    assert owner.delete(f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}").status_code == 200
    assert not sidecar.exists()

    paths = app.openapi()["paths"]
    path = "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/canonical-artifacts"
    assert set(paths[path]) == {"get", "post"}
    forbidden = ("semantic-extraction", "dataset-export", "fine-tun", "agent-run", "code-generation", "image-understanding")
    agent_paths = [item for item in paths if item.startswith("/api/v1/agents/implementation")]
    assert not any(any(value in item for value in forbidden) for item in agent_paths)
