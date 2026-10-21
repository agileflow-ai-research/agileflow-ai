from dataclasses import dataclass, field

from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    deterministic_id,
)
from app.modules.agents.testing_validation.context_testability.traceability.schemas import (
    Agent4TraceabilityManifest,
    TraceabilityNodeKind as N,
    TraceabilityRelationType as R,
    UnresolvedReferenceType,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticFactType as F,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode as O

from .constants import OUTPUT_POLICY_VERSION, EvidenceCategory as E
from .policy import OUTPUT_POLICY_BY_CODE, EvidenceRequirement
from .schemas import (
    EvidenceInventoryItem,
    EvidenceRequirementAssessment,
    MissingContextFinding,
    OutputTestabilityAssessment,
    TestabilityFindingSeverity as Severity,
    TestabilityStatus,
)


NODE_CATEGORY = {
    N.FUNCTIONAL_REQUIREMENT: E.FUNCTIONAL_REQUIREMENT_EVIDENCE,
    N.NON_FUNCTIONAL_REQUIREMENT: E.NON_FUNCTIONAL_REQUIREMENT_EVIDENCE,
    N.USER_STORY: E.USER_STORY_EVIDENCE,
    N.ACCEPTANCE_CRITERION: E.ACCEPTANCE_EVIDENCE,
    N.API_ENDPOINT: E.API_ENDPOINT_EVIDENCE,
    N.API_CONTRACT_ITEM: E.API_CONTRACT_EVIDENCE,
    N.DATA_ENTITY: E.DATA_ENTITY_EVIDENCE,
    N.DATA_FIELD: E.DATA_FIELD_EVIDENCE,
    N.UI_FLOW_STEP: E.UI_WORKFLOW_EVIDENCE,
    N.ARCHITECTURE_COMPONENT: E.ARCHITECTURE_COMPONENT_EVIDENCE,
    N.FEATURE: E.FEATURE_BOUNDARY_EVIDENCE,
}
FACT_CATEGORY = {
    F.BEHAVIOR: E.FUNCTIONAL_BEHAVIOR_EVIDENCE,
    F.ACTOR_ACTION: E.FUNCTIONAL_BEHAVIOR_EVIDENCE,
    F.INPUT_CONSTRAINT: E.INPUT_VALIDATION_EVIDENCE,
    F.BOUNDARY_CONSTRAINT: E.BOUNDARY_EVIDENCE,
    F.DATA_INTEGRITY_CONSTRAINT: E.DATA_INTEGRITY_EVIDENCE,
    F.API_CONTRACT: E.API_CONTRACT_EVIDENCE,
    F.UI_INTERACTION: E.UI_WORKFLOW_EVIDENCE,
    F.AUTHENTICATION_REQUIREMENT: E.AUTHENTICATION_EVIDENCE,
    F.AUTHORIZATION_RULE: E.AUTHORIZATION_EVIDENCE,
    F.SECURITY_CONTROL: E.SECURITY_CONTROL_EVIDENCE,
    F.PERFORMANCE_TARGET: E.PERFORMANCE_EVIDENCE,
    F.RELIABILITY_RECOVERY: E.RELIABILITY_EVIDENCE,
    F.ERROR_EXPECTATION: E.ERROR_HANDLING_EVIDENCE,
    F.ACCEPTANCE_CONDITION: E.ACCEPTANCE_EVIDENCE,
    F.STATE_PERSISTENCE: E.STATE_PERSISTENCE_EVIDENCE,
    F.PRECONDITION: E.FUNCTIONAL_BEHAVIOR_EVIDENCE,
    F.POSTCONDITION: E.FUNCTIONAL_BEHAVIOR_EVIDENCE,
    F.EXPECTED_OUTCOME: E.FUNCTIONAL_BEHAVIOR_EVIDENCE,
}
ANCHOR_KINDS = {
    N.FUNCTIONAL_REQUIREMENT, N.NON_FUNCTIONAL_REQUIREMENT,
    N.USER_STORY, N.ACCEPTANCE_CRITERION,
}
INTERACTION_RELATIONS = {R.USES_ENDPOINT, R.USES_ENTITY, R.USES_FIELD}
INTEGRATION_KINDS = {
    N.API_ENDPOINT, N.API_CONTRACT_ITEM, N.ARCHITECTURE_COMPONENT,
    N.DATA_ENTITY, N.DATA_FIELD,
}
IMAGE_RELEVANCE = {
    O.UNIT_TEST_CASES: {"SYSTEM_ARCHITECTURE", "UML_DIAGRAMS", "DATABASE_SCHEMA"},
    O.API_TEST_CASES: {"API_SPECIFICATION"},
    O.INTEGRATION_TEST_CASES: {"SYSTEM_ARCHITECTURE", "UML_DIAGRAMS", "DATABASE_SCHEMA", "API_SPECIFICATION"},
    O.FUNCTIONAL_TEST_CASES: {"UI_FLOW", "WIREFRAMES"},
    O.E2E_TEST_CASES: {"UI_FLOW", "WIREFRAMES"},
    O.REGRESSION_TEST_CASES: set(),
    O.SECURITY_TEST_CASES: {"API_SPECIFICATION", "SYSTEM_ARCHITECTURE"},
    O.ACCEPTANCE_TEST_CASES: {"UI_FLOW", "WIREFRAMES"},
    O.TEST_TRACEABILITY: set(),
}


@dataclass
class _Refs:
    nodes: set[str] = field(default_factory=set)
    links: set[str] = field(default_factory=set)
    facts: set[str] = field(default_factory=set)

    def add_node(self, node):
        self.nodes.add(node.node_id)
        if node.semantic_fact_id:
            self.facts.add(node.semantic_fact_id)

    def add_link(self, link):
        self.links.add(link.traceability_link_id)


@dataclass(frozen=True)
class EvidenceInventory:
    items: tuple[EvidenceInventoryItem, ...]
    unresolved_ids: tuple[str, ...]
    ambiguity_ids: tuple[str, ...]
    pending_images: tuple[tuple[str, str], ...]
    anchor_node_ids: tuple[str, ...]
    unresolved_source_node_ids: tuple[str, ...]

    def item(self, category):
        return self.items[list(E).index(category)]


def build_evidence_inventory(graph: Agent4TraceabilityManifest) -> EvidenceInventory:
    refs = {category: _Refs() for category in E}
    nodes = {item.node_id: item for item in graph.nodes}
    anchors = set()
    pending_images = []

    for node in graph.nodes:
        category = NODE_CATEGORY.get(node.node_kind)
        if category:
            refs[category].add_node(node)
        if node.api_method and node.api_path:
            refs[E.API_ENDPOINT_EVIDENCE].add_node(node)
        if node.node_kind in ANCHOR_KINDS and node.external_reference_id:
            refs[E.TRACEABLE_REQUIREMENT_IDENTITY].add_node(node)
            anchors.add(node.node_id)
        if node.node_kind is N.SEMANTIC_TESTING_FACT and node.semantic_fact_type:
            category = FACT_CATEGORY[node.semantic_fact_type]
            refs[category].add_node(node)

    for link in graph.links:
        refs[E.TRACEABILITY_LINK_EVIDENCE].add_link(link)
        left, right = nodes[link.source_node_id], nodes[link.target_node_id]
        if (
            link.relation_type in INTERACTION_RELATIONS
            or (
                left.source_id != right.source_id
                and ({left.node_kind, right.node_kind} & INTEGRATION_KINDS)
            )
        ):
            refs[E.INTEGRATION_BOUNDARY_EVIDENCE].add_link(link)
        if link.relation_type is R.VALIDATES and {
            left.node_kind, right.node_kind
        } == {N.USER_STORY, N.ACCEPTANCE_CRITERION}:
            refs[E.BUSINESS_WORKFLOW_EVIDENCE].add_link(link)

    for unresolved in graph.unresolved_references:
        if unresolved.reference_type is UnresolvedReferenceType.IMAGE_PENDING_ANALYSIS:
            node = nodes[unresolved.source_node_id]
            refs[E.PENDING_IMAGE_EVIDENCE].add_node(node)
            pending_images.append((node.node_id, node.artifact_type.value))

    items = tuple(
        EvidenceInventoryItem(
            category=category,
            observed_count=len(value.nodes | value.links),
            node_ids=sorted(value.nodes), link_ids=sorted(value.links),
            semantic_fact_ids=sorted(value.facts),
        )
        for category, value in refs.items()
    )
    return EvidenceInventory(
        items=items,
        unresolved_ids=tuple(sorted(item.unresolved_id for item in graph.unresolved_references)),
        ambiguity_ids=tuple(sorted(item.ambiguity_id for item in graph.ambiguities)),
        pending_images=tuple(sorted(pending_images)),
        anchor_node_ids=tuple(sorted(anchors)),
        unresolved_source_node_ids=tuple(sorted({item.source_node_id for item in graph.unresolved_references})),
    )


def _assess_requirement(requirement: EvidenceRequirement, inventory: EvidenceInventory):
    selected = [inventory.item(category) for category in requirement.categories]
    nodes = sorted({value for item in selected for value in item.node_ids})
    links = sorted({value for item in selected for value in item.link_ids})
    facts = sorted({value for item in selected for value in item.semantic_fact_ids})
    return EvidenceRequirementAssessment(
        requirement_id=requirement.requirement_id,
        description=requirement.description,
        required_categories=list(requirement.categories),
        satisfied=any(item.observed_count for item in selected),
        observed_count=len(set(nodes + links)),
        evidence_node_ids=nodes, evidence_link_ids=links,
        semantic_fact_ids=facts,
    )


def _finding(*, output, severity, reason, category, message, requirement=None,
             nodes=(), links=(), graph_findings=(), facts=(), graph_fingerprint=""):
    categories = list(requirement.required_categories) if requirement else []
    observed = requirement.observed_count if requirement else len(set(nodes) | set(links) | set(facts))
    identity = {
        "policy": OUTPUT_POLICY_VERSION, "graph": graph_fingerprint,
        "output": output.value, "severity": severity.value,
        "reason": reason, "categories": [item.value for item in categories],
        "nodes": sorted(nodes), "links": sorted(links),
        "graph_findings": sorted(graph_findings), "facts": sorted(facts),
    }
    return MissingContextFinding(
        finding_id=deterministic_id("A4TBF", identity), output_code=output,
        severity=severity, category=category, reason_code=reason,
        message=message, required_evidence_categories=categories,
        observed_count=observed, related_node_ids=sorted(set(nodes)),
        related_link_ids=sorted(set(links)),
        related_finding_ids=sorted(set(graph_findings)),
        semantic_fact_ids=sorted(set(facts)),
    )


def evaluate_output(output_code, inventory, graph, *, graph_fingerprint):
    policy = OUTPUT_POLICY_BY_CODE[output_code]
    mandatory = [_assess_requirement(item, inventory) for item in policy.mandatory]
    supporting = [_assess_requirement(item, inventory) for item in policy.supporting]
    findings = []
    for item in mandatory:
        if not item.satisfied:
            findings.append(_finding(
                output=output_code, severity=Severity.BLOCKING,
                reason=f"{item.requirement_id}_MISSING", category=item.requirement_id,
                message=f"{item.description.capitalize()} is absent from trusted evidence.",
                requirement=item, graph_findings=inventory.unresolved_ids + inventory.ambiguity_ids,
                graph_fingerprint=graph_fingerprint,
            ))
    for item in supporting:
        if not item.satisfied:
            findings.append(_finding(
                output=output_code, severity=Severity.WARNING,
                reason=f"{item.requirement_id}_MISSING", category=item.requirement_id,
                message=f"Trusted {item.description} is not available, reducing planning detail.",
                requirement=item, graph_fingerprint=graph_fingerprint,
            ))

    relevant_images = [
        node_id for node_id, artifact in inventory.pending_images
        if artifact in IMAGE_RELEVANCE[output_code]
    ]
    if relevant_images:
        findings.append(_finding(
            output=output_code, severity=Severity.WARNING,
            reason="PENDING_IMAGE_CONTEXT", category="PENDING_IMAGE_CONTEXT",
            message="Relevant image evidence remains pending analysis and is not treated as semantic context.",
            nodes=relevant_images, graph_fingerprint=graph_fingerprint,
        ))

    if output_code is O.TEST_TRACEABILITY:
        if inventory.unresolved_ids:
            findings.append(_finding(
                output=output_code, severity=Severity.WARNING,
                reason="UNRESOLVED_TRACEABILITY_REMAINS", category="TRACEABILITY_LIMITATION",
                message="Usable traceability evidence exists, but unresolved references remain.",
                graph_findings=inventory.unresolved_ids, graph_fingerprint=graph_fingerprint,
            ))
        if inventory.ambiguity_ids:
            findings.append(_finding(
                output=output_code, severity=Severity.WARNING,
                reason="AMBIGUOUS_TRACEABILITY_REMAINS", category="TRACEABILITY_LIMITATION",
                message="Usable traceability evidence exists, but ambiguous relationships remain unresolved.",
                graph_findings=inventory.ambiguity_ids, graph_fingerprint=graph_fingerprint,
            ))
        if (
            inventory.anchor_node_ids
            and set(inventory.anchor_node_ids).issubset(inventory.unresolved_source_node_ids)
            and not graph.links
        ):
            findings.append(_finding(
                output=output_code, severity=Severity.BLOCKING,
                reason="ALL_TRACEABILITY_ANCHORS_UNRESOLVED",
                category="TRACEABILITY_ANCHOR",
                message="All meaningful traceability anchors remain unresolved.",
                nodes=inventory.anchor_node_ids,
                graph_findings=inventory.unresolved_ids,
                graph_fingerprint=graph_fingerprint,
            ))

    has_blocking = any(item.severity is Severity.BLOCKING for item in findings)
    has_warning = any(item.severity is Severity.WARNING for item in findings)
    status = (
        TestabilityStatus.NOT_READY if has_blocking
        else TestabilityStatus.READY_WITH_WARNINGS if has_warning
        else TestabilityStatus.READY
    )
    requirement_items = mandatory + supporting
    return OutputTestabilityAssessment(
        output_code=output_code, status=status, policy_version=OUTPUT_POLICY_VERSION,
        mandatory_requirements=mandatory, supporting_requirements=supporting,
        satisfied_requirements=sorted(item.requirement_id for item in requirement_items if item.satisfied),
        missing_requirements=sorted(item.requirement_id for item in requirement_items if not item.satisfied),
        finding_ids=sorted(item.finding_id for item in findings),
        evidence_node_ids=sorted({value for item in requirement_items for value in item.evidence_node_ids}),
        evidence_link_ids=sorted({value for item in requirement_items for value in item.evidence_link_ids}),
        semantic_fact_ids=sorted({value for item in requirement_items for value in item.semantic_fact_ids}),
        reason_codes=sorted({item.reason_code for item in findings}),
    ), findings


def evaluate_testability(selected_outputs, inventory, graph, *, graph_fingerprint):
    assessments, findings = [], []
    for output in selected_outputs:
        assessment, output_findings = evaluate_output(
            output, inventory, graph, graph_fingerprint=graph_fingerprint
        )
        assessments.append(assessment)
        findings.extend(output_findings)
    findings = sorted({item.finding_id: item for item in findings}.values(), key=lambda item: item.finding_id)
    statuses = {item.status for item in assessments}
    overall = (
        TestabilityStatus.NOT_READY if TestabilityStatus.NOT_READY in statuses
        else TestabilityStatus.READY_WITH_WARNINGS
        if TestabilityStatus.READY_WITH_WARNINGS in statuses
        else TestabilityStatus.READY
    )
    return assessments, findings, overall
