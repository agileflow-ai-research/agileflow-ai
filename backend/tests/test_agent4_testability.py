import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from app.modules.agents.testing_validation.context_testability.testability.constants import (
    OUTPUT_POLICY_VERSION,
    TESTABILITY_ENGINE_VERSION,
    TESTABILITY_SCHEMA_VERSION,
    EvidenceCategory as E,
)
from app.modules.agents.testing_validation.context_testability.testability.engine import (
    build_evidence_inventory,
    evaluate_testability,
)
from app.modules.agents.testing_validation.context_testability.testability.policy import (
    OUTPUT_POLICY_BY_CODE,
    OUTPUT_TESTABILITY_POLICIES,
)
from app.modules.agents.testing_validation.context_testability.testability.schemas import (
    Agent4TestabilityResult,
    TestabilityFindingSeverity as FindingSeverity,
    TestabilityStatus as Status,
)
from app.modules.agents.testing_validation.context_testability.testability.service import (
    Agent4TestabilityGateError,
    Agent4TestabilityService,
)
from app.modules.agents.testing_validation.context_testability.testability.storage import (
    Agent4TestabilityStorage,
    Agent4TestabilityStorageError,
)
from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    fingerprint,
)
from app.modules.agents.testing_validation.context_testability.traceability.schemas import (
    Agent4TraceabilityManifest,
    AmbiguousTraceabilityMatch,
    TraceabilityCounts,
    TraceabilityEvidenceMethod,
    TraceabilityLink,
    TraceabilityNode,
    TraceabilityNodeKind as N,
    TraceabilityRelationType as R,
    TraceabilityStrength,
    UnresolvedReferenceType,
    UnresolvedTraceabilityReference,
)
from app.modules.agents.testing_validation.context_testability.traceability.storage import (
    Agent4TraceabilityStorage,
)
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType as A,
)
from app.modules.agents.testing_validation.intelligence.effective.storage import (
    Agent4EffectiveStorage,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticFactType as F,
)
from app.modules.agents.testing_validation.intelligence.semantic.storage import (
    Agent4SemanticStorage,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TestingIntelligenceLabel as L,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode as O
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from test_agent4_n2_orchestration import load, n2_context
from test_agent4_traceability import completed_project, trace_service
from test_standalone_foundation import user


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)
PROJECT = "AGP-100"


def node(index, kind, artifact=A.FUNCTIONAL_REQUIREMENTS, *, external=None,
         api=None, fact_type=None, source=None):
    semantic = kind is N.SEMANTIC_TESTING_FACT
    labels = {
        F.BEHAVIOR: L.FUNCTIONAL_BEHAVIOR,
        F.INPUT_CONSTRAINT: L.INPUT_VALIDATION,
        F.BOUNDARY_CONSTRAINT: L.BOUNDARY_CONSTRAINT,
        F.DATA_INTEGRITY_CONSTRAINT: L.DATA_INTEGRITY,
        F.API_CONTRACT: L.API_CONTRACT,
        F.UI_INTERACTION: L.UI_WORKFLOW,
        F.AUTHENTICATION_REQUIREMENT: L.AUTHENTICATION,
        F.AUTHORIZATION_RULE: L.AUTHORIZATION,
        F.SECURITY_CONTROL: L.SECURITY_CONTROL,
        F.PERFORMANCE_TARGET: L.PERFORMANCE_SLO,
        F.RELIABILITY_RECOVERY: L.RELIABILITY_RECOVERY,
        F.ERROR_EXPECTATION: L.ERROR_HANDLING,
        F.ACCEPTANCE_CONDITION: L.ACCEPTANCE_CONDITION,
        F.STATE_PERSISTENCE: L.STATE_PERSISTENCE,
    }
    method, path = api or (None, None)
    return TraceabilityNode(
        node_id=f"A4TRN-{index:032x}", node_kind=kind,
        agent_project_id=PROJECT, source_id=f"A4SRC-{(source or index):032x}",
        artifact_type=artifact, external_reference_id=external,
        chunk_id=f"A4CHK-{index:032x}",
        semantic_fact_id=f"A4FACT-{index:032x}" if semantic else None,
        semantic_fact_type=fact_type,
        semantic_labels=[labels[fact_type]] if fact_type else [],
        display_value=external or (f"{method} {path}" if method else f"Evidence {index}"),
        canonical_value=(external or path or f"evidence-{index}").casefold(),
        provenance_fingerprint=f"{index:064x}", api_method=method, api_path=path,
        hybrid_result_id=f"A4HYB-{index:032x}" if semantic else None,
        effective_result_id=f"A4EFF-{index:032x}" if semantic else None,
    )


