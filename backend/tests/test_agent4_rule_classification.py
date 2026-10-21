from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from app.modules.agents.testing_validation.intelligence.rules.catalog import (
    AGENT4_RULE_CATALOG_FINGERPRINT,
    AGENT4_RULES_VERSION,
    TESTING_RULE_CATALOG,
    rule_catalog_fingerprint,
)
from app.modules.agents.testing_validation.intelligence.rules.matcher import (
    classify_testing_chunk,
)
from app.modules.agents.testing_validation.intelligence.rules.service import (
    Agent4RuleClassificationGateError,
    Agent4RuleClassificationService,
)
from app.modules.agents.testing_validation.intelligence.rules.storage import (
    Agent4RuleStorage,
    Agent4RuleStorageError,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TestingIntelligenceLabel as IntelligenceLabel,
)
from app.modules.agents.testing_validation.preparation.chunking.schemas import (
    TestingChunk as Chunk,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
)
from app.modules.agents.testing_validation.workflow.storage import (
    Agent4WorkflowStorage,
)
from app.modules.standalone.service import StandaloneService
from test_agent4_n2_orchestration import add_text, confirm, create_project, load, n2_context
from test_agent4_testing_intelligence_contracts import chunk, chunk_set
from test_standalone_foundation import user


NOW = datetime(2026, 2, 1, tzinfo=UTC)


def classify(text, *, artifact_type="FUNCTIONAL_REQUIREMENTS"):
    base = chunk()
    item = Chunk.model_validate({
        **base.model_dump(mode="json"),
        "artifact_type": artifact_type,
        "text": text,
        "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "token_count": max(1, len(text.split())),
        "source_spans": [{
            **base.source_spans[0].model_dump(mode="json"),
            "end_offset": len(text),
        }],
    })
    manifest = chunk_set(item)
    return classify_testing_chunk(
        item, manifest, confirmed_source_ids={item.source_id}, processed_at=NOW
    )


def labels(text, **kwargs):
    return set(classify(text, **kwargs).detected_labels)


def test_rule_catalog_is_versioned_unique_ordered_immutable_and_fingerprinted():
    assert AGENT4_RULES_VERSION == "R1"
    ids = [rule.rule_id for rule in TESTING_RULE_CATALOG]
    assert len(ids) == len(set(ids))
    assert all(rule.label in TESTING_INTELLIGENCE_LABEL_ORDER for rule in TESTING_RULE_CATALOG)
    assert isinstance(TESTING_RULE_CATALOG, tuple)
    assert rule_catalog_fingerprint() == AGENT4_RULE_CATALOG_FINGERPRINT
    changed = (replace(TESTING_RULE_CATALOG[0], pattern="changed"), *TESTING_RULE_CATALOG[1:])
    assert rule_catalog_fingerprint(changed) != AGENT4_RULE_CATALOG_FINGERPRINT


@pytest.mark.parametrize(("text", "expected"), [
    ("The system shall create a booking.", {"FUNCTIONAL_BEHAVIOR"}),
    ("The email field is required and must be a valid email.", {"INPUT_VALIDATION"}),
    ("The password must have a minimum length of 12 characters.", {"BOUNDARY_CONSTRAINT"}),
    ("The quantity must be between 1 and 20.", {"BOUNDARY_CONSTRAINT"}),
    ("The account number must be unique.", {"DATA_INTEGRITY"}),
    ("Foreign key consistency prevents orphan records.", {"DATA_INTEGRITY"}),
    ("POST /api/bookings uses a request body.", {"API_CONTRACT"}),
    ("Return HTTP 404 for a missing booking.", {"API_CONTRACT", "ERROR_HANDLING"}),
    ("Click the Submit button, then navigate to the confirmation page.", {"UI_WORKFLOW"}),
    ("Users log in using credentials and MFA.", {"AUTHENTICATION"}),
    ("Only administrators may delete bookings.", {"AUTHORIZATION"}),
    ("Only the owner can update a booking.", {"AUTHORIZATION"}),
    ("Traffic must use TLS 1.3 and rate limiting.", {"SECURITY_CONTROL"}),
    ("Response time must be under 2 seconds.", {"PERFORMANCE_SLO"}),
    ("Support at least 100 requests per second.", {"PERFORMANCE_SLO", "BOUNDARY_CONSTRAINT"}),
    ("Automatically retry the request and failover to the backup.", {"RELIABILITY_RECOVERY"}),
    ("Display an error message for invalid input.", {"ERROR_HANDLING"}),
    ("Given a booking When it is cancelled Then the slot is released", {"ACCEPTANCE_CONDITION"}),
    ("The feature is accepted when a receipt appears.", {"ACCEPTANCE_CONDITION"}),
    ("Persist the record and update the stored value.", {"STATE_PERSISTENCE"}),
])
def test_precision_rule_families(text, expected):
    assert expected.issubset({label.value for label in labels(text)})


