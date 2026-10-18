import hashlib
import json
from types import SimpleNamespace

import pytest

from app.main import app
from app.modules.agents.implementation.preparation.human_review import constants
from app.modules.agents.implementation.preparation.human_review.service import HumanReviewService
from test_agent3_document_extraction import create_project, extraction_context, upload_dir
from test_agent3_hybrid_detection import hybrid_url
from test_agent3_rule_detection import run_detector
from test_agent3_zero_shot_detection import prepare, run_model, zero_context


def review_url(project_id, upload_id, chunk_id=None):
    base = f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/human-reviews"
    return f"{base}/{chunk_id}" if chunk_id else base


def prepare_hybrid(client):
    project, metadata = prepare(client, b"POST /api/bookings returns HTTP 409")
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    assert run_detector(client, project_id, upload_id).status_code == 200
    assert run_model(client, project_id, upload_id).status_code == 200
    assert client.post(hybrid_url(project_id, upload_id)).status_code == 200
    return project, metadata


def state(client, project, metadata):
    response = client.get(review_url(project["agent_project_id"], metadata["upload_id"]))
    assert response.status_code == 200
    return response.json()["data"]


def put(client, project, metadata, chunk_id, fingerprint, decisions):
    return client.put(
        review_url(project["agent_project_id"], metadata["upload_id"], chunk_id),
        json={"expected_review_fingerprint": fingerprint, "decisions": decisions},
    )


def accept(label, note=None):
    return {"action": "ACCEPT", "source_candidate_label": label,
            "final_label": label, "note": note}


def test_initial_state_accept_persistence_identity_metrics_and_machine_immutability(zero_context):
    authentication, _, root, _ = zero_context
    client = authentication.client("USR-001")
    project, metadata = prepare_hybrid(client)
    directory = upload_dir(root, project["agent_project_id"])
    machine_paths = [directory / f'{metadata["upload_id"]}.{suffix}.json' for suffix in (
        "rule-detections", "zero-shot-detections", "hybrid-detections",
    )]
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in machine_paths]
    initial = state(client, project, metadata)
    review = initial["review"]
    assert review["review_status"] == "NOT_STARTED"
    assert review["chunks"][0]["review_status"] == "UNREVIEWED"
    assert initial["stale"] is False
    assert review["created_at"] is None
    queue = initial["review_queue"]
    label = queue[0]["hybrid"]["candidates"][0]["label"]
    response = put(
        client, project, metadata, queue[0]["chunk"]["chunk_id"],
        review["review_fingerprint"], [accept(label, "Confirmed against the source.")],
    )
    assert response.status_code == 200
    saved = response.json()["data"]["review"]
    assert saved["chunks"][0]["verified_labels"] == [label]
    assert saved["chunks"][0]["review_status"] == "VERIFIED"
    assert saved["review_status"] == "COMPLETE"
    assert saved["reviewer_owner_id"] == "USR-001"
    assert saved["chunks"][0]["decisions"][0]["reviewer_owner_id"] == "USR-001"
    assert saved["chunks"][0]["decisions"][0]["reviewed_at"]
    assert saved["metrics"] == {
        "total_chunks": 1, "verified_chunks": 1, "remaining_chunks": 0,
        "accepted_candidate_count": 1, "relabeled_candidate_count": 0,
        "excluded_candidate_count": 0, "added_label_count": 0,
        "review_completion_percentage": 100.0,
    }
    assert state(client, project, metadata)["review"] == saved
    after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in machine_paths]
    assert after == before
    sidecar = directory / f'{metadata["upload_id"]}.human-reviews.json'
    assert sidecar.exists()
    serialized = sidecar.read_text(encoding="utf-8").lower()
    assert "post /api/bookings" not in serialized and "file_path" not in serialized