def link(index, left, right, relation=R.RELATED_TO):
    return TraceabilityLink(
        traceability_link_id=f"A4TRL-{index:032x}",
        source_node_id=left.node_id, target_node_id=right.node_id,
        relation_type=relation,
        evidence_method=TraceabilityEvidenceMethod.EXPLICIT_REFERENCE,
        evidence_references=[left.node_id, right.node_id],
        reason_code="EXPLICIT_TEST_RELATION", explanation="Explicit trusted relation.",
        strength=TraceabilityStrength.EXACT, traceability_version="TR1",
    )


def graph(*nodes, links=(), unresolved=(), ambiguities=()):
    nodes = sorted(nodes, key=lambda item: item.node_id)
    links = sorted(links, key=lambda item: item.traceability_link_id)
    unresolved = sorted(unresolved, key=lambda item: item.unresolved_id)
    ambiguities = sorted(ambiguities, key=lambda item: item.ambiguity_id)
    return Agent4TraceabilityManifest(
        schema_version="1", engine_version="TR1", lexical_policy_version="LX1",
        agent_project_id=PROJECT, confirmation_id=f"A4N1C-{'1' * 32}",
        n2_execution_id=f"A4N2E-{'2' * 32}", n3_execution_id=f"A4N3E-{'3' * 32}",
        input_fingerprint="4" * 64, evidence_fingerprints={"trusted": "5" * 64},
        nodes=nodes, links=links, unresolved_references=unresolved,
        ambiguities=ambiguities,
        counts=TraceabilityCounts(
            node_count=len(nodes), link_count=len(links),
            unresolved_count=len(unresolved), ambiguous_count=len(ambiguities),
        ), built_at=NOW,
    )


def assess(output, value):
    inventory = build_evidence_inventory(value)
    return evaluate_testability(
        [output], inventory, value, graph_fingerprint=fingerprint(value.model_dump(mode="json"))
    )


def status(output, value):
    return assess(output, value)[0][0].status


def test_versions_policy_catalog_and_fingerprint_contract_are_exact_and_immutable():
    assert (TESTABILITY_SCHEMA_VERSION, TESTABILITY_ENGINE_VERSION, OUTPUT_POLICY_VERSION) == ("1", "TB1", "OP1")
    assert tuple(item.output_code for item in OUTPUT_TESTABILITY_POLICIES) == tuple(O)
    assert len(OUTPUT_POLICY_BY_CODE) == len(O) == 9
    assert isinstance(OUTPUT_POLICY_BY_CODE, MappingProxyType)
    with pytest.raises(TypeError):
        OUTPUT_POLICY_BY_CODE[O.UNIT_TEST_CASES] = OUTPUT_TESTABILITY_POLICIES[0]
    known = set(E)
    assert all(
        set(requirement.categories).issubset(known)
        for policy in OUTPUT_TESTABILITY_POLICIES
        for requirement in policy.mandatory + policy.supporting
    )
    baseline = fingerprint([asdict(item) for item in OUTPUT_TESTABILITY_POLICIES])
    changed = replace(OUTPUT_TESTABILITY_POLICIES[0], description="changed")
    assert baseline != fingerprint([asdict(changed), *map(asdict, OUTPUT_TESTABILITY_POLICIES[1:])])


def test_status_aggregation_uses_only_selected_outputs_and_has_no_confidence():
    behavior = node(1, N.SEMANTIC_TESTING_FACT, fact_type=F.BEHAVIOR)
    feature = node(2, N.FEATURE, A.FEATURES)
    acceptance = node(3, N.ACCEPTANCE_CRITERION, A.ACCEPTANCE_CRITERIA, external="AC-001")
    requirement = node(4, N.FUNCTIONAL_REQUIREMENT, external="FR-001")
    value = graph(behavior, feature, acceptance, requirement)
    inventory = build_evidence_inventory(value)
    ready = evaluate_testability([O.UNIT_TEST_CASES, O.ACCEPTANCE_TEST_CASES], inventory, value, graph_fingerprint="a" * 64)
    assert [item.status for item in ready[0]] == [Status.READY, Status.READY]
    assert ready[2] is Status.READY
    warning = evaluate_testability([O.REGRESSION_TEST_CASES], inventory, value, graph_fingerprint="a" * 64)
    assert warning[2] is Status.READY_WITH_WARNINGS
    blocked = evaluate_testability([O.API_TEST_CASES, O.UNIT_TEST_CASES], inventory, value, graph_fingerprint="a" * 64)
    assert blocked[2] is Status.NOT_READY
    assert "confidence" not in json.dumps([item.model_dump(mode="json") for item in blocked[0]]).casefold()