@pytest.mark.parametrize("text", [
    "This chapter gives project background and history.",
    "The project page has a blue theme.",
    "The booking is valid for 2 days.",
    "An error occurred during the historical migration.",
    "The current state is discussed below.",
])
def test_broad_or_incidental_language_does_not_overmatch(text):
    assert classify(text).detected_labels == []


def test_incidental_documentation_path_is_not_an_api_contract():
    assert IntelligenceLabel.API_CONTRACT not in labels(
        "Users can view the API documentation at /docs/getting-started."
    )


def test_rule_miss_never_emits_non_testable_context():
    result = classify("General project background.")
    assert result.detected_labels == []
    assert IntelligenceLabel.NON_TESTABLE_CONTEXT not in result.detected_labels
    assert not any(rule.label is IntelligenceLabel.NON_TESTABLE_CONTEXT for rule in TESTING_RULE_CATALOG)


def test_multilabel_order_and_independent_security_meaning():
    result = classify(
        "The system shall reject invalid input. The value must be at least 3. "
        "Only administrators may update it."
    )
    assert result.detected_labels == [
        label for label in TESTING_INTELLIGENCE_LABEL_ORDER
        if label in set(result.detected_labels)
    ]
    assert IntelligenceLabel.FUNCTIONAL_BEHAVIOR in result.detected_labels
    assert IntelligenceLabel.BOUNDARY_CONSTRAINT in result.detected_labels
    assert IntelligenceLabel.AUTHORIZATION in result.detected_labels
    assert IntelligenceLabel.SECURITY_CONTROL not in result.detected_labels


def test_grounding_original_case_offsets_identity_deduplication_and_order():
    text = "Only Administrators may delete. Only administrators may archive."
    first = classify(text)
    second = classify(text)
    assert first.result_id == second.result_id
    assert [item.evidence_id for item in first.rule_evidence] == [
        item.evidence_id for item in second.rule_evidence
    ]
    assert len(first.rule_evidence) == 2
    for evidence in first.rule_evidence:
        assert evidence.quote == text[evidence.start_offset:evidence.end_offset]
        assert evidence.confidence is None
        assert evidence.evidence_type.value == "RULE"
    assert [item.start_offset for item in first.rule_evidence] == sorted(
        item.start_offset for item in first.rule_evidence
    )


def test_artifact_type_is_only_a_narrowing_context():
    assert labels("Background only.", artifact_type="API_SPECIFICATION") == set()
    assert labels("Background only.", artifact_type="ACCEPTANCE_CRITERIA") == set()
    assert labels("Background only.", artifact_type="NON_FUNCTIONAL_REQUIREMENTS") == set()
    assert IntelligenceLabel.API_CONTRACT in labels(
        "The response schema contains an id.", artifact_type="API_SPECIFICATION"
    )
    assert IntelligenceLabel.API_CONTRACT not in labels(
        "The response schema contains an id.", artifact_type="UI_FLOW"
    )


