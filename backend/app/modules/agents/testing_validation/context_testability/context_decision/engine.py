"""
Pure CD1 consolidation engine (N4.4). No I/O, no model, no re-evaluation.

It takes the persisted TB1 testability result and FB1 feasibility result for the
selected outputs, and produces three things:
  - an OutputContextDecisionProfile per output (PROCEED / PROCEED_WITH_WARNINGS / BLOCKED),
  - a DownstreamPlanningProfile per output (planning_allowed for N5),
  - deduplicated ConsolidatedContextFindings with their origin references.

Decision mapping:
  BLOCKED                 TB1 NOT_READY. Planning is not allowed.
  PROCEED_WITH_WARNINGS   TB1 READY_WITH_WARNINGS, or FB1 SPECIFICATION_ONLY that
                          is not the intentional TEST_TRACEABILITY structured artifact.
  PROCEED                 everything else.
planning_allowed is True for PROCEED and PROCEED_WITH_WARNINGS, and False for BLOCKED.
The overall decision is the worst output decision: BLOCKED > PROCEED_WITH_WARNINGS > PROCEED.

TEST_TRACEABILITY is intentionally a STRUCTURED_ARTIFACT. It is not an executable
test, so its SPECIFICATION_ONLY feasibility does not add a false executable-framework warning.
"""

from collections import defaultdict

from app.modules.agents.testing_validation.context_testability.feasibility.schemas import (
    FeasibilityFindingSeverity,
    FeasibilityStatus,
    RepresentationRecommendation,
)
from app.modules.agents.testing_validation.context_testability.testability.schemas import (
    TestabilityFindingSeverity,
    TestabilityStatus,
)
from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    deterministic_id,
    fingerprint,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode

from .constants import (
    CONTEXT_DECISION_POLICY_VERSION,
    ConsolidatedFindingOrigin,
    ConsolidatedFindingSeverity,
    ContextDecisionStatus,
)
from .schemas import (
    ConsolidatedContextFinding,
    ConsolidatedOriginReference,
    DownstreamPlanningProfile,
    OutputContextDecisionProfile,
)


class ContextDecisionInputError(ValueError):
    """Persisted TB1 and FB1 contradict each other. The input is not trusted."""
    pass


def _assessment_ref(prefix, assessment):
    """Deterministic reference to one TB1 or FB1 output assessment."""
    return deterministic_id(prefix, assessment.model_dump(mode="json"))


def _decision(output, testability, feasibility):
    """
    Map one output's TB1 and FB1 assessments to a ContextDecisionStatus.
    TB1 is authoritative for blocking. FB1 can add warnings but cannot unblock.
    """
    if feasibility.n4_2_status is not testability.status:
        raise ContextDecisionInputError("FB1 testability status does not match TB1")
    if testability.status is TestabilityStatus.NOT_READY:
        if feasibility.feasibility is not FeasibilityStatus.NOT_READY:
            raise ContextDecisionInputError("feasibility cannot override a testability block")
        return ContextDecisionStatus.BLOCKED
    if feasibility.feasibility is FeasibilityStatus.NOT_READY:
        raise ContextDecisionInputError("FB1 NOT_READY requires TB1 NOT_READY")
    if testability.status is TestabilityStatus.READY_WITH_WARNINGS:
        return ContextDecisionStatus.PROCEED_WITH_WARNINGS
    intentional_structured = (
        output is TestGenerationOutputCode.TEST_TRACEABILITY
        and feasibility.feasibility is FeasibilityStatus.SPECIFICATION_ONLY
        and feasibility.recommended_representation
        is RepresentationRecommendation.STRUCTURED_ARTIFACT
    )
    if feasibility.feasibility is FeasibilityStatus.SPECIFICATION_ONLY and not intentional_structured:
        return ContextDecisionStatus.PROCEED_WITH_WARNINGS
    return ContextDecisionStatus.PROCEED


def _finding_parts(testability_findings, feasibility_findings):
    """
    Flatten TB1 and FB1 findings into one common shape.
    TB1 BLOCKING findings stay blocking. FB1 findings are always WARNING.
    """
    parts = []
    for item in testability_findings:
        parts.append({
            "output": item.output_code,
            "severity": ConsolidatedFindingSeverity.BLOCKING
            if item.severity is TestabilityFindingSeverity.BLOCKING
            else ConsolidatedFindingSeverity.WARNING,
            "category": item.category,
            "reason": item.reason_code,
            "message": item.message,
            "origin": ConsolidatedFindingOrigin.TESTABILITY,
            "origin_id": item.finding_id,
            "nodes": item.related_node_ids,
            "links": item.related_link_ids,
            "facts": item.semantic_fact_ids,
            "sources": [],
            "chunks": [],
        })
    for item in feasibility_findings:
        # FB1 mirrors TB1 NOT_READY so that feasibility cannot accidentally
        # upgrade it. TB1 remains the authoritative consolidated blocker.
        if item.reason_code == "SEMANTIC_TESTABILITY_NOT_READY":
            continue
        parts.append({
            "output": item.output_code,
            "severity": ConsolidatedFindingSeverity.WARNING,
            "category": item.reason_code,
            "reason": item.reason_code,
            "message": item.message,
            "origin": ConsolidatedFindingOrigin.FEASIBILITY,
            "origin_id": item.finding_id,
            "nodes": item.related_node_ids,
            "links": item.related_link_ids,
            "facts": item.semantic_fact_ids,
            "sources": item.source_ids,
            "chunks": item.chunk_ids,
        })
    return parts