def test_functional_and_unit_policies_separate_broad_from_localized_evidence():
    broad = node(1, N.FUNCTIONAL_REQUIREMENT, external="FR-001")
    assert status(O.FUNCTIONAL_TEST_CASES, graph(broad)) is Status.READY_WITH_WARNINGS
    assert status(O.UNIT_TEST_CASES, graph(broad)) is Status.NOT_READY
    behavior = node(2, N.SEMANTIC_TESTING_FACT, fact_type=F.BEHAVIOR)
    assert status(O.UNIT_TEST_CASES, graph(behavior)) is Status.READY_WITH_WARNINGS
    feature = node(3, N.FEATURE, A.FEATURES)
    assert status(O.UNIT_TEST_CASES, graph(behavior, feature)) is Status.READY
    assert "framework" not in json.dumps(assess(O.UNIT_TEST_CASES, graph(behavior))[0][0].model_dump()).casefold()


def test_api_policy_requires_usable_method_path_and_warns_until_details_exist():
    generic = node(1, N.API_CONTRACT_ITEM, A.API_SPECIFICATION)
    assert status(O.API_TEST_CASES, graph(generic)) is Status.NOT_READY
    operation = node(2, N.API_ENDPOINT, A.API_SPECIFICATION, api=("POST", "/bookings"))
    assert status(O.API_TEST_CASES, graph(operation)) is Status.READY_WITH_WARNINGS
    validation = node(3, N.SEMANTIC_TESTING_FACT, fact_type=F.INPUT_CONSTRAINT)
    assert status(O.API_TEST_CASES, graph(operation, validation)) is Status.READY
    malformed = UnresolvedTraceabilityReference(
        unresolved_id=f"A4TRU-{'4' * 32}", source_node_id=generic.node_id,
        reference_type=UnresolvedReferenceType.API_ENDPOINT,
        reference_value="POST api/bookings", reason_code="MALFORMED_API_ENDPOINT",
    )
    result = assess(O.API_TEST_CASES, graph(generic, unresolved=(malformed,)))
    assert result[0][0].status is Status.NOT_READY
    assert any(malformed.unresolved_id in item.related_finding_ids for item in result[1])


def test_integration_requires_a_trusted_interaction_not_merely_two_components():
    component = node(1, N.ARCHITECTURE_COMPONENT, A.SYSTEM_ARCHITECTURE)
    entity = node(2, N.DATA_ENTITY, A.DATABASE_SCHEMA)
    assert status(O.INTEGRATION_TEST_CASES, graph(component, entity)) is Status.NOT_READY
    operation = node(3, N.API_ENDPOINT, A.API_SPECIFICATION, api=("GET", "/bookings"))
    interaction = link(1, operation, entity, R.USES_ENTITY)
    assert status(O.INTEGRATION_TEST_CASES, graph(operation, entity, links=(interaction,))) is Status.READY_WITH_WARNINGS
    persistence = node(4, N.SEMANTIC_TESTING_FACT, fact_type=F.STATE_PERSISTENCE)
    assert status(O.INTEGRATION_TEST_CASES, graph(operation, entity, persistence, links=(interaction,))) is Status.READY
    ambiguity = AmbiguousTraceabilityMatch(
        ambiguity_id=f"A4TRA-{'6' * 32}", source_node_id=operation.node_id,
        candidate_node_ids=sorted([component.node_id, entity.node_id]),
        evidence_method=TraceabilityEvidenceMethod.ENTITY_FIELD,
        reference_value="booking", reason_code="STRUCTURED_REFERENCE_HAS_MULTIPLE_TARGETS",
    )
    result = assess(O.INTEGRATION_TEST_CASES, graph(operation, component, entity, ambiguities=(ambiguity,)))
    assert result[0][0].status is Status.NOT_READY
    assert ambiguity.ambiguity_id in result[1][0].related_finding_ids