def test_rule_result_contains_only_deterministic_contract_fields():
    result = classify("The system shall create a booking.")
    payload = result.model_dump(mode="json")
    assert payload["taxonomy_version"] == "T1"
    assert payload["rules_version"] == "R1"
    assert "label_scores" not in payload
    assert "model_id" not in payload
    assert "hybrid" not in payload
    assert "facts" not in payload


def service_for(n2_context):
    _, _, _, root, projects, runs, _, _, _ = n2_context
    return Agent4RuleClassificationService(
        StandaloneService(projects, runs),
        Agent4WorkflowStorage(root),
        Agent4ChunkStorage(root),
        Agent4RuleStorage(root),
        clock=lambda: NOW,
    )


def prepared_project(n2_context, content="The system shall create a booking."):
    client, _, executor, _, _, _, _, _, _ = n2_context
    project_id = create_project(client)
    source = add_text(client, project_id, content)
    confirm(client, project_id)
    executor.drain()
    return client, project_id, source


def test_project_service_persists_separately_reuses_cache_and_force_is_stable(n2_context):
    client, project_id, source = prepared_project(n2_context)
    service = service_for(n2_context)
    root = n2_context[3]
    immutable = {
        path: path.read_bytes() for path in (root / project_id).rglob("*") if path.is_file()
    }
    first = service.build(project_id, source["source_id"], user())
    sidecar = root / project_id / "intelligence" / f"{source['source_id']}.rules.json"
    raw = sidecar.read_bytes()
    cached = service.build(project_id, source["source_id"], user())
    assert cached == first
    assert sidecar.read_bytes() == raw
    service._clock = lambda: NOW + timedelta(seconds=1)
    rebuilt = service.build(project_id, source["source_id"], user(), force=True)
    assert rebuilt.processed_at != first.processed_at
    assert [r.result_id for r in rebuilt.results] == [r.result_id for r in first.results]
    assert [[e.evidence_id for e in r.rule_evidence] for r in rebuilt.results] == [
        [e.evidence_id for e in r.rule_evidence] for r in first.results
    ]
    assert all(path.read_bytes() == value for path, value in immutable.items())
    workflow = load(client, project_id)
    assert workflow["current_node_id"] == "TESTING_INTELLIGENCE"
    assert workflow["nodes"][2]["status"] == "NOT_STARTED"
    assert workflow["nodes"][3]["status"] == "LOCKED"
    assert n2_context[5].documents == {}
    assert not list((root / project_id).rglob("*.zero-shot.json"))
    assert not list((root / project_id).rglob("*.hybrid.json"))


def test_corrupt_or_stale_cache_rebuilds(n2_context):
    _, project_id, source = prepared_project(n2_context)
    service = service_for(n2_context)
    root = n2_context[3]
    first = service.build(project_id, source["source_id"], user())
    sidecar = root / project_id / "intelligence" / f"{source['source_id']}.rules.json"
    sidecar.write_text("not-json", encoding="utf-8")
    service._clock = lambda: NOW + timedelta(seconds=1)
    rebuilt = service.build(project_id, source["source_id"], user())
    assert rebuilt.processed_at != first.processed_at


def test_atomic_failure_cleans_partial(n2_context, monkeypatch):
    _, project_id, source = prepared_project(n2_context)
    service = service_for(n2_context)
    original = Path.replace
    monkeypatch.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(OSError("boom")) if self.name.endswith(".rules.json.part") else original(self, target))
    with pytest.raises(Agent4RuleStorageError):
        service.build(project_id, source["source_id"], user())
    assert not list((n2_context[3] / project_id).rglob("*.rules.json.part"))


def test_project_service_rejects_before_n2_completion(n2_context):
    client = n2_context[0]
    project_id = create_project(client)
    source = add_text(client, project_id)
    confirm(client, project_id)
    with pytest.raises(Agent4RuleClassificationGateError, match="must complete"):
        service_for(n2_context).build(project_id, source["source_id"], user())