def consolidate_findings(testability_findings, feasibility_findings):
    """
    Merge identical findings (same output, severity, category, reason, and message)
    into one consolidated finding. Its origin_references keep every TB1/FB1 finding it came from.
    """
    groups = defaultdict(list)
    for part in _finding_parts(testability_findings, feasibility_findings):
        # Only identical output/severity/category/reason/message issues group.
        key = (
            part["output"].value, part["severity"].value,
            part["category"], part["reason"], part["message"],
        )
        groups[key].append(part)
    findings = []
    for key, parts in groups.items():
        output_value, severity_value, category, reason, message = key
        origins = sorted(
            {
                (part["origin"], part["origin_id"])
                for part in parts
            },
            key=lambda value: (value[0].value, value[1]),
        )
        identity = {
            "policy": CONTEXT_DECISION_POLICY_VERSION,
            "output": output_value,
            "severity": severity_value,
            "category": category,
            "reason": reason,
            "origins": [(origin.value, finding_id) for origin, finding_id in origins],
        }
        findings.append(ConsolidatedContextFinding(
            consolidated_finding_id=deterministic_id("A4CTXF", identity),
            output_code=TestGenerationOutputCode(output_value),
            severity=ConsolidatedFindingSeverity(severity_value),
            category=category,
            reason_code=reason,
            display_message=message,
            origin_references=[
                ConsolidatedOriginReference(origin=origin, origin_finding_id=finding_id)
                for origin, finding_id in origins
            ],
            evidence_node_ids=sorted({value for part in parts for value in part["nodes"]}),
            evidence_link_ids=sorted({value for part in parts for value in part["links"]}),
            semantic_fact_ids=sorted({value for part in parts for value in part["facts"]}),
            source_ids=sorted({value for part in parts for value in part["sources"]}),
            chunk_ids=sorted({value for part in parts for value in part["chunks"]}),
        ))
    return sorted(findings, key=lambda item: item.consolidated_finding_id)


def consolidate_context_decision(selected_outputs, testability_result, feasibility_result):
    """
    Produce the per-output profiles, planning profiles, consolidated findings,
    and overall decision. Returns (profiles, planning_profiles, findings, overall).
    Every selected output must have exactly one TB1 and one FB1 assessment.
    """
    tb_by_output = {item.output_code: item for item in testability_result.output_assessments}
    fb_by_output = {item.output_code: item for item in feasibility_result.output_assessments}
    if set(tb_by_output) != set(selected_outputs) or set(fb_by_output) != set(selected_outputs):
        raise ContextDecisionInputError("every selected output requires one TB1 and FB1 assessment")
    findings = consolidate_findings(testability_result.findings, feasibility_result.findings)
    finding_by_output = defaultdict(list)
    for item in findings:
        finding_by_output[item.output_code].append(item)

    profiles, planning_profiles = [], []
    for output in selected_outputs:
        testability = tb_by_output[output]
        feasibility = fb_by_output[output]
        decision = _decision(output, testability, feasibility)
        output_findings = finding_by_output[output]
        blocking = sorted(
            item.consolidated_finding_id for item in output_findings
            if item.severity is ConsolidatedFindingSeverity.BLOCKING
        )
        warnings = sorted(
            item.consolidated_finding_id for item in output_findings
            if item.severity is ConsolidatedFindingSeverity.WARNING
        )
        nodes = sorted(set(testability.evidence_node_ids + feasibility.evidence_node_ids))
        links = sorted(set(testability.evidence_link_ids + feasibility.evidence_link_ids))
        facts = sorted(set(testability.semantic_fact_ids + feasibility.semantic_fact_ids))
        reason_codes = sorted(set(testability.reason_codes + feasibility.reason_codes))
        planning_allowed = decision is not ContextDecisionStatus.BLOCKED
        tb_ref = _assessment_ref("A4TBA", testability)
        fb_ref = _assessment_ref("A4FBA", feasibility)
        profile_identity = {
            "policy": CONTEXT_DECISION_POLICY_VERSION,
            "output": output.value,
            "decision": decision.value,
            "testability_assessment": tb_ref,
            "feasibility_assessment": fb_ref,
            "findings": blocking + warnings,
        }
        generation_fp = (
            fingerprint(feasibility.generation_profile.model_dump(mode="json"))
            if feasibility.generation_profile is not None else None
        )
        profile = OutputContextDecisionProfile(
            profile_id=deterministic_id("A4CTXP", profile_identity),
            output_code=output,
            decision=decision,
            planning_allowed=planning_allowed,
            testability_status=testability.status,
            feasibility_status=feasibility.feasibility,
            recommended_representation=feasibility.recommended_representation,
            testability_assessment_ref=tb_ref,
            feasibility_assessment_ref=fb_ref,
            generation_profile_fingerprint=generation_fp,
            execution_status=feasibility.execution_status,
            blocking_finding_ids=blocking,
            warning_finding_ids=warnings,
            evidence_node_ids=nodes,
            evidence_link_ids=links,
            semantic_fact_ids=facts,
            reason_codes=reason_codes,
        )
        profiles.append(profile)
        planning_profiles.append(DownstreamPlanningProfile(
            output_code=output,
            planning_allowed=planning_allowed,
            recommended_representation=feasibility.recommended_representation,
            executable_code_possible=(
                feasibility.feasibility is FeasibilityStatus.EXECUTABLE_POSSIBLE
            ),
            evidence_node_ids=nodes,
            evidence_link_ids=links,
            semantic_fact_ids=facts,
            blocking_finding_ids=blocking,
            warning_finding_ids=warnings,
        ))
    decisions = {item.decision for item in profiles}
    overall = (
        ContextDecisionStatus.BLOCKED if ContextDecisionStatus.BLOCKED in decisions
        else ContextDecisionStatus.PROCEED_WITH_WARNINGS
        if ContextDecisionStatus.PROCEED_WITH_WARNINGS in decisions
        else ContextDecisionStatus.PROCEED
    )
    return profiles, planning_profiles, findings, overall
