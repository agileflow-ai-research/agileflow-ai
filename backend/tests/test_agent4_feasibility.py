import json
import os
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.agents.testing_validation.context_testability.feasibility.catalog import (
    TECHNOLOGY_PATTERNS,
)
from app.modules.agents.testing_validation.context_testability.feasibility.constants import (
    FEASIBILITY_ENGINE_VERSION,
    FEASIBILITY_POLICY_VERSION,
    FEASIBILITY_SCHEMA_VERSION,
    TECHNOLOGY_CATALOG_VERSION,
    TechnicalEvidenceCategory as C,
)
from app.modules.agents.testing_validation.context_testability.feasibility.engine import (
    evaluate_feasibility,
)
from app.modules.agents.testing_validation.context_testability.feasibility.extractor import (
    build_technical_evidence_inventory,
)
from app.modules.agents.testing_validation.context_testability.feasibility.policy import (
    FEASIBILITY_POLICIES,
    FEASIBILITY_POLICY_BY_OUTPUT,
)
from app.modules.agents.testing_validation.context_testability.feasibility.schemas import (
    Agent4FeasibilityResult,
    FeasibilityFindingSeverity as FindingSeverity,
    FeasibilityStatus as Status,
    RepresentationRecommendation as Representation,
)
from app.modules.agents.testing_validation.context_testability.feasibility.service import (
    Agent4FeasibilityGateError,
    Agent4FeasibilityService,
)
from app.modules.agents.testing_validation.context_testability.feasibility.storage import (
    Agent4FeasibilityStorage,
    Agent4FeasibilityStorageError,
)
from app.modules.agents.testing_validation.context_testability.testability.schemas import (
    TestabilityStatus as TBStatus,
)
from app.modules.agents.testing_validation.context_testability.testability.service import (
    Agent4TestabilityService,
)
from app.modules.agents.testing_validation.context_testability.testability.storage import (
    Agent4TestabilityStorage,
)
from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    fingerprint,
)
from app.modules.agents.testing_validation.context_testability.traceability.schemas import (
    TraceabilityNodeKind as N,
    TraceabilityRelationType as R,
)
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType as A,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticFactType as F,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode as O
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from test_agent4_n2_orchestration import load, n2_context
from test_agent4_testability import graph, link, node
from test_agent4_traceability import completed_project, trace_service
from test_standalone_foundation import user


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


def text_node(index, text, *, kind=N.ARCHITECTURE_COMPONENT,
              artifact=A.SYSTEM_ARCHITECTURE, fact_type=None):
    value = node(index, kind, artifact, fact_type=fact_type)
    return value.model_copy(update={
        "display_value": text,
        "canonical_value": " ".join(text.casefold().split())[:500],
    })


def tb(output, status=TBStatus.READY):
    return SimpleNamespace(output_code=output, status=status)


def evaluate(outputs, value, statuses=None):
    inventory = build_technical_evidence_inventory(value)
    assessments = [tb(output, (statuses or {}).get(output, TBStatus.READY)) for output in outputs]
    return evaluate_feasibility(
        outputs, assessments, inventory,
        input_fingerprint=fingerprint({
            "graph": value.input_fingerprint,
            "technical": inventory.fingerprint,
            "outputs": [item.value for item in outputs],
        }),
    ), inventory


def test_versions_states_policy_and_catalog_are_exact_immutable_and_canonical():
    assert (
        FEASIBILITY_SCHEMA_VERSION, FEASIBILITY_ENGINE_VERSION,
        FEASIBILITY_POLICY_VERSION, TECHNOLOGY_CATALOG_VERSION,
    ) == ("1", "FB1", "FP1", "TC1")
    assert {item.value for item in Status} == {
        "NOT_READY", "SPECIFICATION_ONLY", "EXECUTABLE_POSSIBLE",
    }
    assert tuple(item.output_code for item in FEASIBILITY_POLICIES) == tuple(O)
    assert len(FEASIBILITY_POLICY_BY_OUTPUT) == len(O) == 9
    with pytest.raises(TypeError):
        FEASIBILITY_POLICY_BY_OUTPUT[O.UNIT_TEST_CASES] = FEASIBILITY_POLICIES[0]
    with pytest.raises(TypeError):
        TECHNOLOGY_PATTERNS[C.TEST_FRAMEWORK] = ()
    baseline = fingerprint([asdict(item) for item in FEASIBILITY_POLICIES])
    changed = replace(FEASIBILITY_POLICIES[0], description="changed")
    assert baseline != fingerprint([asdict(changed), *map(asdict, FEASIBILITY_POLICIES[1:])])