def test_e2e_accepts_ui_or_business_flow_and_handles_pending_images_output_aware():
    ui = node(1, N.UI_FLOW_STEP, A.UI_FLOW)
    acceptance = node(2, N.ACCEPTANCE_CRITERION, A.ACCEPTANCE_CRITERIA, external="AC-001")
    assert status(O.E2E_TEST_CASES, graph(ui, acceptance)) is Status.READY
    story = node(3, N.USER_STORY, A.USER_STORIES, external="US-001")
    relation = link(1, acceptance, story, R.VALIDATES)
    api = node(4, N.API_ENDPOINT, A.API_SPECIFICATION, api=("POST", "/orders"))
    assert status(O.E2E_TEST_CASES, graph(story, acceptance, api, links=(relation,))) is Status.READY
    image = node(5, N.GENERIC_EVIDENCE, A.WIREFRAMES)
    pending = UnresolvedTraceabilityReference(
        unresolved_id=f"A4TRU-{'5' * 32}", source_node_id=image.node_id,
        reference_type=UnresolvedReferenceType.IMAGE_PENDING_ANALYSIS,
        reference_value="flow.png", reason_code="IMAGE_HAS_NO_TRUSTED_TEXT_EVIDENCE",
    )
    assert status(O.E2E_TEST_CASES, graph(image, unresolved=(pending,))) is Status.NOT_READY
    assessment, findings, _ = assess(O.E2E_TEST_CASES, graph(ui, acceptance, image, unresolved=(pending,)))
    assert assessment[0].status is Status.READY_WITH_WARNINGS
    assert any(item.reason_code == "PENDING_IMAGE_CONTEXT" for item in findings)
    functional = assess(O.REGRESSION_TEST_CASES, graph(acceptance, image, unresolved=(pending,)))
    assert all(item.reason_code != "PENDING_IMAGE_CONTEXT" for item in functional[1])


def test_regression_security_and_acceptance_policies_are_conservative():
    baseline = node(1, N.FUNCTIONAL_REQUIREMENT, external="FR-001")
    assert status(O.REGRESSION_TEST_CASES, graph(baseline)) is Status.READY_WITH_WARNINGS
    assert status(O.REGRESSION_TEST_CASES, graph()) is Status.NOT_READY
    api = node(2, N.API_ENDPOINT, A.API_SPECIFICATION, api=("GET", "/users"))
    narrative = node(3, N.NON_FUNCTIONAL_REQUIREMENT, external="NFR-SECURITY")
    assert status(O.SECURITY_TEST_CASES, graph(api, narrative)) is Status.NOT_READY
    for index, fact_type in enumerate((F.AUTHENTICATION_REQUIREMENT, F.AUTHORIZATION_RULE, F.SECURITY_CONTROL), 4):
        concern = node(index, N.SEMANTIC_TESTING_FACT, fact_type=fact_type)
        assert status(O.SECURITY_TEST_CASES, graph(concern, narrative)) is Status.READY
    assert status(O.ACCEPTANCE_TEST_CASES, graph(baseline)) is Status.NOT_READY
    story = node(8, N.USER_STORY, A.USER_STORIES, external="US-001")
    assert status(O.ACCEPTANCE_TEST_CASES, graph(story)) is Status.NOT_READY
    acceptance = node(9, N.SEMANTIC_TESTING_FACT, fact_type=F.ACCEPTANCE_CONDITION)
    assert status(O.ACCEPTANCE_TEST_CASES, graph(acceptance, story)) is Status.READY


def test_nfr_performance_and_reliability_are_supporting_not_fabricated_outputs():
    nfr = node(1, N.NON_FUNCTIONAL_REQUIREMENT, A.NON_FUNCTIONAL_REQUIREMENTS, external="NFR-001")
    performance = node(2, N.SEMANTIC_TESTING_FACT, fact_type=F.PERFORMANCE_TARGET)
    reliability = node(3, N.SEMANTIC_TESTING_FACT, fact_type=F.RELIABILITY_RECOVERY)
    inventory = build_evidence_inventory(graph(nfr, performance, reliability))
    assert inventory.item(E.NON_FUNCTIONAL_REQUIREMENT_EVIDENCE).observed_count == 1
    assert inventory.item(E.PERFORMANCE_EVIDENCE).observed_count == 1
    assert inventory.item(E.RELIABILITY_EVIDENCE).observed_count == 1
    assert status(O.FUNCTIONAL_TEST_CASES, graph(nfr, performance, reliability)) is Status.NOT_READY
    assert status(O.SECURITY_TEST_CASES, graph(nfr, performance, reliability)) is Status.NOT_READY


