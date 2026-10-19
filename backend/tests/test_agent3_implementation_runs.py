from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.common.status import AgentRunStatus, AgentType
from app.modules.agents.implementation.contracts.enums import ImplementationOutputCode
from app.modules.agents.implementation.preparation.consolidation.constants import (
    ConflictAction,
    ConflictStatus,
    ConsolidationSourceKind,
    ConsolidationStatus,
)
from app.modules.agents.implementation.preparation.consolidation.schemas import (
    ConflictCandidate,
    ProjectConflict,
    ProjectSourceRef,
    ProjectSpecificationItem,
    TrustedProjectSpecification,
)
from app.modules.agents.implementation.preparation.readiness.trusted.policy import digest
from app.modules.agents.implementation.preparation.readiness.schemas import (
    ReadinessStatus,
)
from app.modules.agents.implementation.preparation.readiness.trusted.schemas import (
    TrustedReadinessContinuationRequest,
    TrustedReadinessEvaluationRequest,
)
from app.modules.agents.implementation.preparation.readiness.trusted.service import (
    TrustedReadinessService,
    readiness_fingerprint,
)
from app.modules.agents.implementation.preparation.readiness.trusted.storage import (
    TrustedReadinessStorage,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel as A,
)
from app.modules.agents.implementation.runs.schemas import (
    ImplementationRunCreateRequest,
)
from app.modules.agents.implementation.runs.service import (
    ImplementationRunApprovalError,
    ImplementationRunNotFoundError,
    ImplementationRunService,
    ImplementationRunStorageError,
)
from app.modules.standalone.schemas import AgentRun
from app.modules.standalone.service import AgentProjectNotFoundError


NOW = datetime(2026, 10, 19, 7, 10, tzinfo=timezone.utc)
PROJECT_ID = "AGP-003"
OWNER_ID = "USR-001"
USER = SimpleNamespace(user_id=OWNER_ID)


def source_ref(suffix="A"):
    return ProjectSourceRef(
        source_id=f"SRC-{suffix}",
        source_kind=ConsolidationSourceKind.TEXT,
        label=f"Source {suffix}",
        source_fingerprint=suffix.lower() * 64,
        final_artifact_id=f"FTA-{suffix * 24}",
    )


def project_item(category=A.FUNCTIONAL_REQUIREMENTS, suffix="A", data=None):
    ref = source_ref(suffix)
    return ProjectSpecificationItem(
        project_item_id=f"PSI-{suffix * 24}",
        artifact_type=category,
        identity_key=suffix.lower() * 64,
        data=data or {"statement": suffix},
        supporting_sources=[ref],
        source_artifact_ids=[ref.final_artifact_id],
    )


def specification(categories=None, conflicts=None):
    source_digest = "b" * 64
    decision_digest = "c" * 64
    specification_id = "TPS-" + digest(
        [PROJECT_ID, source_digest, decision_digest]
    )[:24].upper()
    items = (
        {A.FUNCTIONAL_REQUIREMENTS: [project_item()]}
        if categories is None
        else categories
    )
    return TrustedProjectSpecification(
        project_specification_id=specification_id,
        agent_project_id=PROJECT_ID,
        status=ConsolidationStatus.READY,
        categories=items,
        relationships=[],
        source_artifact_refs=[
            artifact_id
            for values in items.values()
            for item in values
            for artifact_id in item.source_artifact_ids
        ],
        conflict_decisions=conflicts or [],
        traceability={
            item.project_item_id: item.supporting_sources
            for values in items.values()
            for item in values
        },
        source_set_digest=source_digest,
        decision_digest=decision_digest,
        schema_version="1",
        created_at=NOW,
    )


class FakeConsolidation:
    def __init__(self, final):
        self.final = final
        self.status = ConsolidationStatus.READY
        self.source_set_digest = final.source_set_digest

    def get_status(self, *_):
        return SimpleNamespace(
            status=self.status, source_set_digest=self.source_set_digest
        )

    def get_final(self, *_):
        return self.final


