import hashlib
import json
import time
from datetime import datetime, timezone

import pytest

from app.main import app
from app.modules.agents.implementation.api.dependencies import (
    get_project_preparation_storage,
    get_project_specification_storage,
)
from app.modules.agents.implementation.preparation.orchestration.storage import (
    ProjectPreparationStorage,
)
from app.modules.agents.implementation.preparation.orchestration.constants import (
    PreparationStage,
    ProjectPreparationStatus,
    SourcePreparationStatus,
)
from app.modules.agents.implementation.preparation.orchestration.schemas import (
    PersistedPreparationSource,
    ProjectPreparationRecord,
)
from app.modules.agents.implementation.preparation.specification.constants import (
    ProjectSpecificationStatus,
    SourceSpecificationStatus,
)
from app.modules.agents.implementation.preparation.specification.schemas import (
    SpecificationSourceState,
)
from app.modules.agents.implementation.preparation.specification.service import (
    derive_specification_status,
)
from app.modules.agents.implementation.preparation.specification.storage import (
    ProjectSpecificationStorage,
)
from test_agent3_canonical_artifacts import _complete_review
from test_agent3_document_extraction import extraction_context, upload_dir  # noqa: F401
from test_agent3_human_review import prepare_hybrid
from test_agent3_semantic_artifacts import (
    prepare_canonical,
    semantic_context,
    semantic_url,
)
from test_agent3_zero_shot_detection import zero_context  # noqa: F401


@pytest.fixture
def wf2_context(semantic_context):
    root = semantic_context[2]
    app.dependency_overrides[get_project_preparation_storage] = (
        lambda: ProjectPreparationStorage(root)
    )
    app.dependency_overrides[get_project_specification_storage] = (
        lambda: ProjectSpecificationStorage(root)
    )
    try:
        yield semantic_context
    finally:
        app.dependency_overrides.pop(get_project_preparation_storage, None)
        app.dependency_overrides.pop(get_project_specification_storage, None)


def specification_url(project_id):
    return f"/api/v1/agents/implementation/{project_id}/specification"


def semantic_review_url(project_id, upload_id):
    return (
        f"/api/v1/agents/implementation/{project_id}/input-files/"
        f"{upload_id}/semantic-reviews"
    )


def wait_for_status(client, project_id, terminal, timeout=5):
    deadline = time.monotonic() + timeout
    response = None
    while time.monotonic() < deadline:
        response = client.get(f"{specification_url(project_id)}/status")
        assert response.status_code == 200
        if response.json()["data"]["status"] in terminal:
            return response.json()["data"]
        time.sleep(0.02)
    raise AssertionError(f"Specification did not reach {terminal}: {response.text}")