def test_traceability_requires_stable_anchor_and_treats_partial_findings_as_warnings():
    broad = node(1, N.FUNCTIONAL_REQUIREMENT)
    assert status(O.TEST_TRACEABILITY, graph(broad)) is Status.NOT_READY
    anchor = node(2, N.FUNCTIONAL_REQUIREMENT, external="FR-001")
    assert status(O.TEST_TRACEABILITY, graph(anchor)) is Status.READY_WITH_WARNINGS
    target = node(3, N.USER_STORY, A.USER_STORIES, external="US-001")
    resolved = link(1, target, anchor, R.REFINES)
    dangling = UnresolvedTraceabilityReference(
        unresolved_id=f"A4TRU-{'7' * 32}", source_node_id=target.node_id,
        reference_type=UnresolvedReferenceType.EXPLICIT_ID,
        reference_value="FR-999", reason_code="EXPLICIT_REFERENCE_NOT_FOUND",
    )
    result = assess(O.TEST_TRACEABILITY, graph(anchor, target, links=(resolved,), unresolved=(dangling,)))
    assert result[0][0].status is Status.READY_WITH_WARNINGS
    assert any(item.reason_code == "UNRESOLVED_TRACEABILITY_REMAINS" for item in result[1])
    only_unresolved = UnresolvedTraceabilityReference(
        unresolved_id=f"A4TRU-{'8' * 32}", source_node_id=anchor.node_id,
        reference_type=UnresolvedReferenceType.EXPLICIT_ID,
        reference_value="US-404", reason_code="EXPLICIT_REFERENCE_NOT_FOUND",
    )
    blocked = assess(O.TEST_TRACEABILITY, graph(anchor, unresolved=(only_unresolved,)))
    assert blocked[0][0].status is Status.NOT_READY
    assert any(item.reason_code == "ALL_TRACEABILITY_ANCHORS_UNRESOLVED" for item in blocked[1])


def test_findings_are_deterministic_output_aware_auditable_and_not_questions():
    empty = graph()
    first = assess(O.API_TEST_CASES, empty)
    second = assess(O.API_TEST_CASES, empty)
    unit = assess(O.UNIT_TEST_CASES, empty)
    assert [item.finding_id for item in first[1]] == [item.finding_id for item in second[1]]
    assert first[1][0].finding_id != unit[1][0].finding_id
    assert first[1][0].required_evidence_categories == [E.API_ENDPOINT_EVIDENCE]
    assert first[1][0].observed_count == 0
    serialized = json.dumps([item.model_dump(mode="json") for item in first[1]])
    assert "?" not in serialized and "confidence" not in serialized.casefold()
    with pytest.raises(ValidationError, match="extra_forbidden"):
        type(first[1][0]).model_validate({**first[1][0].model_dump(), "question": "What is missing"})


def sample_result(value, output=O.FUNCTIONAL_TEST_CASES):
    inventory = build_evidence_inventory(value)
    graph_fp = fingerprint(value.model_dump(mode="json"))
    assessments, findings, overall = evaluate_testability([output], inventory, value, graph_fingerprint=graph_fp)
    return Agent4TestabilityResult(
        schema_version="1", engine_version="TB1", output_policy_version="OP1",
        agent_project_id=PROJECT, confirmation_id=value.confirmation_id,
        selection_revision=1, selected_outputs_digest="6" * 64,
        confirmed_selected_outputs=[output],
        traceability_input_fingerprint=value.input_fingerprint,
        traceability_manifest_fingerprint=graph_fp,
        traceability_finding_ids=sorted(
            [item.unresolved_id for item in value.unresolved_references]
            + [item.ambiguity_id for item in value.ambiguities]
        ),
        evidence_inventory=list(inventory.items), output_assessments=assessments,
        overall_status=overall,
        blocking_finding_count=sum(item.severity is FindingSeverity.BLOCKING for item in findings),
        warning_count=sum(item.severity is FindingSeverity.WARNING for item in findings),
        findings=findings, input_fingerprint="7" * 64, evaluated_at=NOW,
    )


