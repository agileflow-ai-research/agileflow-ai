from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.common.status import AgentType
from app.modules.agents.implementation.contracts.enums import ImplementationOutputCode
from app.modules.agents.implementation.preparation.consolidation.constants import (
    ConsolidationSourceKind,
    ConsolidationStatus,
)
from app.modules.agents.implementation.preparation.consolidation.schemas import (
    ProjectSourceRef,
    ProjectSpecificationItem,
    TrustedProjectSpecification,
)
from app.modules.agents.implementation.preparation.readiness.trusted.constants import TRUSTED_READINESS_POLICY_VERSION
from app.modules.agents.implementation.preparation.readiness.trusted.policy import digest
from app.modules.agents.implementation.preparation.readiness.trusted.schemas import (
    TrustedReadinessContinuationRequest,
    TrustedReadinessEvaluationRequest,
    TrustedStackAdaptation,
)
from app.modules.agents.implementation.preparation.readiness.trusted.service import (
    ReadinessContinuationError,
    StaleStackAdaptationError,
    TrustedReadinessService,
)
from app.modules.agents.implementation.preparation.readiness.trusted.storage import TrustedReadinessStorage
from app.modules.agents.implementation.preparation.schemas import ArtifactDetectionLabel as A


NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
PROJECT_ID = "AGP-003"


class FakeStandalone:
    def require_active_project(self, owner_id, project_id):
        return SimpleNamespace(agent_project_id=project_id, agent_type=AgentType.IMPLEMENTATION)


def project_item(category, suffix, data=None):
    ref = ProjectSourceRef(
        source_id=f"SRC-{suffix}", source_kind=ConsolidationSourceKind.TEXT,
        label=f"Source {suffix}", source_fingerprint=suffix.lower() * 64,
        final_artifact_id=f"FTA-{suffix * 24}",
    )
    return ProjectSpecificationItem(
        project_item_id=f"PSI-{suffix * 24}", artifact_type=category,
        identity_key=suffix.lower() * 64, data=data or {"statement": suffix},
        supporting_sources=[ref], source_artifact_ids=[ref.final_artifact_id],
    )


def specification(categories):
    specification_id = "TPS-" + digest([PROJECT_ID, "b" * 64, "c" * 64])[:24].upper()
    return TrustedProjectSpecification(
        project_specification_id=specification_id,
        agent_project_id=PROJECT_ID, status=ConsolidationStatus.READY,
        categories=categories, relationships=[], source_artifact_refs=[],
        conflict_decisions=[], traceability={}, source_set_digest="b" * 64,
        decision_digest="c" * 64, schema_version="1", created_at=NOW,
    )


class FakeConsolidation:
    def __init__(self, final=None, status=ConsolidationStatus.READY):
        self.final = final
        self.status = status

    def get_status(self, *_):
        return SimpleNamespace(status=self.status, source_set_digest="b" * 64)

    def get_final(self, *_):
        return self.final


def service(tmp_path, categories=None, status=ConsolidationStatus.READY):
    final = specification(categories or {}) if status is ConsolidationStatus.READY else None
    consolidation = FakeConsolidation(final, status)
    value = TrustedReadinessService(
        FakeStandalone(), consolidation, TrustedReadinessStorage(tmp_path), clock=lambda: NOW
    )
    return value, consolidation


def request(*outputs, adaptation=None):
    return TrustedReadinessEvaluationRequest(
        selected_outputs=list(outputs), stack_adaptation=adaptation
    )


def codes(result):
    return {item.issue_code for item in result.findings}


def test_sufficient_current_trusted_evidence_is_ready_and_persists(tmp_path):
    categories = {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")],
        A.API_SPECIFICATION: [project_item(A.API_SPECIFICATION, "B")],
        A.ACCEPTANCE_CRITERIA: [project_item(A.ACCEPTANCE_CRITERIA, "C")],
        A.NON_FUNCTIONAL_REQUIREMENTS: [project_item(A.NON_FUNCTIONAL_REQUIREMENTS, "D")],
        A.TEST_CASES: [project_item(A.TEST_CASES, "E")],
    }
    readiness, _ = service(tmp_path, categories)
    result = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.API_IMPLEMENTATION), SimpleNamespace(user_id="USR-001"))
    assert result.status == "READY"
    assert result.policy_version == TRUSTED_READINESS_POLICY_VERSION
    assert readiness.get(PROJECT_ID, SimpleNamespace(user_id="USR-001")).readiness_id == result.readiness_id


