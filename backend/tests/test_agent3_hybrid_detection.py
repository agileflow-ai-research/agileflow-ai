import json

import pytest

from app.main import app
from app.modules.agents.implementation.semantic_discovery.hybrid import constants
from app.modules.agents.implementation.semantic_discovery.hybrid.policy import decide_chunk
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel as Label, ChunkRuleDetection, RuleEvidence,
    RuleEvidenceSource, RulePrediction, RuleStrength,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.schemas import (
    ChunkZeroShotDetection, ZeroShotScore,
)
from test_agent3_rule_detection import run_detector
from test_agent3_zero_shot_detection import (
    get_model, prepare, run_model, semantic_chunk, zero_context,
)
from test_agent3_document_extraction import extraction_context, upload_dir


def rule_detection(*predictions):
    chunk = semantic_chunk()
    if not predictions:
        predictions = (RulePrediction(
            label=Label.OTHER_CONTEXT, rule_score=0,
            strength=RuleStrength.WEAK,
            evidence=[RuleEvidence(rule_id="OTHER_CONTEXT_FALLBACK",
                                   matched_text="No deterministic artifact rule matched",
                                   source=RuleEvidenceSource.TEXT)],
        ),)
    return ChunkRuleDetection(
        chunk_id=chunk.chunk_id, text_hash=chunk.text_hash,
        predictions=list(predictions), unclassified=predictions[0].label is Label.OTHER_CONTEXT,
    )


def prediction(label, strength, score=.9):
    return RulePrediction(
        label=label, rule_score=score, strength=strength,
        evidence=[RuleEvidence(rule_id="TEST_RULE", matched_text="POST /api/bookings",
                               source=RuleEvidenceSource.TEXT)],
    )


def model_detection(scores):
    chunk = semantic_chunk()
    vector = [ZeroShotScore(label=label, score=scores.get(label, .1)) for label in Label]
    return ChunkZeroShotDetection(
        chunk_id=chunk.chunk_id, text_hash=chunk.text_hash,
        provenance=chunk.provenance, model_token_count=10, model_max_length=512,
        input_truncated=False, classification_succeeded=True, inference_ms=1,
        scores=vector, display_predictions=[],
    )


def candidate(result, label):
    return next(item for item in result.candidates if item.label is label)


def test_agreement_auto_candidate_and_evidence_preserved():
    rule = prediction(Label.API_SPECIFICATION, RuleStrength.STRONG, .94)
    result = decide_chunk(rule_detection(rule), model_detection({Label.API_SPECIFICATION: .91}))
    item = candidate(result, Label.API_SPECIFICATION)
    assert (item.evidence_state, item.decision) == ("RULE_AND_MODEL", "AUTO_CANDIDATE")
    assert item.rule.score == .94 and item.rule.evidence and item.model.score == .91
    assert item.reason_codes == ["RULE_MODEL_AGREEMENT", "STRONG_RULE_SUPPORT"]
    assert decide_chunk(rule_detection(rule), model_detection({Label.API_SPECIFICATION: .91})) == result


def test_rule_only_is_reviewed_and_weak_evidence_is_rejected():
    strong = decide_chunk(
        rule_detection(prediction(Label.DATABASE_SCHEMA, RuleStrength.STRONG)),
        model_detection({Label.DATABASE_SCHEMA: .2}),
    )
    assert candidate(strong, Label.DATABASE_SCHEMA).evidence_state == "RULE_ONLY"
    assert candidate(strong, Label.DATABASE_SCHEMA).decision == "REVIEW_REQUIRED"
    weak = decide_chunk(
        rule_detection(prediction(Label.DATABASE_SCHEMA, RuleStrength.WEAK, .4)),
        model_detection({Label.DATABASE_SCHEMA: .4}),
    )
    assert candidate(weak, Label.DATABASE_SCHEMA).decision == "REJECTED"
    assert candidate(weak, Label.DATABASE_SCHEMA).evidence_state == "INSUFFICIENT_EVIDENCE"


def test_model_only_never_auto_candidate_and_other_context_fallback():
    result = decide_chunk(rule_detection(), model_detection({Label.API_SPECIFICATION: .9}))
    item = candidate(result, Label.API_SPECIFICATION)
    assert (item.evidence_state, item.decision) == ("MODEL_ONLY", "REVIEW_REQUIRED")
    fallback = decide_chunk(rule_detection(), model_detection({Label.OTHER_CONTEXT: .05}))
    item = candidate(fallback, Label.OTHER_CONTEXT)
    assert item.evidence_state == "INSUFFICIENT_EVIDENCE"
    assert item.decision == "REVIEW_REQUIRED"
    assert item.reason_codes == ["NO_ARTIFACT_EVIDENCE", "OTHER_CONTEXT_FALLBACK"]


def test_disagreement_ambiguity_and_label_explosion_are_explicit():
    conflict = decide_chunk(
        rule_detection(prediction(Label.DATABASE_SCHEMA, RuleStrength.STRONG)),
        model_detection({Label.API_SPECIFICATION: .87, Label.DATABASE_SCHEMA: .31}),
    )
    item = candidate(conflict, Label.DATABASE_SCHEMA)
    assert (item.evidence_state, item.decision) == ("RULE_MODEL_DISAGREEMENT", "REVIEW_REQUIRED")
    scores = {
        Label.API_SPECIFICATION: .84, Label.DATABASE_SCHEMA: .82,
        Label.SYSTEM_ARCHITECTURE: .79, Label.FUNCTIONAL_REQUIREMENTS: .77,
    }
    noisy = decide_chunk(rule_detection(), model_detection(scores))
    assert noisy.diagnostics.model_label_explosion is True
    assert noisy.diagnostics.model_ambiguous is True
    assert len([item for item in noisy.candidates if item.evidence_state == "MODEL_ONLY"]) == 1
    assert all(item.decision != "AUTO_CANDIDATE" for item in noisy.candidates)