def test_technical_extraction_detects_explicit_stack_and_rejects_narrative_false_positives():
    explicit = text_node(1, """Language: Python
Test framework: pytest
Backend framework: FastAPI
Frontend framework: React
Dependency manifest: requirements.txt
Build tool: Maven
Database: PostgreSQL
Container: Docker""")
    narrative = text_node(2, "Monty Python watched people react to a story and go to checkout.")
    first = build_technical_evidence_inventory(graph(explicit, narrative))
    second = build_technical_evidence_inventory(graph(explicit, narrative))
    assert first.values(C.PROGRAMMING_LANGUAGE) == ["PYTHON"]
    assert first.values(C.TEST_FRAMEWORK) == ["PYTEST"]
    assert first.values(C.BACKEND_FRAMEWORK) == ["FASTAPI"]
    assert first.values(C.FRONTEND_FRAMEWORK) == ["REACT"]
    assert first.values(C.DEPENDENCY_MANIFEST_TYPE) == ["REQUIREMENTS_TXT"]
    assert first.values(C.PACKAGE_ECOSYSTEM) == ["MAVEN", "PIP"]
    assert first.values(C.DATABASE_TECHNOLOGY) == ["POSTGRESQL"]
    assert first.values(C.CONTAINER_CONTEXT) == ["DOCKER"]
    assert first.fingerprint == second.fingerprint


@pytest.mark.parametrize(
    ("text", "category", "expected"),
    (
        ("Language: Java", C.PROGRAMMING_LANGUAGE, "JAVA"),
        ("Language: TypeScript", C.PROGRAMMING_LANGUAGE, "TYPESCRIPT"),
        ("Test framework: JUnit 5", C.TEST_FRAMEWORK, "JUNIT"),
        ("E2E test framework: Playwright", C.TEST_FRAMEWORK, "PLAYWRIGHT"),
        ("Frontend framework: Angular", C.FRONTEND_FRAMEWORK, "ANGULAR"),
        ("Backend framework: Spring Boot", C.BACKEND_FRAMEWORK, "SPRING_BOOT"),
    ),
)
def test_technology_catalog_retains_supported_explicit_values(text, category, expected):
    inventory = build_technical_evidence_inventory(graph(text_node(1, text)))
    assert expected in inventory.values(category)


def test_host_and_agileflow_environment_never_fabricate_target_evidence(monkeypatch):
    monkeypatch.setenv("TARGET_LANGUAGE", "Python")
    monkeypatch.setenv("TEST_FRAMEWORK", "pytest")
    before = (sys.version, "pytest" in sys.modules, os.name)
    inventory = build_technical_evidence_inventory(graph())
    after = (sys.version, "pytest" in sys.modules, os.name)
    assert before == after
    assert inventory.values(C.PROGRAMMING_LANGUAGE) == []
    assert inventory.values(C.TEST_FRAMEWORK) == []
    assert inventory.values(C.BACKEND_FRAMEWORK) == []
    assert inventory.values(C.FRONTEND_FRAMEWORK) == []


def test_n4_2_gate_and_overall_aggregation_are_conservative_and_selected_only():
    stack = text_node(1, "Language: Python\nTest framework: pytest")
    blocked = evaluate(
        [O.UNIT_TEST_CASES], graph(stack),
        {O.UNIT_TEST_CASES: TBStatus.NOT_READY},
    )[0]
    assert blocked[0][0].feasibility is Status.NOT_READY
    assert blocked[0][0].recommended_representation is None
    spec = evaluate([O.API_TEST_CASES], graph(node(2, N.API_ENDPOINT, A.API_SPECIFICATION, api=("GET", "/users"))))[0]
    assert spec[0][0].feasibility is Status.SPECIFICATION_ONLY
    ready = evaluate([O.UNIT_TEST_CASES], graph(stack))[0]
    assert ready[0][0].feasibility is Status.EXECUTABLE_POSSIBLE
    warned = evaluate(
        [O.UNIT_TEST_CASES], graph(stack),
        {O.UNIT_TEST_CASES: TBStatus.READY_WITH_WARNINGS},
    )[0]
    assert warned[0][0].feasibility is Status.EXECUTABLE_POSSIBLE
    mixed = evaluate([O.UNIT_TEST_CASES, O.API_TEST_CASES], graph(stack))[0]
    assert mixed[2] is Status.SPECIFICATION_ONLY
    assert [item.output_code for item in mixed[0]] == [O.UNIT_TEST_CASES, O.API_TEST_CASES]