def test_partial_add_label_then_multilabel_relabel_and_false_negative_capture(zero_context):
    authentication, _, _, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    initial = state(client, project, metadata)
    review, item = initial["review"], initial["review_queue"][0]
    source = item["hybrid"]["candidates"][0]["label"]
    chunk_id = item["chunk"]["chunk_id"]
    partial = put(client, project, metadata, chunk_id, review["review_fingerprint"], [{
        "action": "ADD_LABEL", "source_candidate_label": None,
        "final_label": "ACCEPTANCE_CRITERIA", "note": "Status behavior is also a criterion.",
    }])
    assert partial.status_code == 200
    partial_review = partial.json()["data"]["review"]
    assert partial_review["chunks"][0]["review_status"] == "IN_REVIEW"
    assert partial_review["review_status"] == "IN_PROGRESS"
    assert partial_review["metrics"]["added_label_count"] == 1
    complete = put(client, project, metadata, chunk_id, review["review_fingerprint"], [
        accept(source),
        {"action": "ADD_LABEL", "source_candidate_label": None,
         "final_label": "ACCEPTANCE_CRITERIA", "note": None},
    ])
    assert complete.status_code == 200
    labels = complete.json()["data"]["review"]["chunks"][0]["verified_labels"]
    assert set(labels) == {source, "ACCEPTANCE_CRITERIA"}


def test_relabel_and_exclude_preserve_machine_prediction(zero_context):
    authentication, _, _, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    initial = state(client, project, metadata)
    review, item = initial["review"], initial["review_queue"][0]
    source = item["hybrid"]["candidates"][0]["label"]
    chunk_id = item["chunk"]["chunk_id"]
    relabeled = put(client, project, metadata, chunk_id, review["review_fingerprint"], [{
        "action": "RELABEL", "source_candidate_label": source,
        "final_label": "TECHNICAL_CONSTRAINTS", "note": None,
    }])
    assert relabeled.status_code == 200
    data = relabeled.json()["data"]
    assert data["review"]["chunks"][0]["verified_labels"] == ["TECHNICAL_CONSTRAINTS"]
    assert data["review"]["metrics"]["relabeled_candidate_count"] == 1
    assert data["review_queue"][0]["hybrid"]["candidates"][0]["label"] == source
    excluded = put(client, project, metadata, chunk_id, review["review_fingerprint"], [{
        "action": "EXCLUDE", "source_candidate_label": source,
        "final_label": None, "note": "Not an artifact.",
    }])
    assert excluded.status_code == 200
    result = excluded.json()["data"]["review"]
    assert result["chunks"][0]["verified_labels"] == []
    assert result["chunks"][0]["review_status"] == "VERIFIED"
    assert result["metrics"]["excluded_candidate_count"] == 1


@pytest.mark.parametrize(("decisions", "code"), [
    ([{"action": "ACCEPT", "source_candidate_label": "DATABASE_SCHEMA", "final_label": "DATABASE_SCHEMA"}], "UNKNOWN_SOURCE_CANDIDATE"),
    ([{"action": "EXCLUDE", "source_candidate_label": "DATABASE_SCHEMA", "final_label": None}], "UNKNOWN_SOURCE_CANDIDATE"),
    ([{"action": "RELABEL", "source_candidate_label": "API_SPECIFICATION", "final_label": "API_SPECIFICATION"}], "SAME_LABEL_RELABEL_NOT_ALLOWED"),
    ([{"action": "RELABEL", "source_candidate_label": None, "final_label": "DATABASE_SCHEMA"}], "UNKNOWN_SOURCE_CANDIDATE"),
])
def test_invalid_candidate_actions_rejected(zero_context, decisions, code):
    authentication, _, _, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    initial = state(client, project, metadata)
    item = initial["review_queue"][0]
    actual_source = item["hybrid"]["candidates"][0]["label"]
    decisions = [{key: (actual_source if value == "API_SPECIFICATION" else value)
                  for key, value in decision.items()} for decision in decisions]
    response = put(client, project, metadata, item["chunk"]["chunk_id"],
                   initial["review"]["review_fingerprint"], decisions)
    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == code