def test_optional_missing_warns_but_required_missing_blocks_only_selected_output(tmp_path):
    categories = {A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]}
    readiness, _ = service(tmp_path, categories)
    frontend = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.FRONTEND_CODE), SimpleNamespace(user_id="USR-001"))
    assert frontend.status == "READY_WITH_WARNINGS"
    assert "FRONTEND_CODE_UI_FLOW_RECOMMENDED" in codes(frontend)
    database = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.DATABASE_IMPLEMENTATION), SimpleNamespace(user_id="USR-001"))
    assert database.status == "NOT_READY"
    assert "DATABASE_SCHEMA_REQUIRED" in codes(database)
    config = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.CONFIGURATION_FILES), SimpleNamespace(user_id="USR-001"))
    assert "DATABASE_SCHEMA_REQUIRED" not in codes(config)


@pytest.mark.parametrize("status,code", [
    (ConsolidationStatus.NOT_STARTED, "PROJECT_SPECIFICATION_NOT_READY"),
    (ConsolidationStatus.WAITING_FOR_HUMAN, "PROJECT_SPECIFICATION_REVIEW_REQUIRED"),
    (ConsolidationStatus.STALE, "PROJECT_SPECIFICATION_STALE"),
    (ConsolidationStatus.FAILED, "PROJECT_SPECIFICATION_FAILED"),
])
def test_non_ready_project_specification_is_a_hard_gate(tmp_path, status, code):
    readiness, _ = service(tmp_path, status=status)
    result = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.GIT_SUMMARY), SimpleNamespace(user_id="USR-001"))
    assert result.status == "NOT_READY"
    assert codes(result) == {code}


def test_stack_adaptation_is_bound_and_does_not_mutate_specification(tmp_path):
    tech = project_item(A.TECHNOLOGY_STACK, "B", {"category": "database", "value": "PostgreSQL"})
    categories = {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")],
        A.TECHNOLOGY_STACK: [tech],
        A.TECHNICAL_CONSTRAINTS: [project_item(A.TECHNICAL_CONSTRAINTS, "C")],
    }
    readiness, consolidation = service(tmp_path, categories)
    before = consolidation.final.model_dump(mode="json")
    first = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.CONFIGURATION_FILES), SimpleNamespace(user_id="USR-001"))
    assert first.status == "NOT_READY"
    assert first.stack_adaptation.approved is False
    adapted = readiness.evaluate(PROJECT_ID, request(
        ImplementationOutputCode.CONFIGURATION_FILES,
        adaptation={"decision": "ADAPT_TO_SUPPORTED_STACK", "expected_fingerprint": first.stack_adaptation.fingerprint},
    ), SimpleNamespace(user_id="USR-001"))
    assert adapted.stack_adaptation.approved is True
    assert adapted.status == "READY"
    assert consolidation.final.model_dump(mode="json") == before
    with pytest.raises(StaleStackAdaptationError):
        readiness.evaluate(PROJECT_ID, request(
            ImplementationOutputCode.CONFIGURATION_FILES,
            adaptation={"decision": "ADAPT_TO_SUPPORTED_STACK", "expected_fingerprint": "0" * 64},
        ), SimpleNamespace(user_id="USR-001"))


def test_selected_outputs_and_specification_changes_invalidate_current_snapshot(tmp_path):
    categories = {A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]}
    readiness, consolidation = service(tmp_path, categories)
    first = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.GIT_SUMMARY), SimpleNamespace(user_id="USR-001"))
    second = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.FRONTEND_CODE), SimpleNamespace(user_id="USR-001"))
    assert first.selected_outputs_digest != second.selected_outputs_digest
    consolidation.status = ConsolidationStatus.STALE
    assert readiness.get(PROJECT_ID, SimpleNamespace(user_id="USR-001")).current is False


def test_traceability_uses_project_item_ids_and_github_is_not_required(tmp_path):
    item = project_item(A.FUNCTIONAL_REQUIREMENTS, "A")
    readiness, _ = service(tmp_path, {A.FUNCTIONAL_REQUIREMENTS: [item]})
    result = readiness.evaluate(PROJECT_ID, request(ImplementationOutputCode.GIT_SUMMARY), SimpleNamespace(user_id="USR-001"))
    assert result.status == "READY"
    assert all("GITHUB" not in code for code in codes(result))
    assert result.coverage[0].project_item_ids == [item.project_item_id]