def test_unit_requires_explicit_compatible_toolchain_and_local_boundary():
    boundary = text_node(1, "Component: BookingService")
    assert evaluate([O.UNIT_TEST_CASES], graph(boundary))[0][0][0].feasibility is Status.SPECIFICATION_ONLY
    no_boundary = text_node(2, "Language: Python\nTest framework: pytest", kind=N.GENERIC_EVIDENCE)
    result = evaluate([O.UNIT_TEST_CASES], graph(no_boundary))[0]
    assert result[0][0].feasibility is Status.SPECIFICATION_ONLY
    assert "MISSING_COMPONENT_BOUNDARY" in result[0][0].reason_codes
    complete = text_node(3, "Language: Java\nTest framework: JUnit\nComponent: BookingService")
    assessment = evaluate([O.UNIT_TEST_CASES], graph(complete))[0][0][0]
    assert assessment.feasibility is Status.EXECUTABLE_POSSIBLE
    assert (assessment.generation_profile.language, assessment.generation_profile.test_framework) == ("JAVA", "JUNIT")
    assert assessment.execution_status == "NOT_EXECUTED"
    assert "BookingService" not in assessment.model_dump_json()


def test_api_feasibility_needs_explicit_stack_but_not_live_base_url_and_respects_auth():
    operation = node(1, N.API_ENDPOINT, A.API_SPECIFICATION, api=("POST", "/orders"))
    assert evaluate([O.API_TEST_CASES], graph(operation))[0][0][0].feasibility is Status.SPECIFICATION_ONLY
    stack = text_node(2, "Language: TypeScript\nTest framework: Vitest", kind=N.GENERIC_EVIDENCE)
    executable = evaluate([O.API_TEST_CASES], graph(operation, stack))[0][0][0]
    assert executable.feasibility is Status.EXECUTABLE_POSSIBLE
    assert executable.generation_profile.automation_surface == "API"
    auth = text_node(
        3, "Authentication is required.", kind=N.SEMANTIC_TESTING_FACT,
        artifact=A.API_SPECIFICATION, fact_type=F.AUTHENTICATION_REQUIREMENT,
    )
    missing = evaluate([O.API_TEST_CASES], graph(operation, stack, auth))[0]
    assert missing[0][0].feasibility is Status.SPECIFICATION_ONLY
    assert "MISSING_AUTH_SETUP" in missing[0][0].reason_codes
    setup = text_node(4, "Authentication setup: Bearer token", kind=N.GENERIC_EVIDENCE, artifact=A.API_SPECIFICATION)
    assert evaluate([O.API_TEST_CASES], graph(operation, stack, auth, setup))[0][0][0].feasibility is Status.EXECUTABLE_POSSIBLE


def test_integration_requires_interface_detail_and_never_invents_mocks():
    operation = node(1, N.API_ENDPOINT, A.API_SPECIFICATION, api=("GET", "/orders"))
    entity = node(2, N.DATA_ENTITY, A.DATABASE_SCHEMA)
    relation = link(1, operation, entity, R.USES_ENTITY)
    stack = text_node(3, "Language: Python\nTest framework: pytest", kind=N.GENERIC_EVIDENCE)
    executable = evaluate([O.INTEGRATION_TEST_CASES], graph(operation, entity, stack, links=(relation,)))[0][0][0]
    assert executable.feasibility is Status.EXECUTABLE_POSSIBLE
    assert "mock" not in executable.model_dump_json().casefold()
    without_stack = evaluate([O.INTEGRATION_TEST_CASES], graph(operation, entity, links=(relation,)))[0][0][0]
    assert without_stack.feasibility is Status.SPECIFICATION_ONLY
    components = text_node(4, "Language: Python\nTest framework: pytest")
    sparse = evaluate([O.INTEGRATION_TEST_CASES], graph(components))[0]
    assert sparse[0][0].feasibility is Status.SPECIFICATION_ONLY
    assert "MISSING_AUTOMATION_SURFACE" in sparse[0][0].reason_codes