def test_duplicates_other_context_unknown_label_fingerprint_and_chunk_rejected(zero_context):
    authentication, _, _, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    initial = state(client, project, metadata)
    review, item = initial["review"], initial["review_queue"][0]
    source, chunk_id = item["hybrid"]["candidates"][0]["label"], item["chunk"]["chunk_id"]
    duplicate = put(client, project, metadata, chunk_id, review["review_fingerprint"], [
        {"action": "RELABEL", "source_candidate_label": source, "final_label": "ACCEPTANCE_CRITERIA"},
        {"action": "ADD_LABEL", "source_candidate_label": None, "final_label": "ACCEPTANCE_CRITERIA"},
    ])
    assert duplicate.status_code == 422
    assert duplicate.json()["errors"][0]["message"] == "DUPLICATE_FINAL_LABEL"
    mixed = put(client, project, metadata, chunk_id, review["review_fingerprint"], [
        accept(source),
        {"action": "ADD_LABEL", "source_candidate_label": None, "final_label": "OTHER_CONTEXT"},
    ])
    assert mixed.status_code == 422
    assert mixed.json()["errors"][0]["message"] == "OTHER_CONTEXT_MUST_BE_EXCLUSIVE"
    unknown_label = client.put(review_url(project["agent_project_id"], metadata["upload_id"], chunk_id), json={
        "expected_review_fingerprint": review["review_fingerprint"],
        "decisions": [{"action": "ADD_LABEL", "source_candidate_label": None, "final_label": "UNKNOWN"}],
    })
    assert unknown_label.status_code == 422
    assert put(client, project, metadata, chunk_id, "0" * 64, [accept(source)]).status_code == 409
    assert put(client, project, metadata, "CHK-FFFFFFFFFFFFFFFFFFFF",
               review["review_fingerprint"], [accept(source)]).status_code == 422


def test_stale_hybrid_and_review_policy_return_fresh_unapplied_state(zero_context, monkeypatch):
    authentication, _, root, _ = zero_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    initial = state(client, project, metadata)
    item = initial["review_queue"][0]
    assert put(client, project, metadata, item["chunk"]["chunk_id"],
               initial["review"]["review_fingerprint"],
               [accept(item["hybrid"]["candidates"][0]["label"])]).status_code == 200
    monkeypatch.setattr(constants, "HUMAN_REVIEW_POLICY_VERSION", "2")
    stale = state(client, project, metadata)
    assert stale["stale"] is True
    assert stale["stale_message"] == "Artifact analysis changed. Human verification must be performed again."
    assert stale["review"]["review_status"] == "NOT_STARTED"
    assert stale["review"]["chunks"][0]["verified_labels"] == []
    old = put(client, project, metadata, item["chunk"]["chunk_id"],
              initial["review"]["review_fingerprint"],
              [accept(item["hybrid"]["candidates"][0]["label"])] )
    assert old.status_code == 409
    assert old.json()["errors"][0]["message"] == "STALE_HUMAN_REVIEW"

    monkeypatch.setattr(constants, "HUMAN_REVIEW_POLICY_VERSION", "1")
    directory = upload_dir(root, project["agent_project_id"])
    hybrid_path = directory / f'{metadata["upload_id"]}.hybrid-detections.json'
    payload = json.loads(hybrid_path.read_text(encoding="utf-8"))
    payload["created_at"] = "2026-10-18T16:00:00Z"
    hybrid_path.write_text(json.dumps(payload), encoding="utf-8")
    changed = state(client, project, metadata)
    assert changed["stale"] is True
    assert changed["review"]["review_fingerprint"] != initial["review"]["review_fingerprint"]