class FakeStandalone:
    def __init__(self):
        self.runs = []
        self.create_calls = 0

    def require_active_project(self, owner_id, project_id):
        if owner_id != OWNER_ID or project_id != PROJECT_ID:
            raise AgentProjectNotFoundError(project_id)
        return SimpleNamespace(
            agent_project_id=project_id,
            owner_user_id=owner_id,
            agent_type=AgentType.IMPLEMENTATION,
        )

    def create_run(self, owner_id, project_id, run_mode, selected_outputs, input_snapshot):
        self.require_active_project(owner_id, project_id)
        self.create_calls += 1
        run = AgentRun(
            run_id=f"RUN-{len(self.runs) + 1:03d}",
            agent_project_id=project_id,
            owner_user_id=owner_id,
            agent_type=AgentType.IMPLEMENTATION,
            run_mode=run_mode,
            selected_outputs=deepcopy(selected_outputs),
            input_snapshot=deepcopy(input_snapshot),
            status=AgentRunStatus.QUEUED,
            created_at=NOW,
        )
        self.runs.append(run)
        return run.model_copy(deep=True)

    def list_runs(self, project_id, current_user):
        self.require_active_project(current_user.user_id, project_id)
        return [run.model_copy(deep=True) for run in reversed(self.runs)]

    def get_run(self, project_id, run_id, current_user):
        self.require_active_project(current_user.user_id, project_id)
        for run in self.runs:
            if run.run_id == run_id:
                return run.model_copy(deep=True)
        raise LookupError(run_id)


class FakeReadiness:
    def __init__(self, value):
        self.value = value

    def get(self, *_):
        return self.value

    def valid_continuation(self, *_):
        return None


class FakeRepository:
    def __init__(self, value=None):
        self.value = value

    def find_by_owner(self, *_):
        return deepcopy(self.value)

    def find_by_project(self, *_):
        return deepcopy(self.value)


def evaluated_readiness(tmp_path, final, output=ImplementationOutputCode.GIT_SUMMARY):
    consolidation = FakeConsolidation(final)
    readiness_service = TrustedReadinessService(
        FakeStandalone(),
        consolidation,
        TrustedReadinessStorage(tmp_path),
        clock=lambda: NOW,
    )
    value = readiness_service.evaluate(
        PROJECT_ID,
        TrustedReadinessEvaluationRequest(selected_outputs=[output]),
        USER,
    )
    return value, consolidation


def harness(tmp_path, *, output=ImplementationOutputCode.GIT_SUMMARY, final=None, connection=None, binding=None):
    final = final or specification()
    readiness, consolidation = evaluated_readiness(tmp_path, final, output)
    standalone = FakeStandalone()
    service = ImplementationRunService(
        standalone,
        consolidation,
        FakeReadiness(readiness),
        FakeRepository(connection),
        FakeRepository(binding),
        clock=lambda: NOW,
    )
    return service, standalone, consolidation, readiness


def request(readiness, **updates):
    values = {
        "approved": True,
        "acknowledged_warning_codes": [],
        "idempotency_key": "approval-request-001",
        "expected_project_specification_id": readiness.project_specification_id,
        "expected_readiness_id": readiness.readiness_id,
        "expected_readiness_fingerprint": readiness.readiness_fingerprint,
        "expected_selected_outputs_digest": readiness.selected_outputs_digest,
        "expected_stack_adaptation_fingerprint": (
            readiness.stack_adaptation.fingerprint
            if readiness.stack_adaptation
            else None
        ),
    }
    values.update(updates)
    return ImplementationRunCreateRequest.model_validate(values)


def create(service, readiness, **updates):
    return service.create(PROJECT_ID, request(readiness, **updates), USER)[0]


def test_ready_creates_shared_agent_run_with_immutable_approved_snapshot(tmp_path):
    service, standalone, _, readiness = harness(tmp_path)
    result = create(service, readiness)
    assert result.run_status == "READY_FOR_GENERATION"
    assert standalone.runs[0].status is AgentRunStatus.QUEUED
    assert result.approved_input.trusted_project_specification.project_specification_id == result.project_specification_id
    assert result.approved_input.trusted_readiness.readiness_id == result.readiness_id
    assert standalone.create_calls == 1
    assert standalone.runs[0].output_manifest == {}
    approval = result.approved_input.approval
    assert approval.reviewer_owner_id == OWNER_ID
    assert approval.decision == "APPROVED"
    assert approval.project_specification_source_set_digest == "b" * 64
    assert approval.project_specification_decision_digest == "c" * 64
    assert approval.readiness_fingerprint == readiness.readiness_fingerprint
    assert approval.approval_id.startswith("APR-")
    assert len(approval.approval_fingerprint) == 64