def test_incomplete_review_blocks_then_builds_semantic_review_and_trusted_output(
    wf2_context,
):
    authentication, _, root, _, _, _ = wf2_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    project_id = project["agent_project_id"]
    upload_id = metadata["upload_id"]

    response = client.post(f"{specification_url(project_id)}/start")
    assert response.status_code == 202
    assert response.json()["data"]["status"] == "WAITING_FOR_ARTIFACT_REVIEW"

    _complete_review(client, project, metadata)
    response = client.post(f"{specification_url(project_id)}/start")
    assert response.status_code == 202
    status = wait_for_status(
        client,
        project_id,
        {"WAITING_FOR_SEMANTIC_REVIEW", "SPECIFICATION_READY"},
    )
    assert status["failed_source_count"] == 0

    directory = upload_dir(root, project_id)
    canonical_path = directory / f"{upload_id}.canonical-artifacts.json"
    canonical_digest = hashlib.sha256(canonical_path.read_bytes()).hexdigest()

    if status["status"] == "WAITING_FOR_SEMANTIC_REVIEW":
        review_url = semantic_review_url(project_id, upload_id)
        review = client.get(review_url)
        assert review.status_code == 200
        state = review.json()["data"]
        assert state["items"]
        assert all(item["evidence"] for item in state["items"])
        assert "source_text" not in json.dumps(state).casefold()

        invalid = client.put(
            f"{review_url}/SRD-000000000000000000000000",
            json={
                "action": "APPROVE_ADDITION",
                "expected_review_fingerprint": state["review_fingerprint"],
            },
        )
        assert invalid.status_code == 404

        for item in state["items"]:
            action = (
                "APPROVE_ADDITION"
                if "APPROVE_ADDITION" in item["allowed_actions"]
                else "KEEP_DETERMINISTIC"
            )
            saved = client.put(
                f"{review_url}/{item['decision_id']}",
                json={
                    "action": action,
                    "expected_review_fingerprint": state["review_fingerprint"],
                },
            )
            assert saved.status_code == 200
            state = saved.json()["data"]

        status = wait_for_status(client, project_id, {"SPECIFICATION_READY"})

    assert status["status"] == "SPECIFICATION_READY"
    trusted = client.get(
        f"/api/v1/agents/implementation/{project_id}/input-files/"
        f"{upload_id}/trusted-artifacts"
    )
    assert trusted.status_code == 200
    payload = trusted.json()["data"]
    assert payload["canonical_artifact_digest"] == canonical_digest
    assert all(item["status"] == "TRUSTED" for item in payload["artifacts"])
    assert all(
        decision["reviewer_owner_id"] == "USR-001"
        for artifact in payload["artifacts"]
        for decision in artifact["human_decisions"]
    )
    assert all(
        field["origin"] in {
            "DETERMINISTIC",
            "SEMANTIC_HUMAN_APPROVED",
            "SEMANTIC_HUMAN_OVERRIDE",
        }
        for artifact in payload["artifacts"]
        for field in artifact["field_provenance"]
    )
    assert hashlib.sha256(canonical_path.read_bytes()).hexdigest() == canonical_digest
    assert "file_path" not in trusted.text.casefold()

    canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    canonical_payload["warnings"].append("STALE_FINAL_TEST")
    canonical_path.write_text(json.dumps(canonical_payload), encoding="utf-8")
    stale = client.get(
        f"/api/v1/agents/implementation/{project_id}/input-files/"
        f"{upload_id}/trusted-artifacts"
    )
    assert stale.status_code == 404


def test_completed_artifact_review_automatically_continues_a_wf1_project(
    wf2_context,
):
    authentication, _, root, _, _, _ = wf2_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    now = datetime.now(timezone.utc)
    ProjectPreparationStorage(root).save(ProjectPreparationRecord(
        agent_project_id=project_id,
        owner_user_id="USR-001",
        status=ProjectPreparationStatus.WAITING_FOR_HUMAN,
        sources=[PersistedPreparationSource(
            source_id=upload_id,
            source_kind=metadata["source_type"],
            artifact_type=metadata["artifact_type"],
            label=metadata["label"],
            filename=metadata["original_filename"],
            status=SourcePreparationStatus.WAITING_FOR_HUMAN,
            current_stage=PreparationStage.HUMAN_REVIEW,
        )],
        started_at=now,
        updated_at=now,
    ))

    _complete_review(client, project, metadata)
    status = wait_for_status(
        client,
        project_id,
        {"WAITING_FOR_SEMANTIC_REVIEW", "SPECIFICATION_READY"},
    )
    assert status["status"] in {
        "WAITING_FOR_SEMANTIC_REVIEW", "SPECIFICATION_READY",
    }


def test_grounded_additions_can_be_rejected_without_changing_the_baseline(
    wf2_context,
):
    authentication, _, root, _, _, _ = wf2_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    _complete_review(client, project, metadata)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    assert client.post(f"{specification_url(project_id)}/start").status_code == 202
    status = wait_for_status(
        client, project_id,
        {"WAITING_FOR_SEMANTIC_REVIEW", "SPECIFICATION_READY"},
    )
    if status["status"] == "SPECIFICATION_READY":
        return

    directory = upload_dir(root, project_id)
    canonical_path = directory / f"{upload_id}.canonical-artifacts.json"
    canonical_before = canonical_path.read_bytes()
    review_url = semantic_review_url(project_id, upload_id)
    state = client.get(review_url).json()["data"]
    assert any(
        "REJECT_ADDITION" in item["allowed_actions"]
        for item in state["items"]
    )
    for item in state["items"]:
        action = (
            "REJECT_ADDITION"
            if "REJECT_ADDITION" in item["allowed_actions"]
            else "KEEP_DETERMINISTIC"
        )
        response = client.put(
            f"{review_url}/{item['decision_id']}",
            json={
                "action": action,
                "expected_review_fingerprint": state["review_fingerprint"],
            },
        )
        assert response.status_code == 200
        state = response.json()["data"]
    final = client.get(
        f"/api/v1/agents/implementation/{project_id}/input-files/"
        f"{upload_id}/trusted-artifacts"
    ).json()["data"]
    decisions = [
        decision["decision"]
        for artifact in final["artifacts"]
        for decision in artifact["human_decisions"]
    ]
    assert "REJECT_ADDITION" in decisions
    assert canonical_path.read_bytes() == canonical_before


