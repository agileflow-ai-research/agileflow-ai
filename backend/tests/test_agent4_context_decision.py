import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.agents.testing_validation.context_testability.context_decision.constants import (
    CONTEXT_DECISION_ENGINE_VERSION,
    CONTEXT_DECISION_POLICY_VERSION,
    CONTEXT_DECISION_SCHEMA_VERSION,
    ConsolidatedFindingOrigin,
    ConsolidatedFindingSeverity,
    ContextDecisionStatus,
)
from app.modules.agents.testing_validation.context_testability.context_decision.engine import (
    ContextDecisionInputError,
    consolidate_context_decision,
    consolidate_findings,
)
from app.modules.agents.testing_validation.context_testability.context_decision.schemas import (
    OutputContextDecisionProfile,
)
from app.modules.agents.testing_validation.context_testability.context_decision.service import (
    Agent4ContextDecisionGateError,
    Agent4ContextDecisionService,
)
from app.modules.agents.testing_validation.context_testability.context_decision.storage import (
    Agent4ContextDecisionStorage,
    Agent4ContextDecisionStorageError,
)
from app.modules.agents.testing_validation.context_testability.feasibility.schemas import (
    FeasibilityFinding,
    FeasibilityFindingSeverity,
    FeasibilityStatus,
    GenerationProfile,
    RepresentationRecommendation,
)
from app.modules.agents.testing_validation.context_testability.feasibility.storage import (
    Agent4FeasibilityStorage,
)
from app.modules.agents.testing_validation.context_testability.testability.schemas import (
    MissingContextFinding,
    TestabilityFindingSeverity as TBFindingSeverity,
    TestabilityStatus as TBStatus,
)
from app.modules.agents.testing_validation.context_testability.testability.storage import (
    Agent4TestabilityStorage,
)
from app.modules.agents.testing_validation.context_testability.traceability.storage import (
    Agent4TraceabilityStorage,
)
from app.modules.agents.testing_validation.context_testability.feasibility.constants import (
    TechnicalEvidenceCategory,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode as O
from app.modules.agents.testing_validation.workflow.schemas import Agent4WorkflowNodeStatus
from app.modules.standalone.schemas import AgentProjectStatus, AgentStage
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from test_agent4_feasibility import feasibility_service
from test_agent4_n2_orchestration import load, n2_context
from test_agent4_traceability import completed_project
from test_standalone_foundation import user


NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def prepared(context):
    project_id = completed_project(context)
    feasibility, traceability, testability = feasibility_service(context)
    graph = traceability.build(project_id, user())
    tb = testability.evaluate(project_id, user())
    fb = feasibility.evaluate(project_id, user())
    return project_id, graph, tb, fb


def decision_service(context):
    root = context[3]
    return Agent4ContextDecisionService(
        context[1]._workflow_service,
        Agent4WorkflowStorage(root),
        Agent4TraceabilityStorage(root),
        Agent4TestabilityStorage(root),
        Agent4FeasibilityStorage(root),
        Agent4ContextDecisionStorage(root),
        clock=lambda: NOW,
    )


def variants(tb, fb, tb_status, fb_status, representation):
    tb_assessment = tb.output_assessments[0].model_copy(update={"status": tb_status})
    fb_assessment = fb.output_assessments[0].model_copy(update={
        "n4_2_status": tb_status,
        "feasibility": fb_status,
        "recommended_representation": representation,
        "generation_profile": GenerationProfile(
            language="PYTHON", test_framework="PYTEST", automation_surface="UNIT",
            evidence_node_ids=[], evidence_link_ids=[],
        ) if fb_status is FeasibilityStatus.EXECUTABLE_POSSIBLE else None,
        "execution_status": "NOT_EXECUTED"
        if fb_status is FeasibilityStatus.EXECUTABLE_POSSIBLE else None,
    })
    return (
        tb.model_copy(update={"output_assessments": [tb_assessment]}),
        fb.model_copy(update={"output_assessments": [fb_assessment]}),
    )


def test_contract_versions_states_are_exact_strict_and_score_free(n2_context):
    project_id, _, _, _ = prepared(n2_context)
    result = decision_service(n2_context).evaluate(project_id, user())
    assert (
        CONTEXT_DECISION_SCHEMA_VERSION,
        CONTEXT_DECISION_ENGINE_VERSION,
        CONTEXT_DECISION_POLICY_VERSION,
    ) == ("1", "CD1", "CP1")
    assert {item.value for item in ContextDecisionStatus} == {
        "PROCEED", "PROCEED_WITH_WARNINGS", "BLOCKED",
    }
    assert result.selected_outputs == [O.UNIT_TEST_CASES]
    assert "confidence" not in result.model_dump_json().casefold()
    assert "readiness_score" not in result.model_dump_json().casefold()
    with pytest.raises(ValidationError, match="extra_forbidden"):
        OutputContextDecisionProfile.model_validate({
            **result.output_profiles[0].model_dump(), "clarification_question": "Why?",
        })


@pytest.mark.parametrize(
    ("tb_status", "fb_status", "representation", "expected"),
    (
        (TBStatus.READY, FeasibilityStatus.EXECUTABLE_POSSIBLE,
         RepresentationRecommendation.EXECUTABLE_CODE, ContextDecisionStatus.PROCEED),
        (TBStatus.READY, FeasibilityStatus.SPECIFICATION_ONLY,
         RepresentationRecommendation.SPECIFICATION, ContextDecisionStatus.PROCEED_WITH_WARNINGS),
        (TBStatus.READY_WITH_WARNINGS, FeasibilityStatus.EXECUTABLE_POSSIBLE,
         RepresentationRecommendation.EXECUTABLE_CODE, ContextDecisionStatus.PROCEED_WITH_WARNINGS),
        (TBStatus.READY_WITH_WARNINGS, FeasibilityStatus.SPECIFICATION_ONLY,
         RepresentationRecommendation.SPECIFICATION, ContextDecisionStatus.PROCEED_WITH_WARNINGS),
    ),
)
def test_decision_matrix_preserves_dimensions_and_planning(
    n2_context, tb_status, fb_status, representation, expected,
):
    _, _, tb, fb = prepared(n2_context)
    tb, fb = variants(tb, fb, tb_status, fb_status, representation)
    profiles, planning, _, overall = consolidate_context_decision(
        tb.confirmed_selected_outputs, tb, fb
    )
    profile = profiles[0]
    assert profile.decision is expected and overall is expected
    assert profile.planning_allowed and planning[0].planning_allowed
    assert profile.testability_status is tb_status
    assert profile.feasibility_status is fb_status
    assert profile.recommended_representation is representation
    if fb_status is FeasibilityStatus.EXECUTABLE_POSSIBLE:
        assert profile.execution_status == "NOT_EXECUTED"


def test_testability_block_cannot_be_overridden_and_blocked_output_remains_selected(n2_context):
    _, _, tb, fb = prepared(n2_context)
    blocking = MissingContextFinding(
        finding_id="A4TBF-" + "1" * 32,
        output_code=O.UNIT_TEST_CASES,
        severity=TBFindingSeverity.BLOCKING,
        category="MISSING_BEHAVIOR",
        reason_code="MISSING_BEHAVIOR",
        message="Behavior evidence is missing.",
        required_evidence_categories=[], observed_count=0,
        related_node_ids=[], related_link_ids=[], related_finding_ids=[],
        semantic_fact_ids=[],
    )
    tb_assessment = tb.output_assessments[0].model_copy(update={
        "status": TBStatus.NOT_READY,
        "finding_ids": [blocking.finding_id],
    })
    fb_assessment = fb.output_assessments[0].model_copy(update={
        "n4_2_status": TBStatus.NOT_READY,
        "feasibility": FeasibilityStatus.NOT_READY,
        "recommended_representation": None,
        "generation_profile": None,
        "execution_status": None,
    })
    blocked_tb = tb.model_copy(update={"output_assessments": [tb_assessment], "findings": [blocking]})
    blocked_fb = fb.model_copy(update={"output_assessments": [fb_assessment]})
    profiles, planning, findings, overall = consolidate_context_decision(
        [O.UNIT_TEST_CASES], blocked_tb, blocked_fb
    )
    assert profiles[0].decision is ContextDecisionStatus.BLOCKED
    assert not profiles[0].planning_allowed and not planning[0].planning_allowed
    assert profiles[0].output_code is O.UNIT_TEST_CASES
    assert overall is ContextDecisionStatus.BLOCKED
    assert any(item.severity is ConsolidatedFindingSeverity.BLOCKING for item in findings)
    overridden = fb_assessment.model_copy(update={
        "feasibility": FeasibilityStatus.EXECUTABLE_POSSIBLE,
        "recommended_representation": RepresentationRecommendation.EXECUTABLE_CODE,
        "generation_profile": GenerationProfile(
            language="PYTHON", test_framework="PYTEST", automation_surface="UNIT",
            evidence_node_ids=[], evidence_link_ids=[],
        ),
        "execution_status": "NOT_EXECUTED",
    })
    with pytest.raises(ContextDecisionInputError, match="override"):
        consolidate_context_decision(
            [O.UNIT_TEST_CASES], blocked_tb,
            blocked_fb.model_copy(update={"output_assessments": [overridden]}),
        )


def test_traceability_structured_artifact_is_normal_but_tb_warning_propagates(n2_context):
    _, _, tb, fb = prepared(n2_context)
    output = O.TEST_TRACEABILITY
    tb_assessment = tb.output_assessments[0].model_copy(update={
        "output_code": output, "status": TBStatus.READY,
        "finding_ids": [], "reason_codes": [],
    })
    fb_assessment = fb.output_assessments[0].model_copy(update={
        "output_code": output,
        "n4_2_status": TBStatus.READY,
        "feasibility": FeasibilityStatus.SPECIFICATION_ONLY,
        "recommended_representation": RepresentationRecommendation.STRUCTURED_ARTIFACT,
        "generation_profile": None, "execution_status": None,
        "finding_ids": [], "reason_codes": ["STRUCTURED_ARTIFACT_NOT_EXECUTABLE"],
    })
    trace_tb = tb.model_copy(update={
        "confirmed_selected_outputs": [output], "output_assessments": [tb_assessment],
        "findings": [],
    })
    trace_fb = fb.model_copy(update={
        "selected_outputs": [output], "output_assessments": [fb_assessment],
        "findings": [],
    })
    profiles, _, findings, overall = consolidate_context_decision([output], trace_tb, trace_fb)
    assert overall is ContextDecisionStatus.PROCEED
    assert profiles[0].recommended_representation is RepresentationRecommendation.STRUCTURED_ARTIFACT
    assert findings == [] and profiles[0].warning_finding_ids == []
    warned_tb = trace_tb.model_copy(update={
        "output_assessments": [tb_assessment.model_copy(update={"status": TBStatus.READY_WITH_WARNINGS})]
    })
    warned_fb = trace_fb.model_copy(update={
        "output_assessments": [fb_assessment.model_copy(update={"n4_2_status": TBStatus.READY_WITH_WARNINGS})]
    })
    assert consolidate_context_decision([output], warned_tb, warned_fb)[3] is ContextDecisionStatus.PROCEED_WITH_WARNINGS


def test_findings_preserve_origins_deduplicate_only_equivalent_and_order_deterministically():
    message = "A compatible test framework is missing."
    tb_finding = MissingContextFinding(
        finding_id="A4TBF-" + "2" * 32, output_code=O.API_TEST_CASES,
        severity=TBFindingSeverity.WARNING,
        category="MISSING_TEST_FRAMEWORK", reason_code="MISSING_TEST_FRAMEWORK",
        message=message, required_evidence_categories=[], observed_count=0,
        related_node_ids=[], related_link_ids=[], related_finding_ids=[], semantic_fact_ids=[],
    )
    fb_finding = FeasibilityFinding(
        finding_id="A4FBF-" + "3" * 32, output_code=O.API_TEST_CASES,
        severity=FeasibilityFindingSeverity.BLOCKING_EXECUTABLE,
        reason_code="MISSING_TEST_FRAMEWORK", message=message,
        technical_categories=[TechnicalEvidenceCategory.TEST_FRAMEWORK],
        evidence_values=[], related_node_ids=[], related_link_ids=[],
        semantic_fact_ids=[], source_ids=[], chunk_ids=[],
    )
    first = consolidate_findings([tb_finding], [fb_finding])
    second = consolidate_findings([tb_finding], [fb_finding])
    assert len(first) == 1
    assert first[0].consolidated_finding_id == second[0].consolidated_finding_id
    assert {(item.origin, item.origin_finding_id) for item in first[0].origin_references} == {
        (ConsolidatedFindingOrigin.TESTABILITY, tb_finding.finding_id),
        (ConsolidatedFindingOrigin.FEASIBILITY, fb_finding.finding_id),
    }
    distinct = fb_finding.model_copy(update={"message": "The executable toolchain is ambiguous."})
    assert len(consolidate_findings([tb_finding], [distinct])) == 2


def test_service_loads_persisted_artifacts_without_reassessment_and_preserves_immutability(
    n2_context, monkeypatch,
):
    project_id, _, _, _ = prepared(n2_context)
    root, runs = n2_context[3], n2_context[5]
    immutable = {
        path: path.read_bytes() for path in (root / project_id).rglob("*") if path.is_file()
    }
    def forbidden(*_args, **_kwargs):
        raise AssertionError("upstream algorithm was invoked")
    monkeypatch.setattr(
        "app.modules.agents.testing_validation.context_testability.traceability.service.Agent4TraceabilityService.build",
        forbidden,
    )
    monkeypatch.setattr(
        "app.modules.agents.testing_validation.context_testability.testability.service.Agent4TestabilityService.evaluate",
        forbidden,
    )
    monkeypatch.setattr(
        "app.modules.agents.testing_validation.context_testability.feasibility.service.Agent4FeasibilityService.evaluate",
        forbidden,
    )
    monkeypatch.setattr(
        "app.modules.agents.testing_validation.context_testability.feasibility.extractor.build_technical_evidence_inventory",
        forbidden,
    )
    result = decision_service(n2_context).evaluate(project_id, user())
    path = root / project_id / "context-testability" / "context-decision.json"
    assert path.is_file()
    assert all(path.read_bytes() == content for path, content in immutable.items())
    workflow = load(n2_context[0], project_id)
    assert [item["status"] for item in workflow["nodes"]] == [
            "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "NOT_STARTED", "LOCKED", "LOCKED",
    ]
    assert workflow["current_node_id"] == "CONTEXT_TESTABILITY"
    assert workflow["pipeline_status"] == "RUNNING" and runs.documents == {}
    assert result.planning_allowed_output_count + result.blocked_output_count == len(result.selected_outputs)


def test_cache_force_corruption_and_storage_atomicity(n2_context, monkeypatch, tmp_path):
    project_id, _, _, _ = prepared(n2_context)
    service = decision_service(n2_context)
    first = service.evaluate(project_id, user())
    path = n2_context[3] / project_id / "context-testability" / "context-decision.json"
    raw = path.read_bytes()
    cached = service.evaluate(project_id, user())
    forced = service.evaluate(project_id, user(), force=True)
    assert cached.evaluated_at == first.evaluated_at and path.read_bytes() == raw
    assert forced.input_fingerprint == first.input_fingerprint
    assert [item.profile_id for item in forced.output_profiles] == [item.profile_id for item in first.output_profiles]
    path.write_text("{corrupt", encoding="utf-8")
    assert service.evaluate(project_id, user()).input_fingerprint == first.input_fingerprint

    storage = Agent4ContextDecisionStorage(tmp_path)
    storage.save(first, owner_user_id="USR-001")
    atomic = tmp_path / project_id / "context-testability" / "context-decision.json"
    assert atomic.is_file() and not atomic.with_suffix(".json.part").exists()
    with pytest.raises(Agent4ContextDecisionStorageError, match="identity"):
        storage.load(agent_project_id=project_id, owner_user_id="USR-002")
    original = type(atomic).replace
    monkeypatch.setattr(type(atomic), "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(Agent4ContextDecisionStorageError):
        storage.save(first, owner_user_id="USR-001")
    assert not atomic.with_suffix(".json.part").exists()
    monkeypatch.setattr(type(atomic), "replace", original)


def test_cache_with_unknown_origin_reference_is_rejected(n2_context, monkeypatch):
    project_id, _, _, _ = prepared(n2_context)
    service = decision_service(n2_context)
    result = service.evaluate(project_id, user())
    path = n2_context[3] / project_id / "context-testability" / "context-decision.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload["consolidated_findings"]:
        pytest.skip("fixture produced no upstream findings")
    payload["consolidated_findings"][0]["origin_references"][0]["origin_finding_id"] = (
        "A4FBF-" + "f" * 32
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    def proves_rebuild(*_args, **_kwargs):
        raise RuntimeError("rebuild reached")
    monkeypatch.setattr(
        "app.modules.agents.testing_validation.context_testability.context_decision.service.consolidate_context_decision",
        proves_rebuild,
    )
    with pytest.raises(RuntimeError, match="rebuild reached"):
        service.evaluate(project_id, user())


def test_cache_with_stale_assessment_reference_is_rejected(n2_context, monkeypatch):
    project_id, _, _, _ = prepared(n2_context)
    service = decision_service(n2_context)
    service.evaluate(project_id, user())
    path = n2_context[3] / project_id / "context-testability" / "context-decision.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["output_profiles"][0]["testability_assessment_ref"] = "A4TBA-" + "e" * 32
    path.write_text(json.dumps(payload), encoding="utf-8")
    def proves_rebuild(*_args, **_kwargs):
        raise RuntimeError("rebuild reached")
    monkeypatch.setattr(
        "app.modules.agents.testing_validation.context_testability.context_decision.service.consolidate_context_decision",
        proves_rebuild,
    )
    with pytest.raises(RuntimeError, match="rebuild reached"):
        service.evaluate(project_id, user())


def test_selected_output_mismatch_is_rejected(n2_context):
    project_id, _, _, fb = prepared(n2_context)
    Agent4FeasibilityStorage(n2_context[3]).save(
        fb.model_copy(update={"selected_outputs": [O.API_TEST_CASES]}),
        owner_user_id=user().user_id,
    )
    with pytest.raises(Agent4ContextDecisionGateError, match="persisted"):
        decision_service(n2_context).evaluate(project_id, user())


@pytest.mark.parametrize("artifact", ("traceability", "testability", "feasibility"))
def test_service_rejects_each_stale_upstream_artifact(n2_context, artifact):
    project_id, graph, tb, fb = prepared(n2_context)
    root = n2_context[3]
    if artifact == "traceability":
        Agent4TraceabilityStorage(root).save(
            graph.model_copy(update={"input_fingerprint": "0" * 64}), owner_user_id=user().user_id
        )
        expected = "TB1"
    elif artifact == "testability":
        Agent4TestabilityStorage(root).save(
            tb.model_copy(update={"traceability_manifest_fingerprint": "0" * 64}),
            owner_user_id=user().user_id,
        )
        expected = "TB1"
    else:
        Agent4FeasibilityStorage(root).save(
            fb.model_copy(update={"testability_result_fingerprint": "0" * 64}),
            owner_user_id=user().user_id,
        )
        expected = "FB1"
    with pytest.raises(Agent4ContextDecisionGateError, match=expected):
        decision_service(n2_context).evaluate(project_id, user())


def test_service_rejects_incomplete_workflow_wrong_project_and_foreign_owner(n2_context):
    project_id, _, _, _ = prepared(n2_context)
    service = decision_service(n2_context)
    with pytest.raises(Exception):
        service.evaluate("AGP-999999", user())
    foreign = user().model_copy(update={"user_id": "USR-999"})
    with pytest.raises(Exception):
        service.evaluate(project_id, foreign)
    workflows = Agent4WorkflowStorage(n2_context[3])
    record = workflows.load(agent_project_id=project_id, owner_user_id=user().user_id)
    changed = record.model_copy(deep=True)
    changed.nodes[2].status = Agent4WorkflowNodeStatus.FAILED
    workflows.save(changed)
    with pytest.raises(Agent4ContextDecisionGateError, match="workflow boundary"):
        service.evaluate(project_id, user())


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("status", AgentProjectStatus.ARCHIVED),
        ("agent_stage", None),
        ("agent_stage", AgentStage.VALIDATION),
    ),
)
def test_project_archive_and_wrong_or_legacy_stage_are_rejected(n2_context, field, value):
    project_id, _, _, _ = prepared(n2_context)
    n2_context[4].documents[project_id][field] = value
    with pytest.raises(Exception):
        decision_service(n2_context).evaluate(project_id, user())


def test_scope_contains_no_questions_plans_execution_ai_or_agentrun(n2_context):
    project_id, _, _, _ = prepared(n2_context)
    result = decision_service(n2_context).evaluate(project_id, user())
    serialized = result.model_dump_json().casefold()
    for forbidden in (
        "clarification_question", "test case plan", "test_steps", "expected_result",
        '"executed"', '"passed"', '"failed"', "agentrun", "confidence",
    ):
        assert forbidden not in serialized
