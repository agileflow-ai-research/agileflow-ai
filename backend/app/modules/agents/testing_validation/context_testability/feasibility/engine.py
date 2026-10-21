from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    deterministic_id,
)
from app.modules.agents.testing_validation.context_testability.testability.schemas import (
    TestabilityStatus,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode as O

from .catalog import (
    API_FRAMEWORKS,
    FRAMEWORK_LANGUAGES,
    SECURITY_FRAMEWORKS,
    UI_FRAMEWORKS,
    UNIT_FRAMEWORKS,
)
from .constants import FEASIBILITY_POLICY_VERSION, TechnicalEvidenceCategory as C
from .policy import FEASIBILITY_POLICY_BY_OUTPUT
from .schemas import (
    FeasibilityFinding,
    FeasibilityFindingSeverity as Severity,
    FeasibilityStatus,
    GenerationProfile,
    OutputFeasibilityAssessment,
    RepresentationRecommendation,
)


def _refs(inventory, categories):
    items = [inventory.item(category) for category in categories]
    return {
        "nodes": sorted({value for item in items for value in item.node_ids}),
        "links": sorted({value for item in items for value in item.link_ids}),
        "facts": sorted({value for item in items for value in item.semantic_fact_ids}),
        "sources": sorted({value for item in items for value in item.source_ids}),
        "chunks": sorted({value for item in items for value in item.chunk_ids}),
        "values": sorted({value for item in items for value in item.values}),
    }


def _finding(output, reason, message, categories, inventory, input_fingerprint,
             severity=Severity.BLOCKING_EXECUTABLE):
    refs = _refs(inventory, categories)
    identity = {
        "policy": FEASIBILITY_POLICY_VERSION,
        "input": input_fingerprint,
        "output": output.value,
        "reason": reason,
        "categories": [item.value for item in categories],
        "values": refs["values"], "nodes": refs["nodes"],
        "links": refs["links"],
    }
    return FeasibilityFinding(
        finding_id=deterministic_id("A4FBF", identity), output_code=output,
        severity=severity, reason_code=reason, message=message,
        technical_categories=list(categories), evidence_values=refs["values"],
        related_node_ids=refs["nodes"], related_link_ids=refs["links"],
        semantic_fact_ids=refs["facts"], source_ids=refs["sources"],
        chunk_ids=refs["chunks"],
    )


def _eligible_frameworks(output, inventory):
    frameworks = set(inventory.values(C.TEST_FRAMEWORK))
    if output is O.UNIT_TEST_CASES:
        return frameworks & UNIT_FRAMEWORKS
    if output in {O.API_TEST_CASES, O.INTEGRATION_TEST_CASES}:
        return frameworks & API_FRAMEWORKS
    if output is O.SECURITY_TEST_CASES:
        return frameworks & SECURITY_FRAMEWORKS
    if output in {O.E2E_TEST_CASES, O.ACCEPTANCE_TEST_CASES}:
        if inventory.present(C.UI_WORKFLOW) or inventory.present(C.UI_ROUTE):
            ui = frameworks & UI_FRAMEWORKS
            if ui:
                return ui
        return frameworks & API_FRAMEWORKS
    if output is O.FUNCTIONAL_TEST_CASES:
        if inventory.present(C.UI_WORKFLOW) or inventory.present(C.UI_ROUTE):
            return (frameworks & UI_FRAMEWORKS) or (frameworks & API_FRAMEWORKS)
        return frameworks & (API_FRAMEWORKS | UNIT_FRAMEWORKS)
    if output is O.REGRESSION_TEST_CASES:
        return frameworks & (API_FRAMEWORKS | UNIT_FRAMEWORKS | UI_FRAMEWORKS)
    return set()


def _select_toolchain(output, inventory, findings, input_fingerprint):
    languages = set(inventory.values(C.PROGRAMMING_LANGUAGE))
    frameworks = _eligible_frameworks(output, inventory)
    versions = inventory.values(C.RUNTIME_VERSION)
    version_groups = {}
    for value in versions:
        runtime, _, version = value.partition(":")
        version_groups.setdefault(runtime, set()).add(version)

    if len(languages) > 1:
        findings.append(_finding(
            output, "AMBIGUOUS_TEST_LANGUAGE",
            "Multiple target-system programming languages are present without an output-specific scope.",
            (C.PROGRAMMING_LANGUAGE,), inventory, input_fingerprint,
        ))
    elif not languages:
        findings.append(_finding(
            output, "MISSING_TEST_LANGUAGE",
            "No trusted target-system test language is available.",
            (C.PROGRAMMING_LANGUAGE,), inventory, input_fingerprint,
        ))
    if len(frameworks) > 1:
        findings.append(_finding(
            output, "AMBIGUOUS_TEST_FRAMEWORK",
            "Multiple compatible test frameworks are present without an output-specific scope.",
            (C.TEST_FRAMEWORK,), inventory, input_fingerprint,
        ))
    elif not frameworks:
        findings.append(_finding(
            output, "MISSING_TEST_FRAMEWORK",
            "No explicit compatible test framework is available for this output.",
            (C.TEST_FRAMEWORK,), inventory, input_fingerprint,
        ))
    if any(len(values) > 1 for values in version_groups.values()):
        findings.append(_finding(
            output, "AMBIGUOUS_RUNTIME_VERSION",
            "Conflicting runtime versions are present without an output-specific scope.",
            (C.RUNTIME_VERSION,), inventory, input_fingerprint,
        ))
    if len(languages) != 1 or len(frameworks) != 1 or any(
        len(values) > 1 for values in version_groups.values()
    ):
        return None
    language, framework = next(iter(languages)), next(iter(frameworks))
    if language not in FRAMEWORK_LANGUAGES[framework]:
        findings.append(_finding(
            output, "INCOMPATIBLE_TEST_TOOLCHAIN",
            "The explicit language and test framework do not form a supported deterministic toolchain.",
            (C.PROGRAMMING_LANGUAGE, C.TEST_FRAMEWORK), inventory,
            input_fingerprint,
        ))
        return None
    return language, framework


def _surface(output, inventory, findings, input_fingerprint):
    def require(category, reason, message):
        if inventory.present(category):
            return True
        findings.append(_finding(
            output, reason, message, (category,), inventory, input_fingerprint
        ))
        return False

    if output is O.UNIT_TEST_CASES:
        return "UNIT" if require(
            C.MODULE_COMPONENT_BOUNDARY, "MISSING_COMPONENT_BOUNDARY",
            "No trusted localized component, module, or function boundary is available.",
        ) else None
    if output is O.API_TEST_CASES:
        available = require(
            C.API_OPERATION, "MISSING_AUTOMATION_SURFACE",
            "No trusted API method and path are available for executable generation.",
        )
        if inventory.present(C.AUTHENTICATION_REQUIRED) and not inventory.present(C.AUTHENTICATION_SETUP):
            findings.append(_finding(
                output, "MISSING_AUTH_SETUP",
                "Authentication is required, but no trusted request authentication setup is available.",
                (C.AUTHENTICATION_REQUIRED, C.AUTHENTICATION_SETUP), inventory,
                input_fingerprint,
            ))
            available = False
        return "API" if available else None
    if output is O.INTEGRATION_TEST_CASES:
        boundary = require(
            C.INTEGRATION_BOUNDARY, "MISSING_AUTOMATION_SURFACE",
            "No trusted executable integration boundary is available.",
        )
        detail = any(inventory.present(item) for item in (
            C.SERVICE_INTERFACE, C.DATA_INTERFACE, C.MOCKABLE_BOUNDARY,
        ))
        if not detail:
            findings.append(_finding(
                output, "INSUFFICIENT_INTERFACE_DETAIL",
                "The interaction lacks trusted interface or mock-boundary detail.",
                (C.SERVICE_INTERFACE, C.DATA_INTERFACE, C.MOCKABLE_BOUNDARY),
                inventory, input_fingerprint,
            ))
        return "INTEGRATION" if boundary and detail else None
    if output in {O.FUNCTIONAL_TEST_CASES, O.ACCEPTANCE_TEST_CASES}:
        if inventory.present(C.UI_WORKFLOW) or inventory.present(C.UI_ROUTE):
            return "UI"
        if inventory.present(C.API_OPERATION):
            return "API"
        if inventory.present(C.SERVICE_INTERFACE) or inventory.present(C.FUNCTION_SIGNATURE):
            return "SERVICE"
        findings.append(_finding(
            output, "MISSING_AUTOMATION_SURFACE",
            "No trusted UI, API, or service automation surface is available.",
            (C.UI_WORKFLOW, C.UI_ROUTE, C.API_OPERATION, C.SERVICE_INTERFACE),
            inventory, input_fingerprint,
        ))
        return None
    if output is O.E2E_TEST_CASES:
        if inventory.present(C.UI_WORKFLOW) and (
            inventory.present(C.UI_ROUTE) or inventory.present(C.UI_ELEMENT_OR_SELECTOR)
        ):
            return "E2E"
        if inventory.present(C.API_OPERATION):
            return "E2E"
        findings.append(_finding(
            output, "MISSING_AUTOMATION_SURFACE",
            "The business flow has no trusted executable UI route/selector or API operation.",
            (C.UI_WORKFLOW, C.UI_ROUTE, C.UI_ELEMENT_OR_SELECTOR, C.API_OPERATION),
            inventory, input_fingerprint,
        ))
        return None
    if output is O.REGRESSION_TEST_CASES:
        if inventory.present(C.UI_WORKFLOW) or inventory.present(C.UI_ROUTE):
            return "REGRESSION"
        if inventory.present(C.API_OPERATION) or inventory.present(C.MODULE_COMPONENT_BOUNDARY):
            return "REGRESSION"
        findings.append(_finding(
            output, "MISSING_AUTOMATION_SURFACE",
            "No trusted executable unit, API, UI, or service surface supports regression code generation.",
            (C.MODULE_COMPONENT_BOUNDARY, C.API_OPERATION, C.UI_WORKFLOW, C.UI_ROUTE),
            inventory, input_fingerprint,
        ))
        return None
    if output is O.SECURITY_TEST_CASES:
        target = require(
            C.SECURITY_TARGET, "MISSING_AUTOMATION_SURFACE",
            "No concrete trusted security target is available for executable checks.",
        )
        interface = inventory.present(C.API_OPERATION) or inventory.present(C.UI_ROUTE) or inventory.present(C.SERVICE_INTERFACE)
        if not interface:
            findings.append(_finding(
                output, "INSUFFICIENT_INTERFACE_DETAIL",
                "The security concern has no trusted API, UI, or service interface for executable checks.",
                (C.API_OPERATION, C.UI_ROUTE, C.SERVICE_INTERFACE), inventory,
                input_fingerprint,
            ))
        return "SECURITY" if target and interface else None
    return None


def evaluate_output_feasibility(output, testability, inventory, *, input_fingerprint):
    policy = FEASIBILITY_POLICY_BY_OUTPUT[output]
    if testability.status is TestabilityStatus.NOT_READY:
        finding = _finding(
            output, "SEMANTIC_TESTABILITY_NOT_READY",
            "N4.2 mandatory semantic planning context is not ready.",
            (), inventory, input_fingerprint,
        )
        return _assessment(
            output, testability.status, FeasibilityStatus.NOT_READY, None,
            None, [finding], inventory,
        ), [finding]
    if policy.structured_artifact_only:
        return _assessment(
            output, testability.status, FeasibilityStatus.SPECIFICATION_ONLY,
            RepresentationRecommendation.STRUCTURED_ARTIFACT, None, [], inventory,
            reason_codes=["STRUCTURED_ARTIFACT_NOT_EXECUTABLE"],
        ), []

    findings = []
    toolchain = _select_toolchain(output, inventory, findings, input_fingerprint)
    surface = _surface(output, inventory, findings, input_fingerprint)
    executable = toolchain is not None and surface is not None
    profile = None
    if executable:
        language, framework = toolchain
        categories = (
            C.PROGRAMMING_LANGUAGE, C.TEST_FRAMEWORK, C.PACKAGE_ECOSYSTEM,
            C.BACKEND_FRAMEWORK, C.FRONTEND_FRAMEWORK,
        )
        refs = _refs(inventory, categories)
        profile = GenerationProfile(
            language=language, test_framework=framework,
            automation_surface=surface,
            package_ecosystem=_single(inventory.values(C.PACKAGE_ECOSYSTEM)),
            backend_framework=_single(inventory.values(C.BACKEND_FRAMEWORK)),
            frontend_framework=_single(inventory.values(C.FRONTEND_FRAMEWORK)),
            evidence_node_ids=refs["nodes"], evidence_link_ids=refs["links"],
        )
    return _assessment(
        output, testability.status,
        FeasibilityStatus.EXECUTABLE_POSSIBLE if executable else FeasibilityStatus.SPECIFICATION_ONLY,
        RepresentationRecommendation.EXECUTABLE_CODE if executable else RepresentationRecommendation.SPECIFICATION,
        profile, findings, inventory,
    ), findings


def _single(values):
    return values[0] if len(values) == 1 else None


def _assessment(output, n4_2_status, feasibility, representation, profile,
                findings, inventory, reason_codes=None):
    categories = sorted(
        [item.category for item in inventory.items if item.values],
        key=lambda item: item.value,
    )
    refs = _refs(inventory, categories)
    return OutputFeasibilityAssessment(
        output_code=output, n4_2_status=n4_2_status,
        feasibility=feasibility, recommended_representation=representation,
        policy_version=FEASIBILITY_POLICY_VERSION,
        technical_evidence_categories=categories, generation_profile=profile,
        execution_status="NOT_EXECUTED" if feasibility is FeasibilityStatus.EXECUTABLE_POSSIBLE else None,
        finding_ids=sorted(item.finding_id for item in findings),
        evidence_node_ids=refs["nodes"], evidence_link_ids=refs["links"],
        semantic_fact_ids=refs["facts"], source_ids=refs["sources"],
        chunk_ids=refs["chunks"],
        reason_codes=sorted(set(reason_codes or [item.reason_code for item in findings])),
    )


def evaluate_feasibility(selected_outputs, testability_assessments, inventory,
                         *, input_fingerprint):
    by_output = {item.output_code: item for item in testability_assessments}
    assessments, findings = [], []
    for output in selected_outputs:
        assessment, output_findings = evaluate_output_feasibility(
            output, by_output[output], inventory,
            input_fingerprint=input_fingerprint,
        )
        assessments.append(assessment)
        findings.extend(output_findings)
    findings = sorted({item.finding_id: item for item in findings}.values(), key=lambda item: item.finding_id)
    values = {item.feasibility for item in assessments}
    overall = (
        FeasibilityStatus.NOT_READY if FeasibilityStatus.NOT_READY in values
        else FeasibilityStatus.EXECUTABLE_POSSIBLE
        if values == {FeasibilityStatus.EXECUTABLE_POSSIBLE}
        else FeasibilityStatus.SPECIFICATION_ONLY
    )
    return assessments, findings, overall