def test_keep_deterministic_and_explicit_semantic_override_are_versioned(
    wf2_context,
):
    authentication, _, root, _, _, _ = wf2_context
    client = authentication.client()
    project, metadata, _ = prepare_canonical(client)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    assert client.post(semantic_url(project_id, upload_id)).status_code == 200

    sidecar = upload_dir(root, project_id) / f"{upload_id}.semantic-artifacts.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    target = next(
        result for result in payload["results"]
        if result["artifact_type"] == "API_SPECIFICATION"
        and result["merged_preview"] is not None
    )
    evidence = next(
        item["evidence"] for item in target["merged_preview"]["field_provenance"]
        if item["evidence"]
    )
    target["merged_preview"]["conflicts"].append({
        "code": "SEMANTIC_DETERMINISTIC_CONFLICT",
        "field_path": "endpoints[0].method",
        "deterministic_value": "POST",
        "semantic_value": "POST",
        "semantic_evidence": evidence,
    })
    target["merged_preview"]["status"] = "HUMAN_REVIEW_REQUIRED"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    review_url = semantic_review_url(project_id, upload_id)
    state = client.get(review_url).json()["data"]
    conflict = next(item for item in state["items"] if item["kind"] == "CONFLICT")
    for item in state["items"]:
        action = (
            "KEEP_DETERMINISTIC"
            if item["decision_id"] == conflict["decision_id"]
            else "REJECT_ADDITION"
        )
        response = client.put(
            f"{review_url}/{item['decision_id']}",
            json={"action": action,
                  "expected_review_fingerprint": state["review_fingerprint"]},
        )
        assert response.status_code == 200
        state = response.json()["data"]

    final_url = (
        f"/api/v1/agents/implementation/{project_id}/input-files/"
        f"{upload_id}/trusted-artifacts"
    )
    kept = client.get(final_url).json()["data"]
    response = client.put(
        f"{review_url}/{conflict['decision_id']}",
        json={
            "action": "ACCEPT_SEMANTIC_OVERRIDE",
            "expected_review_fingerprint": state["review_fingerprint"],
        },
    )
    assert response.status_code == 200
    overridden = client.get(final_url).json()["data"]
    assert overridden["human_decision_digest"] != kept["human_decision_digest"]
    provenance = [
        field
        for artifact in overridden["artifacts"]
        if artifact["artifact_type"] == "API_SPECIFICATION"
        for field in artifact["field_provenance"]
        if field["field_path"] == "endpoints[0].method"
    ]
    assert provenance[0]["origin"] == "SEMANTIC_HUMAN_OVERRIDE"


def test_specification_status_precedence_and_openapi():
    source = lambda state: SpecificationSourceState(
        source_id=f"A3UP-{'a' * 32}",
        filename="requirements.pdf",
        status=state,
    )
    assert derive_specification_status([]) is ProjectSpecificationStatus.NOT_STARTED
    assert derive_specification_status([
        source(SourceSpecificationStatus.BUILDING_CANONICAL)
    ]) is ProjectSpecificationStatus.PREPARING_SPECIFICATION
    assert derive_specification_status([
        source(SourceSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW)
    ]) is ProjectSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW
    assert derive_specification_status([
        source(SourceSpecificationStatus.WAITING_FOR_SEMANTIC_REVIEW)
    ]) is ProjectSpecificationStatus.WAITING_FOR_SEMANTIC_REVIEW
    assert derive_specification_status([
        source(SourceSpecificationStatus.READY)
    ]) is ProjectSpecificationStatus.SPECIFICATION_READY

    paths = app.openapi()["paths"]
    project = "/api/v1/agents/implementation/{agent_project_id}"
    source_path = project + "/input-files/{upload_id}"
    assert set(paths[project + "/specification/start"]) == {"post"}
    assert set(paths[project + "/specification/status"]) == {"get"}
    assert set(paths[source_path + "/semantic-reviews"]) == {"get"}
    assert set(paths[
        source_path + "/semantic-reviews/{decision_id}"
    ]) == {"put"}
    assert set(paths[source_path + "/trusted-artifacts"]) == {"get"}