def test_ready_with_warnings_requires_exact_current_acknowledgement(tmp_path):
    final = specification({A.FUNCTIONAL_REQUIREMENTS: [project_item()]})
    service, standalone, _, readiness = harness(
        tmp_path, output=ImplementationOutputCode.FRONTEND_CODE, final=final
    )
    warning_codes = sorted(
        item.issue_code for item in readiness.findings if not item.resolved
    )
    assert readiness.status == "READY_WITH_WARNINGS"
    with pytest.raises(ImplementationRunApprovalError, match="acknowledged"):
        create(service, readiness)
    with pytest.raises(ImplementationRunApprovalError, match="acknowledged"):
        create(service, readiness, acknowledged_warning_codes=["OLD_WARNING"])
    result = create(
        service, readiness, acknowledged_warning_codes=warning_codes
    )
    assert result.approved_input.approval.acknowledged_warning_codes == warning_codes


def test_persisted_warning_continuation_avoids_duplicate_run_acknowledgement(tmp_path):
    final = specification({A.FUNCTIONAL_REQUIREMENTS: [project_item()]})
    consolidation = FakeConsolidation(final)
    readiness_service = TrustedReadinessService(
        FakeStandalone(), consolidation, TrustedReadinessStorage(tmp_path),
        clock=lambda: NOW,
    )
    readiness = readiness_service.evaluate(
        PROJECT_ID,
        TrustedReadinessEvaluationRequest(
            selected_outputs=[ImplementationOutputCode.FRONTEND_CODE]
        ),
        USER,
    )
    warning_codes = sorted(
        item.issue_code for item in readiness.findings if not item.resolved
    )
    continued = readiness_service.continue_with_warnings(
        PROJECT_ID,
        TrustedReadinessContinuationRequest(
            expected_readiness_id=readiness.readiness_id,
            expected_readiness_fingerprint=readiness.readiness_fingerprint,
            acknowledged_warning_codes=warning_codes,
        ),
        USER,
    )
    standalone = FakeStandalone()
    service = ImplementationRunService(
        standalone, consolidation, readiness_service,
        FakeRepository(), FakeRepository(), clock=lambda: NOW,
    )
    run = create(service, continued, acknowledged_warning_codes=[])
    assert run.approved_input.approval.acknowledged_warning_codes == warning_codes
    assert (
        run.approved_input.approval.readiness_continuation_decision_id
        == continued.continuation_decision_id
    )
    assert standalone.create_calls == 1


def test_not_ready_and_stale_readiness_are_blocked(tmp_path):
    service, standalone, _, readiness = harness(tmp_path)
    not_ready = readiness.model_copy(update={"status": ReadinessStatus.NOT_READY})
    not_ready = not_ready.model_copy(
        update={"readiness_fingerprint": readiness_fingerprint(not_ready)}
    )
    service._readiness.value = not_ready
    with pytest.raises(ImplementationRunApprovalError, match="not ready"):
        create(service, not_ready)
    service._readiness.value = readiness.model_copy(update={"current": False})
    with pytest.raises(ImplementationRunApprovalError, match="stale"):
        create(service, readiness)
    assert standalone.create_calls == 0


def test_stale_specification_selected_outputs_and_stack_are_blocked(tmp_path):
    service, standalone, consolidation, readiness = harness(tmp_path)
    with pytest.raises(ImplementationRunApprovalError, match="specification changed"):
        create(service, readiness, expected_project_specification_id="TPS-" + "F" * 24)
    with pytest.raises(ImplementationRunApprovalError, match="Selected outputs"):
        create(service, readiness, expected_selected_outputs_digest="0" * 64)
    with pytest.raises(ImplementationRunApprovalError, match="stack adaptation"):
        create(service, readiness, expected_stack_adaptation_fingerprint="0" * 64)
    consolidation.source_set_digest = "d" * 64
    with pytest.raises(ImplementationRunApprovalError, match="stale"):
        create(service, readiness)
    assert standalone.create_calls == 0