def test_manifest_contract_storage_atomic_cleanup_and_corrupt_cache(tmp_path, monkeypatch):
    value = graph(node(1, N.FUNCTIONAL_REQUIREMENT, external="FR-001"))
    result = sample_result(value)
    storage = Agent4TestabilityStorage(tmp_path)
    storage.save(result, owner_user_id="USR-001")
    path = tmp_path / PROJECT / "context-testability" / "testability.json"
    assert path.is_file() and not path.with_suffix(".json.part").exists()
    assert storage.load(agent_project_id=PROJECT, owner_user_id="USR-001") == result
    with pytest.raises(Agent4TestabilityStorageError, match="identity"):
        storage.load(agent_project_id=PROJECT, owner_user_id="USR-002")
    path.write_text("{corrupt", encoding="utf-8")
    assert storage.load(agent_project_id=PROJECT, owner_user_id="USR-001") is None
    original = type(path).replace
    monkeypatch.setattr(type(path), "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(Agent4TestabilityStorageError):
        storage.save(result, owner_user_id="USR-001")
    assert not path.with_suffix(".json.part").exists()
    monkeypatch.setattr(type(path), "replace", original)


def test_project_service_uses_confirmed_outputs_cache_force_and_preserves_all_upstream(n2_context):
    project_id = completed_project(n2_context)
    root, runs = n2_context[3], n2_context[5]
    traceability = trace_service(n2_context)
    service = Agent4TestabilityService(
        n2_context[1]._workflow_service, Agent4WorkflowStorage(root), traceability,
        Agent4TestabilityStorage(root), clock=lambda: NOW,
    )
    traceability.build(project_id, user())
    trace_path = root / project_id / "context-testability" / "traceability.json"
    immutable = {
        path: path.read_bytes() for path in (root / project_id).rglob("*")
        if path.is_file()
    }
    first = service.evaluate(project_id, user())
    testability_path = root / project_id / "context-testability" / "testability.json"
    raw = testability_path.read_bytes()
    cached = service.evaluate(project_id, user())
    forced = service.evaluate(project_id, user(), force=True)
    assert first.confirmed_selected_outputs == [O.UNIT_TEST_CASES]
    assert cached.evaluated_at == first.evaluated_at and testability_path.read_bytes() == raw
    assert forced.input_fingerprint == first.input_fingerprint
    assert [item.finding_id for item in forced.findings] == [item.finding_id for item in first.findings]
    assert all(path.read_bytes() == content for path, content in immutable.items())
    assert trace_path.read_bytes() == immutable[trace_path]
    workflow = load(n2_context[0], project_id)
    assert [item["status"] for item in workflow["nodes"]] == [
        "COMPLETED", "COMPLETED", "COMPLETED", "NOT_STARTED", "LOCKED", "LOCKED",
    ]
    assert workflow["current_node_id"] == "CONTEXT_TESTABILITY"
    assert workflow["pipeline_status"] == "RUNNING" and runs.documents == {}
    serialized = testability_path.read_text(encoding="utf-8")
    for forbidden in ("SPECIFICATION_ONLY", "EXECUTABLE_POSSIBLE", "clarification_question", "test_case_plan"):
        assert forbidden not in serialized


def test_project_service_rejects_stale_traceability_identity(n2_context):
    project_id = completed_project(n2_context)
    traceability = trace_service(n2_context)
    valid = traceability.build(project_id, user())

    class StaleTraceability:
        @staticmethod
        def build(*_args, **_kwargs):
            return valid.model_copy(update={"confirmation_id": f"A4N1C-{'f' * 32}"})

    service = Agent4TestabilityService(
        n2_context[1]._workflow_service, Agent4WorkflowStorage(n2_context[3]),
        StaleTraceability(), Agent4TestabilityStorage(n2_context[3]), clock=lambda: NOW,
    )
    with pytest.raises(Agent4TestabilityGateError, match="TR1"):
        service.evaluate(project_id, user())


def test_project_service_rejects_stale_selection_and_rebuilds_corrupt_cache(n2_context):
    project_id = completed_project(n2_context)
    root = n2_context[3]
    workflows = Agent4WorkflowStorage(root)
    service = Agent4TestabilityService(
        n2_context[1]._workflow_service, workflows, trace_service(n2_context),
        Agent4TestabilityStorage(root), clock=lambda: NOW,
    )
    first = service.evaluate(project_id, user())
    path = root / project_id / "context-testability" / "testability.json"
    path.write_text("{corrupt", encoding="utf-8")
    rebuilt = service.evaluate(project_id, user())
    assert rebuilt.input_fingerprint == first.input_fingerprint
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "1"

    record = workflows.load(agent_project_id=project_id, owner_user_id=user().user_id)
    changed = record.model_copy(deep=True)
    changed.n1_confirmation.selection_digest = "0" * 64
    workflows.save(changed)
    with pytest.raises(Agent4TestabilityGateError, match="selected outputs are stale"):
        service.evaluate(project_id, user())