def test_functional_e2e_and_acceptance_require_concrete_automation_surface():
    flow = text_node(1, "User completes checkout.", kind=N.UI_FLOW_STEP, artifact=A.UI_FLOW)
    spec = evaluate([O.E2E_TEST_CASES], graph(flow))[0][0][0]
    assert spec.feasibility is Status.SPECIFICATION_ONLY
    ui = text_node(2, "Language: TypeScript\nE2E test framework: Playwright\nRoute: /checkout\nSelector: data-testid=submit")
    for output in (O.FUNCTIONAL_TEST_CASES, O.E2E_TEST_CASES, O.ACCEPTANCE_TEST_CASES):
        assessment = evaluate([output], graph(flow, ui))[0][0][0]
        assert assessment.feasibility is Status.EXECUTABLE_POSSIBLE
        assert assessment.generation_profile.test_framework == "PLAYWRIGHT"
    gwt = text_node(3, "Given an order When checkout completes Then confirmation appears", kind=N.GENERIC_EVIDENCE)
    assert evaluate([O.ACCEPTANCE_TEST_CASES], graph(gwt))[0][0][0].feasibility is Status.SPECIFICATION_ONLY
    assert "CUCUMBER" not in build_technical_evidence_inventory(graph(gwt)).values(C.TEST_FRAMEWORK)


def test_regression_security_and_traceability_policies_preserve_representation_truth():
    baseline = text_node(1, "Component: BookingService")
    assert evaluate([O.REGRESSION_TEST_CASES], graph(baseline))[0][0][0].feasibility is Status.SPECIFICATION_ONLY
    stack = text_node(2, "Language: Python\nTest framework: pytest")
    assert evaluate([O.REGRESSION_TEST_CASES], graph(baseline, stack))[0][0][0].feasibility is Status.EXECUTABLE_POSSIBLE
    security = text_node(
        3, "Only administrators may delete.", kind=N.SEMANTIC_TESTING_FACT,
        fact_type=F.AUTHORIZATION_RULE,
    )
    assert evaluate([O.SECURITY_TEST_CASES], graph(security))[0][0][0].feasibility is Status.SPECIFICATION_ONLY
    operation = node(4, N.API_ENDPOINT, A.API_SPECIFICATION, api=("DELETE", "/users/{id}"))
    secured = evaluate([O.SECURITY_TEST_CASES], graph(security, operation, stack))[0][0][0]
    assert secured.feasibility is Status.EXECUTABLE_POSSIBLE
    assert not any(tool in secured.model_dump_json() for tool in ("NMAP", "BURP", "SQLMAP"))
    trace = evaluate([O.TEST_TRACEABILITY], graph())[0]
    assert trace[0][0].feasibility is Status.SPECIFICATION_ONLY
    assert trace[0][0].recommended_representation is Representation.STRUCTURED_ARTIFACT
    assert trace[2] is Status.SPECIFICATION_ONLY


def test_framework_and_runtime_conflicts_downgrade_without_arbitrary_selection():
    conflicting = text_node(1, """Language: TypeScript
Test framework: Jest
Test framework: Vitest
Runtime: Node 20
Runtime: Node 22
Component: BookingService""")
    first = evaluate([O.UNIT_TEST_CASES], graph(conflicting))[0]
    second = evaluate([O.UNIT_TEST_CASES], graph(conflicting))[0]
    assessment = first[0][0]
    assert assessment.feasibility is Status.SPECIFICATION_ONLY
    assert assessment.generation_profile is None
    assert {"AMBIGUOUS_TEST_FRAMEWORK", "AMBIGUOUS_RUNTIME_VERSION"}.issubset(assessment.reason_codes)
    assert [item.finding_id for item in first[1]] == [item.finding_id for item in second[1]]
    assert all("?" not in item.message for item in first[1])
    assert "confidence" not in json.dumps([item.model_dump(mode="json") for item in first[1]]).casefold()


def sample_result(value):
    (assessments, findings, overall), inventory = evaluate([O.UNIT_TEST_CASES], value)
    return Agent4FeasibilityResult(
        schema_version="1", engine_version="FB1", policy_version="FP1",
        technology_catalog_version="TC1", agent_project_id="AGP-100",
        confirmation_id=value.confirmation_id, selection_revision=1,
        selected_outputs_digest="6" * 64, selected_outputs=[O.UNIT_TEST_CASES],
        traceability_manifest_fingerprint="7" * 64,
        testability_input_fingerprint="8" * 64,
        testability_result_fingerprint="9" * 64,
        technical_evidence_fingerprint=inventory.fingerprint,
        technical_evidence_inventory=list(inventory.items),
        output_assessments=assessments, overall_feasibility=overall,
        blocking_executable_finding_count=sum(item.severity is FindingSeverity.BLOCKING_EXECUTABLE for item in findings),
        warning_count=sum(item.severity is FindingSeverity.WARNING for item in findings),
        findings=findings, input_fingerprint="a" * 64, evaluated_at=NOW,
    )