def test_unresolved_consolidation_conflict_blocks_run(tmp_path):
    item = project_item()
    ref = item.supporting_sources[0]
    conflict = ProjectConflict(
        conflict_id="PCF-" + "A" * 24,
        conflict_type="VALUE_CONFLICT",
        artifact_type=A.FUNCTIONAL_REQUIREMENTS,
        candidates=[
            ConflictCandidate(candidate_id="PCC-" + "A" * 24, label="A", value="one", project_item_ids=[item.project_item_id], supporting_sources=[ref]),
            ConflictCandidate(candidate_id="PCC-" + "B" * 24, label="B", value="two", project_item_ids=[item.project_item_id], supporting_sources=[ref]),
        ],
        status=ConflictStatus.PENDING,
        allowed_actions=[ConflictAction.KEEP_BOTH],
        fingerprint="e" * 64,
    )
    final = specification({A.FUNCTIONAL_REQUIREMENTS: [item]}, [conflict])
    service, standalone, _, readiness = harness(tmp_path, final=final)
    with pytest.raises(ImplementationRunApprovalError, match="conflicts"):
        create(service, readiness)
    assert standalone.create_calls == 0


def test_existing_run_is_reproducible_and_unchanged_after_live_project_changes(tmp_path):
    item = project_item()
    final = specification({A.FUNCTIONAL_REQUIREMENTS: [item]})
    service, standalone, consolidation, readiness = harness(tmp_path, final=final)
    first = create(service, readiness)
    original = first.model_dump(mode="json")
    consolidation.final = specification({A.API_SPECIFICATION: [project_item(A.API_SPECIFICATION, "B")]})
    service._readiness.value = readiness.model_copy(update={"current": False})
    assert service.get(PROJECT_ID, first.run_id, USER).model_dump(mode="json") == original
    assert first.approved_input.trusted_project_specification.categories[A.FUNCTIONAL_REQUIREMENTS][0].project_item_id == item.project_item_id
    assert first.approved_input.trusted_readiness.readiness_fingerprint == readiness.readiness_fingerprint
    assert standalone.runs[0].input_snapshot == first.approved_input.model_dump(mode="json")


def test_new_current_state_can_create_an_intentional_later_run(tmp_path):
    service, standalone, _, readiness = harness(tmp_path)
    first = create(service, readiness)
    second = create(service, readiness, idempotency_key="approval-request-002")
    assert first.run_id != second.run_id
    assert standalone.create_calls == 2


def test_idempotency_replays_once_but_key_cannot_approve_different_state(tmp_path):
    service, standalone, _, readiness = harness(tmp_path)
    first, replayed = service.create(PROJECT_ID, request(readiness), USER)
    assert replayed is False
    second, replayed = service.create(PROJECT_ID, request(readiness), USER)
    assert replayed is True
    assert first.run_id == second.run_id
    assert standalone.create_calls == 1
    with pytest.raises(ImplementationRunApprovalError, match="idempotency key"):
        service.create(
            PROJECT_ID,
            request(readiness, expected_selected_outputs_digest="0" * 64),
            USER,
        )


