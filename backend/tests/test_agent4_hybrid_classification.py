from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.agents.testing_validation.intelligence.hybrid.engine import (
    decide_hybrid_for_chunk,
)
from app.modules.agents.testing_validation.intelligence.hybrid.policy import (
    H1_POLICY,
    HYBRID_POLICY_FINGERPRINT,
    HYBRID_POLICY_VERSION,
    MODEL_ONLY_REVIEW_THRESHOLD,
    POLICY_SEMANTICS,
    RULE_MODEL_CONFLICT_THRESHOLD,
    RULE_MODEL_SUPPORT_THRESHOLD,
    hybrid_policy_fingerprint,
)
from app.modules.agents.testing_validation.intelligence.hybrid.service import (
    Agent4HybridClassificationGateError,
    Agent4HybridClassificationService,
)
from app.modules.agents.testing_validation.intelligence.hybrid.storage import (
    Agent4HybridStorage,
    Agent4HybridStorageError,
)
from app.modules.agents.testing_validation.intelligence.rules.storage import Agent4RuleStorage
from app.modules.agents.testing_validation.intelligence.schemas import (
    TestingZeroShotClassificationResult as ZeroShotResult,
    ZeroShotInputMetadata,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TestingIntelligenceLabel as Label,
)
from app.modules.agents.testing_validation.intelligence.zero_shot import constants as zc
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import (
    Agent4ZeroShotStorage,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from app.modules.standalone.service import StandaloneService
from test_agent4_n2_orchestration import add_text, confirm, create_project, load, n2_context
from test_agent4_rule_classification import classify as classify_rules
from test_agent4_rule_classification import service_for as rule_service_for
from test_agent4_zero_shot_classification import FakeRuntime
from test_agent4_zero_shot_classification import service_for as zero_service_for
from test_standalone_foundation import user


NOW = datetime(2026, 4, 1, tzinfo=UTC)


def paired(*, text="Only administrators may delete another user's booking.",
           scores=None, at=NOW):
    rule = classify_rules(text)
    values = {label: 0.1 for label in TESTING_INTELLIGENCE_LABEL_ORDER}
    values.update(scores or {})
    model = ZeroShotResult(
        result_id="A4ZSC-" + "b" * 32,
        chunk=rule.chunk,
        taxonomy_version="T1",
        model_id=zc.MODEL_ID,
        model_revision=zc.MODEL_REVISION,
        label_scores=values,
        label_description_version="ZL1",
        hypothesis_template_version=zc.HYPOTHESIS_TEMPLATE_VERSION,
        input_metadata=ZeroShotInputMetadata(
            input_token_count=10, model_max_tokens=512, truncated=False
        ),
        inference_duration_ms=1,
        processed_at=at,
    )
    return rule, model


def decision(result, label):
    return next(item for item in result.decisions if item.label is label)


def test_h1_policy_is_exact_ordered_immutable_fingerprinted_and_provisional():
    assert HYBRID_POLICY_VERSION == "H1"
    assert RULE_MODEL_SUPPORT_THRESHOLD == 0.60
    assert RULE_MODEL_CONFLICT_THRESHOLD == 0.35
    assert MODEL_ONLY_REVIEW_THRESHOLD == 0.80
    assert 0 <= RULE_MODEL_CONFLICT_THRESHOLD <= RULE_MODEL_SUPPORT_THRESHOLD <= MODEL_ONLY_REVIEW_THRESHOLD <= 1
    assert hybrid_policy_fingerprint() == HYBRID_POLICY_FINGERPRINT
    assert hybrid_policy_fingerprint(replace(H1_POLICY, model_only_review_threshold=.81)) != HYBRID_POLICY_FINGERPRINT
    assert "NOT_CALIBRATED" in POLICY_SEMANTICS
    with pytest.raises((AttributeError, TypeError)):
        H1_POLICY.version = "H2"


@pytest.mark.parametrize(
    ("score", "status", "state", "reason"),
    [
        (.60, "ACCEPTED", "AGREEMENT", "RULE_AND_MODEL_AGREE"),
        (.90, "ACCEPTED", "AGREEMENT", "RULE_AND_MODEL_AGREE"),
        (.59, "REVIEW_REQUIRED", "RULE_ONLY", "RULE_WITH_MODERATE_MODEL_SUPPORT"),
        (.35, "REVIEW_REQUIRED", "RULE_ONLY", "RULE_WITH_MODERATE_MODEL_SUPPORT"),
        (.349, "REVIEW_REQUIRED", "CONFLICT", "RULE_MODEL_CONFLICT"),
    ],
)
def test_rule_boundaries_preserve_evidence_and_raw_score(score, status, state, reason):
    rule, model = paired(scores={Label.AUTHORIZATION: score})
    result = decide_hybrid_for_chunk(rule, model, processed_at=NOW)
    item = decision(result, Label.AUTHORIZATION)
    assert (item.status.value, item.evidence_state.value) == (status, state)
    assert item.reason_codes == [reason]
    assert item.rule_detected is True
    assert item.rule_evidence_ids == sorted(e.evidence_id for e in rule.rule_evidence)
    assert item.model_score == score
    assert "confidence" not in item.model_dump()


@pytest.mark.parametrize(("score", "status", "state"), [(.80, "REVIEW_REQUIRED", "MODEL_ONLY"), (.79, "REJECTED", "AMBIGUOUS")])
def test_model_only_boundary_never_auto_accepts(score, status, state):
    rule, model = paired(text="Project background.", scores={Label.API_CONTRACT: score})
    result = decide_hybrid_for_chunk(rule, model, processed_at=NOW)
    item = decision(result, Label.API_CONTRACT)
    assert item.status.value == status and item.evidence_state.value == state
    assert Label.API_CONTRACT not in result.accepted_labels
    assert model.label_scores[Label.API_CONTRACT] == score


def test_non_testable_context_is_suppressed_by_any_testable_candidate():
    rule, model = paired(scores={Label.AUTHORIZATION: .60, Label.NON_TESTABLE_CONTEXT: .99})
    result = decide_hybrid_for_chunk(rule, model, processed_at=NOW)
    item = decision(result, Label.NON_TESTABLE_CONTEXT)
    assert item.status.value == "REJECTED"
    assert item.reason_codes == ["NON_TESTABLE_SUPPRESSED_BY_TESTABLE_EVIDENCE"]


@pytest.mark.parametrize(("score", "status"), [(.80, "REVIEW_REQUIRED"), (.79, "REJECTED")])
def test_non_testable_without_testable_candidate_uses_model_only_review_gate(score, status):
    rule, model = paired(text="Project background.", scores={Label.NON_TESTABLE_CONTEXT: score})
    result = decide_hybrid_for_chunk(rule, model, processed_at=NOW)
    item = decision(result, Label.NON_TESTABLE_CONTEXT)
    assert item.status.value == status
    assert item.status.value != "ACCEPTED"


def test_result_is_complete_canonical_disjoint_and_identity_ignores_time():
    scores = {Label.AUTHORIZATION: .9, Label.SECURITY_CONTROL: .85}
    rule, model = paired(scores=scores)
    first = decide_hybrid_for_chunk(rule, model, processed_at=NOW)
    second = decide_hybrid_for_chunk(rule, model, processed_at=NOW + timedelta(days=1))
    assert first.result_id == second.result_id
    assert first.decisions[:-1] == second.decisions[:-1]
    assert [d.label for d in first.decisions] == list(TESTING_INTELLIGENCE_LABEL_ORDER)
    groups = first.accepted_labels + first.review_required_labels + first.rejected_labels
    assert len(first.decisions) == len(set(groups)) == 15
    assert set(groups) == set(TESTING_INTELLIGENCE_LABEL_ORDER)


@pytest.mark.parametrize("field", ["chunk_id", "text_sha256", "source_id", "chunk_set_fingerprint"])
def test_mismatched_rule_model_evidence_is_rejected(field):
    rule, model = paired()
    value = "A4CHK-" + "c" * 32 if field == "chunk_id" else "c" * 64
    if field == "source_id":
        value = "A4SRC-" + "c" * 32
    altered = model.model_copy(update={"chunk": model.chunk.model_copy(update={field: value})})
    with pytest.raises(ValueError, match="identical evidence"):
        decide_hybrid_for_chunk(rule, altered, processed_at=NOW)


def test_stale_model_configuration_and_incomplete_scores_are_rejected():
    rule, model = paired()
    stale = model.model_copy(update={"model_revision": "stale"})
    with pytest.raises(ValueError, match="configuration is stale"):
        decide_hybrid_for_chunk(rule, stale, processed_at=NOW)
    payload = model.model_dump(mode="json")
    payload["label_scores"].pop("API_CONTRACT")
    with pytest.raises(ValidationError):
        ZeroShotResult.model_validate(payload)


def hybrid_service(context, *, clock=lambda: NOW):
    _, _, _, root, projects, runs, _, _, _ = context
    return Agent4HybridClassificationService(
        StandaloneService(projects, runs), Agent4WorkflowStorage(root),
        Agent4ChunkStorage(root), Agent4RuleStorage(root),
        Agent4ZeroShotStorage(root), Agent4HybridStorage(root), clock=clock,
    )


def prepared_with_inputs(context):
    client, _, executor, _, _, _, _, _, _ = context
    project_id = create_project(client)
    source = add_text(client, project_id, "The system shall create a booking.")
    confirm(client, project_id)
    executor.drain()
    rule_service_for(context).build(project_id, source["source_id"], user())
    runtime = FakeRuntime(scores=[.1] * 15)
    zero_service_for(context, runtime).build(project_id, source["source_id"], user())
    return client, project_id, source, runtime


def test_service_persists_manifest_summaries_and_reuses_cache_without_inference(n2_context):
    client, project_id, source, runtime = prepared_with_inputs(n2_context)
    root = n2_context[3]
    before = {p: p.read_bytes() for p in (root / project_id).rglob("*") if p.is_file()}
    service = hybrid_service(n2_context)
    first = service.build(project_id, source["source_id"], user())
    path = root / project_id / "intelligence" / f"{source['source_id']}.hybrid.json"
    raw = path.read_bytes()
    cached = service.build(project_id, source["source_id"], user())
    assert cached == first and path.read_bytes() == raw
    assert len(first.results) == len(first.chunk_ids)
    assert first.summary.chunks_total == len(first.chunk_ids)
    assert first.hybrid_policy_fingerprint == HYBRID_POLICY_FINGERPRINT
    assert len(runtime.calls) == 1
    assert all(p.read_bytes() == data for p, data in before.items())
    assert all("text" not in result.chunk.model_dump() for result in first.results)
    workflow = load(client, project_id)
    assert workflow["current_node_id"] == "TESTING_INTELLIGENCE"
    assert workflow["nodes"][2]["status"] == "NOT_STARTED"
    assert workflow["nodes"][3]["status"] == "LOCKED"
    assert n2_context[5].documents == {}


def test_force_rebuild_only_changes_hybrid_timestamp_and_keeps_ids(n2_context):
    _, project_id, source, runtime = prepared_with_inputs(n2_context)
    service = hybrid_service(n2_context)
    first = service.build(project_id, source["source_id"], user())
    rules_path = n2_context[3] / project_id / "intelligence" / f"{source['source_id']}.rules.json"
    model_path = n2_context[3] / project_id / "intelligence" / f"{source['source_id']}.zero-shot.json"
    immutable = (rules_path.read_bytes(), model_path.read_bytes())
    service._clock = lambda: NOW + timedelta(seconds=1)
    second = service.build(project_id, source["source_id"], user(), force=True)
    assert second.processed_at != first.processed_at
    assert [r.result_id for r in second.results] == [r.result_id for r in first.results]
    assert (rules_path.read_bytes(), model_path.read_bytes()) == immutable
    assert len(runtime.calls) == 1


def test_missing_or_stale_inputs_rejected_and_corrupt_hybrid_rebuilds(n2_context):
    _, project_id, source, _ = prepared_with_inputs(n2_context)
    root = n2_context[3]
    service = hybrid_service(n2_context)
    first = service.build(project_id, source["source_id"], user())
    hybrid_path = root / project_id / "intelligence" / f"{source['source_id']}.hybrid.json"
    hybrid_path.write_text("not-json", encoding="utf-8")
    assert service.build(project_id, source["source_id"], user()).results == first.results
    rule_path = root / project_id / "intelligence" / f"{source['source_id']}.rules.json"
    rule_path.unlink()
    with pytest.raises(Agent4HybridClassificationGateError, match="rule classification"):
        service.build(project_id, source["source_id"], user(), force=True)


def test_atomic_failure_cleans_partial(n2_context, monkeypatch):
    _, project_id, source, _ = prepared_with_inputs(n2_context)
    original = Path.replace
    monkeypatch.setattr(
        Path, "replace",
        lambda self, target: (_ for _ in ()).throw(OSError("boom"))
        if self.name.endswith(".hybrid.json.part") else original(self, target),
    )
    with pytest.raises(Agent4HybridStorageError):
        hybrid_service(n2_context).build(project_id, source["source_id"], user())
    assert not list((n2_context[3] / project_id).rglob("*.hybrid.json.part"))


def test_service_requires_completed_n2_and_current_manifests(n2_context):
    client = n2_context[0]
    project_id = create_project(client)
    source = add_text(client, project_id, "The system shall create a booking.")
    confirm(client, project_id)
    with pytest.raises(Agent4HybridClassificationGateError, match="Input Preparation"):
        hybrid_service(n2_context).build(project_id, source["source_id"], user())