def test_request_rejects_frontend_fact_injection():
    with pytest.raises(ValueError):
        TrustedReadinessEvaluationRequest.model_validate({
            "selected_outputs": ["BACKEND_CODE"],
            "trusted_project_specification": {"categories": {}},
        })
    with pytest.raises(ValueError):
        TrustedReadinessContinuationRequest.model_validate({
            "expected_readiness_id": "RDY-" + "A" * 24,
            "expected_readiness_fingerprint": "b" * 64,
            "acknowledged_warning_codes": ["UI_FLOW_RECOMMENDED"],
            "warning_messages": ["frontend supplied fact"],
        })


def test_openapi_exposes_only_the_single_continuation_operation():
    from app.main import app

    path = "/api/v1/agents/implementation/{agent_project_id}/trusted-readiness/continue"
    assert set(app.openapi()["paths"][path]) == {"post"}


def continuation_request(result, warning_codes=None, **updates):
    values = {
        "expected_readiness_id": result.readiness_id,
        "expected_readiness_fingerprint": result.readiness_fingerprint,
        "acknowledged_warning_codes": warning_codes or sorted(codes(result)),
    }
    values.update(updates)
    return TrustedReadinessContinuationRequest(**values)


def test_warning_continuation_persists_without_mutating_readiness_or_specification(tmp_path):
    categories = {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]
    }
    readiness, consolidation = service(tmp_path, categories)
    before = consolidation.final.model_dump(mode="json")
    result = readiness.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.FRONTEND_CODE),
        SimpleNamespace(user_id="USR-001"),
    )
    assert result.status == "READY_WITH_WARNINGS"
    assert result.continuation_required is True

    approved = readiness.continue_with_warnings(
        PROJECT_ID, continuation_request(result),
        SimpleNamespace(user_id="USR-001"),
    )
    assert approved.status == "READY_WITH_WARNINGS"
    assert approved.continuation_approved is True
    assert approved.continuation_required is False
    assert approved.continuation_decision_id.startswith("RCD-")
    assert consolidation.final.model_dump(mode="json") == before

    restored = readiness.get(PROJECT_ID, SimpleNamespace(user_id="USR-001"))
    assert restored.continuation_decision_id == approved.continuation_decision_id
    assert (tmp_path / PROJECT_ID / "implementation-readiness-continuation.json").exists()


def test_warning_continuation_requires_exact_current_identity_and_warning_set(tmp_path):
    readiness, _ = service(tmp_path, {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]
    })
    result = readiness.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.FRONTEND_CODE),
        SimpleNamespace(user_id="USR-001"),
    )
    with pytest.raises(ReadinessContinuationError, match="changed"):
        readiness.continue_with_warnings(
            PROJECT_ID,
            continuation_request(result, expected_readiness_fingerprint="0" * 64),
            SimpleNamespace(user_id="USR-001"),
        )
    with pytest.raises(ReadinessContinuationError, match="exactly"):
        readiness.continue_with_warnings(
            PROJECT_ID, continuation_request(result, ["STALE_WARNING"]),
            SimpleNamespace(user_id="USR-001"),
        )
    with pytest.raises(ReadinessContinuationError, match="exactly"):
        readiness.continue_with_warnings(
            PROJECT_ID,
            continuation_request(result, sorted(codes(result)) + ["EXTRA_WARNING"]),
            SimpleNamespace(user_id="USR-001"),
        )