def test_safe_delivery_metadata_is_snapshotted_without_credentials(tmp_path):
    connection = {
        "owner_id": OWNER_ID,
        "provider": "GITHUB",
        "github_user_id": 41,
        "github_login": "octocat",
        "github_avatar_url": "https://example.test/avatar.png",
        "installation_id": 77,
        "installation_account_id": 41,
        "installation_account_login": "octocat",
        "installation_account_type": "User",
        "status": "CONNECTED",
        "connected_at": NOW,
        "updated_at": NOW,
    }
    binding = {
        "agent_project_id": PROJECT_ID,
        "owner_id": OWNER_ID,
        "github_connection_owner_id": OWNER_ID,
        "repository_id": 99,
        "repository_owner": "octocat",
        "repository_name": "agile-flow",
        "repository_full_name": "octocat/agile-flow",
        "repository_html_url": "https://github.com/octocat/agile-flow",
        "visibility": "PRIVATE",
        "private": True,
        "default_branch": "main",
        "is_empty": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    service, _, _, readiness = harness(
        tmp_path, connection=connection, binding=binding
    )
    result = create(service, readiness)
    delivery = result.delivery_snapshot
    assert delivery.configured is True
    assert delivery.repository.full_name == "octocat/agile-flow"
    serialized = result.model_dump_json().lower()
    assert "token" not in serialized
    assert "private_key" not in serialized
    assert "installation_id" not in serialized
    forbidden_keys = {
        "access_token", "oauth_token", "installation_token", "private_key",
        "authorization", "code_verifier", "client_secret", "secret",
    }

    def keys(value):
        if isinstance(value, dict):
            return set(value) | {key for item in value.values() for key in keys(item)}
        if isinstance(value, list):
            return {key for item in value for key in keys(item)}
        return set()

    assert not (keys(result.model_dump(mode="json")) & forbidden_keys)


def test_no_github_does_not_block_generation_approval(tmp_path):
    service, _, _, readiness = harness(tmp_path)
    result = create(service, readiness)
    assert result.delivery_snapshot.configured is False
    assert result.delivery_snapshot.delivery_ready is False
    assert result.delivery_snapshot.required_before_delivery_execution is True


def test_list_get_ownership_traceability_and_malformed_snapshot_safety(tmp_path):
    item = project_item()
    final = specification({A.FUNCTIONAL_REQUIREMENTS: [item]})
    service, standalone, _, readiness = harness(tmp_path, final=final)
    created = create(service, readiness)
    history = service.list(PROJECT_ID, USER)
    assert [entry.run_id for entry in history] == [created.run_id]
    loaded = service.get(PROJECT_ID, created.run_id, USER)
    assert item.project_item_id in loaded.traceability_root_refs
    assert item.source_artifact_ids[0] in loaded.traceability_root_refs
    with pytest.raises((LookupError, ImplementationRunNotFoundError)):
        service.get(PROJECT_ID, created.run_id, SimpleNamespace(user_id="USR-002"))
    malformed = standalone.runs[0].model_copy(
        update={
            "run_id": "RUN-999",
            "input_snapshot": {"snapshot_kind": "IMPLEMENTATION_APPROVED_INPUT"},
        }
    )
    standalone.runs.append(malformed)
    with pytest.raises(ImplementationRunStorageError):
        service.get(PROJECT_ID, "RUN-999", USER)
    with pytest.raises(ImplementationRunStorageError):
        service.list(PROJECT_ID, USER)


def test_run_r1_openapi_is_create_list_get_only():
    from app.main import app

    collection = "/api/v1/agents/implementation/{agent_project_id}/runs"
    item = collection + "/{run_id}"
    paths = app.openapi()["paths"]
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    assert "patch" not in paths[item]


def test_run_routes_create_list_get_and_enforce_owner(
    tmp_path, authentication_context
):
    from app.main import app
    from app.modules.agents.implementation.api.dependencies import (
        get_implementation_run_service,
    )

    service, _, _, readiness = harness(tmp_path)
    app.dependency_overrides[get_implementation_run_service] = lambda: service
    try:
        client = authentication_context.client()
        payload = request(readiness).model_dump(mode="json")
        created = client.post(
            f"/api/v1/agents/implementation/{PROJECT_ID}/runs", json=payload
        )
        assert created.status_code == 201
        run_id = created.json()["data"]["run_id"]
        assert created.json()["data"]["run_status"] == "READY_FOR_GENERATION"

        history = client.get(
            f"/api/v1/agents/implementation/{PROJECT_ID}/runs"
        )
        assert history.status_code == 200
        assert [item["run_id"] for item in history.json()["data"]] == [run_id]

        loaded = client.get(
            f"/api/v1/agents/implementation/{PROJECT_ID}/runs/{run_id}"
        )
        assert loaded.status_code == 200
        assert loaded.json()["data"]["approval_id"].startswith("APR-")

        foreign = authentication_context.client("USR-002").get(
            f"/api/v1/agents/implementation/{PROJECT_ID}/runs/{run_id}"
        )
        assert foreign.status_code == 404
        wrong_project = client.get(
            f"/api/v1/agents/implementation/AGP-999/runs/{run_id}"
        )
        assert wrong_project.status_code == 404
    finally:
        app.dependency_overrides.pop(get_implementation_run_service, None)