def test_storage_is_separate_atomic_owner_scoped_and_cleans_partial(tmp_path, monkeypatch):
    result = sample_result(graph(text_node(1, "Language: Python\nTest framework: pytest")))
    storage = Agent4FeasibilityStorage(tmp_path)
    storage.save(result, owner_user_id="USR-001")
    path = tmp_path / "AGP-100" / "context-testability" / "feasibility.json"
    assert path.is_file() and not path.with_suffix(".json.part").exists()
    assert storage.load(agent_project_id="AGP-100", owner_user_id="USR-001") == result
    with pytest.raises(Agent4FeasibilityStorageError, match="identity"):
        storage.load(agent_project_id="AGP-100", owner_user_id="USR-002")
    path.write_text("{corrupt", encoding="utf-8")
    assert storage.load(agent_project_id="AGP-100", owner_user_id="USR-001") is None
    original = type(path).replace
    monkeypatch.setattr(type(path), "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(Agent4FeasibilityStorageError):
        storage.save(result, owner_user_id="USR-001")
    assert not path.with_suffix(".json.part").exists()
    monkeypatch.setattr(type(path), "replace", original)


def feasibility_service(context):
    root = context[3]
    traceability = trace_service(context)
    testability = Agent4TestabilityService(
        context[1]._workflow_service, Agent4WorkflowStorage(root), traceability,
        Agent4TestabilityStorage(root), clock=lambda: NOW,
    )
    return Agent4FeasibilityService(
        context[1]._workflow_service, Agent4WorkflowStorage(root), traceability,
        testability, Agent4FeasibilityStorage(root), clock=lambda: NOW,
    ), traceability, testability


def test_service_cache_force_trust_and_upstream_immutability(n2_context):
    project_id = completed_project(n2_context)
    root, runs = n2_context[3], n2_context[5]
    service, _, testability = feasibility_service(n2_context)
    testability.evaluate(project_id, user())
    immutable = {path: path.read_bytes() for path in (root / project_id).rglob("*") if path.is_file()}
    first = service.evaluate(project_id, user())
    path = root / project_id / "context-testability" / "feasibility.json"
    raw = path.read_bytes()
    cached = service.evaluate(project_id, user())
    forced = service.evaluate(project_id, user(), force=True)
    assert cached.evaluated_at == first.evaluated_at and path.read_bytes() == raw
    assert forced.input_fingerprint == first.input_fingerprint
    assert [item.finding_id for item in forced.findings] == [item.finding_id for item in first.findings]
    assert all(path.read_bytes() == content for path, content in immutable.items())
    workflow = load(n2_context[0], project_id)
    assert [item["status"] for item in workflow["nodes"]] == [
            "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "NOT_STARTED", "LOCKED", "LOCKED",
    ]
    assert workflow["current_node_id"] == "CONTEXT_TESTABILITY"
    assert workflow["pipeline_status"] == "RUNNING" and runs.documents == {}
    names = [item.name.casefold() for item in (root / project_id).rglob("*") if item.is_file()]
    assert not any(marker in name for name in names for marker in (
        "clarification", "test-case-plan", "generated-test", "execution-result",
    ))


def test_service_rejects_stale_tb1_and_corrupt_cache_rebuilds(n2_context):
    project_id = completed_project(n2_context)
    root = n2_context[3]
    service, traceability, testability = feasibility_service(n2_context)
    first = service.evaluate(project_id, user())
    path = root / project_id / "context-testability" / "feasibility.json"
    path.write_text("{corrupt", encoding="utf-8")
    assert service.evaluate(project_id, user()).input_fingerprint == first.input_fingerprint

    current = testability.evaluate(project_id, user())

    class StaleTestability:
        @staticmethod
        def evaluate(*_args, **_kwargs):
            return current.model_copy(update={"traceability_manifest_fingerprint": "0" * 64})

    stale = Agent4FeasibilityService(
        n2_context[1]._workflow_service, Agent4WorkflowStorage(root), traceability,
        StaleTestability(), Agent4FeasibilityStorage(root), clock=lambda: NOW,
    )
    with pytest.raises(Agent4FeasibilityGateError, match="TB1"):
        stale.evaluate(project_id, user())


def test_contracts_reject_execution_claims_questions_and_extra_fields():
    result = sample_result(graph(text_node(1, "Language: Python\nTest framework: pytest")))
    serialized = result.model_dump_json()
    for forbidden in ('"execution_status":"EXECUTED"', '"PASS"', '"FAIL"', "RUNNABLE_NOW", "DEPLOYABLE"):
        assert forbidden not in serialized
    finding = result.findings[0] if result.findings else evaluate([O.API_TEST_CASES], graph())[0][1][0]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        type(finding).model_validate({**finding.model_dump(), "clarification_question": "Which framework"})