def test_ready_and_not_ready_cannot_be_continued(tmp_path):
    ready_service, _ = service(tmp_path / "ready", {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")],
        A.API_SPECIFICATION: [project_item(A.API_SPECIFICATION, "B")],
        A.ACCEPTANCE_CRITERIA: [project_item(A.ACCEPTANCE_CRITERIA, "C")],
        A.NON_FUNCTIONAL_REQUIREMENTS: [project_item(A.NON_FUNCTIONAL_REQUIREMENTS, "D")],
        A.TEST_CASES: [project_item(A.TEST_CASES, "E")],
    })
    ready = ready_service.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.API_IMPLEMENTATION),
        SimpleNamespace(user_id="USR-001"),
    )
    with pytest.raises(ReadinessContinuationError, match="Only current"):
        ready_service.continue_with_warnings(
            PROJECT_ID,
            TrustedReadinessContinuationRequest(
                expected_readiness_id=ready.readiness_id,
                expected_readiness_fingerprint=ready.readiness_fingerprint,
                acknowledged_warning_codes=["UNNEEDED"],
            ),
            SimpleNamespace(user_id="USR-001"),
        )

    blocked_service, _ = service(tmp_path / "blocked", {})
    blocked = blocked_service.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.DATABASE_IMPLEMENTATION),
        SimpleNamespace(user_id="USR-001"),
    )
    with pytest.raises(ReadinessContinuationError, match="Only current"):
        blocked_service.continue_with_warnings(
            PROJECT_ID,
            TrustedReadinessContinuationRequest(
                expected_readiness_id=blocked.readiness_id,
                expected_readiness_fingerprint=blocked.readiness_fingerprint,
                acknowledged_warning_codes=["DATABASE_SCHEMA_REQUIRED"],
            ),
            SimpleNamespace(user_id="USR-001"),
        )


def test_changed_outputs_and_specification_invalidate_warning_continuation(tmp_path):
    readiness, consolidation = service(tmp_path, {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]
    })
    first = readiness.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.FRONTEND_CODE),
        SimpleNamespace(user_id="USR-001"),
    )
    readiness.continue_with_warnings(
        PROJECT_ID, continuation_request(first),
        SimpleNamespace(user_id="USR-001"),
    )
    changed = readiness.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.BACKEND_CODE),
        SimpleNamespace(user_id="USR-001"),
    )
    assert changed.continuation_approved is False
    assert changed.continuation_required is True

    readiness.continue_with_warnings(
        PROJECT_ID, continuation_request(changed),
        SimpleNamespace(user_id="USR-001"),
    )
    consolidation.status = ConsolidationStatus.STALE
    stale = readiness.get(PROJECT_ID, SimpleNamespace(user_id="USR-001"))
    assert stale.current is False
    assert stale.continuation_approved is False


def test_continuation_identity_rejects_policy_spec_stack_and_owner_changes(tmp_path):
    readiness, _ = service(tmp_path, {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]
    })
    user = SimpleNamespace(user_id="USR-001")
    result = readiness.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.FRONTEND_CODE), user,
    )
    readiness.continue_with_warnings(
        PROJECT_ID, continuation_request(result), user,
    )
    assert readiness.valid_continuation(result, user) is not None

    changed_values = [
        {"policy_version": "future-policy"},
        {"selected_outputs_digest": "0" * 64},
        {"project_specification_id": "TPS-" + "F" * 24},
        {"stack_adaptation": TrustedStackAdaptation(
            decision="ADAPT_TO_SUPPORTED_STACK", fingerprint="1" * 64,
            approved=True, approved_at=NOW,
        )},
    ]
    for update in changed_values:
        assert readiness.valid_continuation(
            result.model_copy(update=update), user
        ) is None
    assert readiness.valid_continuation(
        result, SimpleNamespace(user_id="USR-OTHER")
    ) is None


def test_malformed_persisted_snapshot_never_loads_as_ready(tmp_path):
    path = tmp_path / PROJECT_ID / "implementation-readiness.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"status":"READY"}', encoding="utf-8")
    readiness, _ = service(tmp_path, {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]
    })
    from app.modules.agents.implementation.preparation.readiness.trusted.storage import TrustedReadinessStorageError
    with pytest.raises(TrustedReadinessStorageError):
        readiness.get(PROJECT_ID, SimpleNamespace(user_id="USR-001"))


def test_invalid_trusted_specification_fingerprint_never_becomes_ready(tmp_path):
    readiness, consolidation = service(tmp_path, {
        A.FUNCTIONAL_REQUIREMENTS: [project_item(A.FUNCTIONAL_REQUIREMENTS, "A")]
    })
    consolidation.final = consolidation.final.model_copy(update={
        "project_specification_id": "TPS-" + "F" * 24
    })
    result = readiness.evaluate(
        PROJECT_ID, request(ImplementationOutputCode.GIT_SUMMARY),
        SimpleNamespace(user_id="USR-001"),
    )
    assert result.status == "NOT_READY"
    assert codes(result) == {"PROJECT_SPECIFICATION_NOT_READY"}