def test_ambiguity_downgrades_same_label_automatic_decision():
    result = decide_chunk(
        rule_detection(prediction(Label.API_SPECIFICATION, RuleStrength.STRONG)),
        model_detection({Label.API_SPECIFICATION: .85, Label.DATABASE_SCHEMA: .80}),
    )
    item = candidate(result, Label.API_SPECIFICATION)
    assert result.diagnostics.model_ambiguous is True
    assert item.decision == "REVIEW_REQUIRED"
    assert "MODEL_AMBIGUOUS" in item.reason_codes


def hybrid_url(project_id, upload_id):
    return f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/hybrid-detections"


def test_api_prerequisites_sidecar_cache_metrics_and_delete(zero_context, monkeypatch):
    authentication, _, root, classifier = zero_context
    client = authentication.client()
    project, metadata = prepare(client, b"POST /api/bookings")
    url = hybrid_url(project["agent_project_id"], metadata["upload_id"])
    missing_rule = client.post(url)
    assert missing_rule.status_code == 409
    assert missing_rule.json()["errors"][0]["message"] == "RULE_DETECTION_REQUIRED"
    assert run_detector(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    missing_model = client.post(url)
    assert missing_model.status_code == 409
    assert missing_model.json()["errors"][0]["message"] == "ZERO_SHOT_DETECTION_REQUIRED"
    assert run_model(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    first = client.post(url)
    assert first.status_code == 200
    result = first.json()["data"]
    assert result["policy"]["decision_version"] == constants.HYBRID_DECISION_VERSION
    assert result["policy"]["threshold_semantics"] == "EXPERIMENTAL_ENGINEERING_DEFAULTS_NOT_VALIDATED"
    assert "accuracy" not in result["metrics"] and "hybrid_score" not in json.dumps(result).lower()
    assert client.post(url).json()["data"] == result
    directory = upload_dir(root, project["agent_project_id"])
    sidecar = directory / f'{metadata["upload_id"]}.hybrid-detections.json'
    assert sidecar.exists()
    assert client.delete(f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}').status_code == 200
    assert not sidecar.exists()


def test_stale_baseline_hash_is_rejected(zero_context):
    authentication, _, root, _ = zero_context
    client = authentication.client()
    project, metadata = prepare(client, b"POST /api/bookings")
    run_detector(client, project["agent_project_id"], metadata["upload_id"])
    run_model(client, project["agent_project_id"], metadata["upload_id"])
    sidecar = upload_dir(root, project["agent_project_id"]) / f'{metadata["upload_id"]}.zero-shot-detections.json'
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["chunks"][0]["text_hash"] = "0" * 64
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    response = client.post(hybrid_url(project["agent_project_id"], metadata["upload_id"]))
    assert response.status_code == 409
    assert response.json()["errors"][0]["message"] == "STALE_CLASSIFICATION_INPUT"


def test_cache_rebuilds_for_malformed_cache_policy_and_baseline_changes(zero_context, monkeypatch):
    authentication, _, root, _ = zero_context
    client = authentication.client()
    project, metadata = prepare(client, b"POST /api/bookings")
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    run_detector(client, project_id, upload_id)
    run_model(client, project_id, upload_id)
    url = hybrid_url(project_id, upload_id)
    first = client.post(url).json()["data"]
    directory = upload_dir(root, project_id)
    hybrid = directory / f"{upload_id}.hybrid-detections.json"
    hybrid.write_text("not-json", encoding="utf-8")
    assert client.get(url).status_code == 404
    rebuilt = client.post(url).json()["data"]
    assert rebuilt["chunks"] == first["chunks"]

    monkeypatch.setattr(constants, "HYBRID_POLICY_VERSION", "2")
    policy_rebuild = client.post(url).json()["data"]
    assert policy_rebuild["policy"]["policy_version"] == "2"

    rule_path = directory / f"{upload_id}.rule-detections.json"
    rule_payload = json.loads(rule_path.read_text(encoding="utf-8"))
    rule_payload["created_at"] = "2026-10-18T15:00:00Z"
    rule_path.write_text(json.dumps(rule_payload), encoding="utf-8")
    rule_rebuild = client.post(url).json()["data"]
    assert rule_rebuild["rule_baseline"]["result_sha256"] != policy_rebuild["rule_baseline"]["result_sha256"]

    model_path = directory / f"{upload_id}.zero-shot-detections.json"
    model_payload = json.loads(model_path.read_text(encoding="utf-8"))
    model_payload["created_at"] = "2026-10-18T15:01:00Z"
    model_path.write_text(json.dumps(model_payload), encoding="utf-8")
    model_rebuild = client.post(url).json()["data"]
    assert model_rebuild["model_baseline"]["result_sha256"] != rule_rebuild["model_baseline"]["result_sha256"]


def test_openapi_exposes_hybrid_only_as_get_and_post():
    path = "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/hybrid-detections"
    assert set(app.openapi()["paths"][path]) == {"get", "post"}