def test_fingerprint_changes_for_chunk_hash():
    class Chunk:
        def __init__(self, text_hash):
            self.chunk_id = "CHK-0123456789ABCDEF0123"
            self.text_hash = text_hash

    pipeline = {
        "extraction_version": "1", "chunker_version": "1",
        "rule_detector_version": "1", "zero_shot_classifier_version": "1",
        "zero_shot_model_id": "model", "zero_shot_model_revision": "rev",
        "zero_shot_label_map_version": "1", "hybrid_decision_version": "1",
        "hybrid_policy_version": "1", "human_review_schema_version": "1",
        "human_review_policy_version": "1",
    }
    from app.modules.agents.implementation.preparation.human_review.schemas import HumanReviewPipelineIdentity
    identity = HumanReviewPipelineIdentity(**pipeline)
    first = HumanReviewService._fingerprint("a" * 64, identity, "b" * 64, "c" * 64, "d" * 64, [Chunk("e" * 64)])
    second = HumanReviewService._fingerprint("a" * 64, identity, "b" * 64, "c" * 64, "d" * 64, [Chunk("f" * 64)])
    assert first != second


def test_research_review_priority_order_is_deterministic():
    from app.modules.agents.implementation.preparation.hybrid.schemas import HybridDecisionState, HybridEvidenceState

    def hybrid(*, evidence=HybridEvidenceState.RULE_AND_MODEL,
               decision=HybridDecisionState.AUTO_CANDIDATE,
               explosion=False, ambiguous=False):
        return SimpleNamespace(
            candidates=[SimpleNamespace(evidence_state=evidence, decision=decision)],
            diagnostics=SimpleNamespace(
                model_label_explosion=explosion, model_ambiguous=ambiguous,
            ),
        )

    priorities = [
        HumanReviewService._priority(hybrid(evidence=HybridEvidenceState.RULE_MODEL_DISAGREEMENT)),
        HumanReviewService._priority(hybrid(explosion=True)),
        HumanReviewService._priority(hybrid(ambiguous=True)),
        HumanReviewService._priority(hybrid(decision=HybridDecisionState.REVIEW_REQUIRED)),
        HumanReviewService._priority(hybrid()),
        HumanReviewService._priority(hybrid(evidence=HybridEvidenceState.INSUFFICIENT_EVIDENCE,
                                             decision=HybridDecisionState.REJECTED)),
    ]
    assert priorities == [1, 2, 3, 4, 5, 6]


def test_foreign_archived_deletion_and_openapi(zero_context):
    authentication, _, root, _ = zero_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project, metadata = prepare_hybrid(owner)
    assert foreign.get(review_url(project["agent_project_id"], metadata["upload_id"])).status_code == 404
    wrong = create_project(owner, "DESIGN_PLANNING")
    assert owner.get(review_url(wrong["agent_project_id"], metadata["upload_id"])).status_code == 422
    initial = state(owner, project, metadata)
    item = initial["review_queue"][0]
    put(owner, project, metadata, item["chunk"]["chunk_id"],
        initial["review"]["review_fingerprint"],
        [accept(item["hybrid"]["candidates"][0]["label"])] )
    sidecar = upload_dir(root, project["agent_project_id"]) / f'{metadata["upload_id"]}.human-reviews.json'
    assert sidecar.exists()
    owner.patch(f'/api/v1/agent-projects/{project["agent_project_id"]}', json={"status": "ARCHIVED"})
    assert owner.get(review_url(project["agent_project_id"], metadata["upload_id"])).status_code == 409
    owner.patch(f'/api/v1/agent-projects/{project["agent_project_id"]}', json={"status": "ACTIVE"})
    assert owner.delete(f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}').status_code == 200
    assert not sidecar.exists()
    paths = app.openapi()["paths"]
    base = "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/human-reviews"
    assert set(paths[base]) == {"get"}
    assert set(paths[f"{base}/{{chunk_id}}"] ) == {"put"}
    forbidden = ("dataset-export", "fine-tun", "structured-artifact", "agent-run", "code-generation", "image-understanding")
    agent_paths = [path for path in paths if path.startswith("/api/v1/agents/implementation")]
    assert not any(any(term in path for term in forbidden) for path in agent_paths)
