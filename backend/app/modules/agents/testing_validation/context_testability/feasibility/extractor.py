"""
N4.3 technical evidence extractor (FB1 input). Pure logic, no I/O.

Scope: TARGET-SYSTEM evidence only. Every value comes from the TR1 graph, which
is built from confirmed N1 source content. The AgileFlow host stack is never
read here. This module does not probe the host, scan the filesystem, or run
any command.

Each category collects explicit text evidence (regex patterns in catalog.py),
plus structured facts from the graph (API operations, UI flow steps, entities,
architecture nodes). Nothing is inferred from defaults or from the host
environment. Missing evidence is recorded as an empty category, not guessed.
"""

import re
from dataclasses import dataclass, field

from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    fingerprint,
)
from app.modules.agents.testing_validation.context_testability.traceability.schemas import (
    TraceabilityNodeKind as N,
    TraceabilityRelationType as R,
    UnresolvedReferenceType,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticFactType as F,
)

from .catalog import (
    NEGATED_TECHNOLOGY_PATTERN,
    TECHNICAL_CONTEXT_PATTERN,
    TECHNOLOGY_PATTERNS,
)
from .constants import TECHNICAL_EVIDENCE_ORDER, TechnicalEvidenceCategory as C
from .schemas import TechnicalEvidenceItem


@dataclass
class _Evidence:
    values: set[str] = field(default_factory=set)
    nodes: set[str] = field(default_factory=set)
    links: set[str] = field(default_factory=set)
    facts: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    chunks: set[str] = field(default_factory=set)

    def node(self, value, item):
        self.values.add(value)
        self.nodes.add(item.node_id)
        self.sources.add(item.source_id)
        if item.chunk_id:
            self.chunks.add(item.chunk_id)
        if item.semantic_fact_id:
            self.facts.add(item.semantic_fact_id)

    def link(self, value, item, nodes):
        self.values.add(value)
        self.links.add(item.traceability_link_id)
        for node_id in (item.source_node_id, item.target_node_id):
            node = nodes[node_id]
            self.nodes.add(node.node_id)
            self.sources.add(node.source_id)
            if node.chunk_id:
                self.chunks.add(node.chunk_id)
            if node.semantic_fact_id:
                self.facts.add(node.semantic_fact_id)


@dataclass(frozen=True)
class TechnicalEvidenceInventory:
    items: tuple[TechnicalEvidenceItem, ...]
    fingerprint: str

    def item(self, category):
        return self.items[TECHNICAL_EVIDENCE_ORDER.index(category)]

    def values(self, category):
        return self.item(category).values

    def present(self, category):
        return bool(self.item(category).values)


def _technical_match(line, match, requires_context):
    """
    Precision guard for technology mentions. A match is rejected when it is
    negated ("no pytest", "not Java") within 32 characters before it. A pattern
    that needs context is kept only if the line also has a technical context word,
    so a plain English use of a common word does not count as a stack declaration.
    """
    prefix = line[max(0, match.start() - 32):match.start()]
    if re.search(NEGATED_TECHNOLOGY_PATTERN, prefix, re.I):
        return False
    return not requires_context or re.search(TECHNICAL_CONTEXT_PATTERN, line, re.I) is not None


def _add_regex_evidence(accumulator, node):
    """
    Scan one TR1 node's display text, line by line, for explicit technical
    declarations. Each match records a value and the node it came from, so the
    evidence stays traceable. Example: "the backend uses FastAPI" records FASTAPI.
    """
    for line in node.display_value.splitlines():
        for category, patterns in TECHNOLOGY_PATTERNS.items():
            for entry in patterns:
                match = re.search(entry.pattern, line, re.I)
                if match and _technical_match(line, match, entry.requires_technical_context):
                    accumulator[category].node(entry.value, node)

        for match in re.finditer(
            r"\b(python|java|node(?:\.js)?)\s+(?:runtime\s+)?(?:version\s+)?v?(\d+(?:\.\d+){0,2})\b",
            line, re.I,
        ):
            if _technical_match(line, match, True):
                name = "NODE" if match.group(1).casefold().startswith("node") else match.group(1).upper()
                accumulator[C.RUNTIME_VERSION].node(f"{name}:{match.group(2)}", node)

        for match in re.finditer(
            r"\b(?:base[_ ]url|service[_ ]url|api[_ ]base)\s*[:=]\s*(https?://[^\s,;]+|\$\{?[A-Z][A-Z0-9_]*\}?)",
            line, re.I,
        ):
            accumulator[C.API_BASE_CONTEXT].node("CONFIGURABLE_BASE_URL", node)

        auth_patterns = (
            ("OAUTH2", r"\boauth\s*2\b"),
            ("BEARER_TOKEN", r"\bbearer\s+(?:token|authentication|authorization)\b|\bauthorization\s*:\s*bearer\b"),
            ("API_KEY", r"\bapi[ _-]?key\b"),
            ("BASIC_AUTH", r"\bbasic\s+auth(?:entication)?\b"),
            ("SESSION_COOKIE", r"\bsession\s+cookie\b"),
        )
        for value, pattern in auth_patterns:
            match = re.search(pattern, line, re.I)
            if match and _technical_match(line, match, False):
                accumulator[C.AUTHENTICATION_SETUP].node(value, node)

        if re.search(r"\b(?:def|function|func)\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|\b(?:public|private|protected)\s+[A-Za-z0-9_<>,?\[\]]+\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", line):
            accumulator[C.FUNCTION_SIGNATURE].node("EXPLICIT_FUNCTION_SIGNATURE", node)
            accumulator[C.MODULE_COMPONENT_BOUNDARY].node("FUNCTION_BOUNDARY", node)
        if re.search(r"\b(?:interface|service interface|client interface|repository interface)\s+[A-Za-z_][A-Za-z0-9_]*", line, re.I):
            accumulator[C.SERVICE_INTERFACE].node("EXPLICIT_SERVICE_INTERFACE", node)
        if re.search(r"\b(?:mock|stub|fake)\s+(?:the\s+)?(?:service|client|repository|interface|dependency)\b", line, re.I):
            accumulator[C.MOCKABLE_BOUNDARY].node("EXPLICIT_MOCK_BOUNDARY", node)
        if re.search(r"\b(?:route|path)\s*[:=]\s*['\"]?/[^\s'\",;]+|\bpath\s*=\s*['\"]/[^'\"]+", line, re.I):
            accumulator[C.UI_ROUTE].node("EXPLICIT_UI_ROUTE", node)
        if re.search(r"\b(?:selector|data-testid|aria-label)\s*[:=]", line, re.I):
            accumulator[C.UI_ELEMENT_OR_SELECTOR].node("EXPLICIT_UI_SELECTOR", node)
        if re.search(r"(?:^|[\\/])(?:tests?|__tests__)(?:[\\/]|$)|\bsrc[\\/]test\b", line, re.I):
            accumulator[C.TEST_DIRECTORY_CONVENTION].node("EXPLICIT_TEST_DIRECTORY", node)
        if re.search(r"\bproject\s+structure\s*:", line, re.I):
            accumulator[C.PROJECT_STRUCTURE].node("EXPLICIT_PROJECT_STRUCTURE", node)


def build_technical_evidence_inventory(graph):
    """
    Build the N4.3 technical evidence inventory from the TR1 graph.
    Returns an inventory with a fingerprint over all categories, which FB1 stores
    so that a changed technical context invalidates the cached feasibility result.
    """
    evidence = {category: _Evidence() for category in TECHNICAL_EVIDENCE_ORDER}
    nodes = {item.node_id: item for item in graph.nodes}
    for node in graph.nodes:
        _add_regex_evidence(evidence, node)
        if node.api_method and node.api_path:
            evidence[C.API_OPERATION].node(f"{node.api_method} {node.api_path}", node)
        if node.node_kind in {N.ARCHITECTURE_COMPONENT, N.FEATURE}:
            evidence[C.MODULE_COMPONENT_BOUNDARY].node(node.node_kind.value, node)
        if node.node_kind is N.UI_FLOW_STEP or node.semantic_fact_type is F.UI_INTERACTION:
            evidence[C.UI_WORKFLOW].node("TRUSTED_UI_WORKFLOW", node)
        if node.node_kind is N.DATA_ENTITY:
            evidence[C.DATA_ENTITY].node(node.entity_name or node.canonical_value, node)
        if node.semantic_fact_type is F.AUTHENTICATION_REQUIREMENT:
            evidence[C.AUTHENTICATION_REQUIRED].node("AUTHENTICATION_REQUIRED", node)
            evidence[C.SECURITY_TARGET].node("AUTHENTICATION", node)
        if node.semantic_fact_type is F.AUTHORIZATION_RULE:
            evidence[C.SECURITY_TARGET].node("AUTHORIZATION", node)
        if node.semantic_fact_type is F.SECURITY_CONTROL:
            evidence[C.SECURITY_TARGET].node("SECURITY_CONTROL", node)

    for link in graph.links:
        if link.relation_type in {R.USES_ENDPOINT, R.USES_ENTITY, R.USES_FIELD}:
            evidence[C.INTEGRATION_BOUNDARY].link(link.relation_type.value, link, nodes)
        if link.relation_type in {R.USES_ENTITY, R.USES_FIELD}:
            evidence[C.DATA_INTERFACE].link(link.relation_type.value, link, nodes)
        if link.relation_type is R.USES_ENDPOINT:
            evidence[C.SERVICE_INTERFACE].link("API_SERVICE_INTERFACE", link, nodes)

    for unresolved in graph.unresolved_references:
        if unresolved.reference_type is UnresolvedReferenceType.IMAGE_PENDING_ANALYSIS:
            evidence[C.PENDING_IMAGE_TECHNICAL_CONTEXT].node(
                nodes[unresolved.source_node_id].artifact_type.value,
                nodes[unresolved.source_node_id],
            )

    manifest_ecosystems = {
        "PACKAGE_JSON": "NPM", "POM_XML": "MAVEN",
        "BUILD_GRADLE": "GRADLE", "REQUIREMENTS_TXT": "PIP",
        "PYPROJECT_TOML": "PYTHON_PACKAGE",
    }
    # A named manifest file (for example package.json) implies its package ecosystem
    # only when the manifest itself is in the trusted text. The ecosystem is not
    # invented from the file name alone.
    manifest_item = evidence[C.DEPENDENCY_MANIFEST_TYPE]
    for manifest, ecosystem in manifest_ecosystems.items():
        if manifest not in manifest_item.values:
            continue
        target = evidence[C.PACKAGE_ECOSYSTEM]
        target.values.add(ecosystem)
        target.nodes.update(manifest_item.nodes)
        target.sources.update(manifest_item.sources)
        target.chunks.update(manifest_item.chunks)

    items = tuple(
        TechnicalEvidenceItem(
            category=category, values=sorted(item.values),
            node_ids=sorted(item.nodes), link_ids=sorted(item.links),
            semantic_fact_ids=sorted(item.facts), source_ids=sorted(item.sources),
            chunk_ids=sorted(item.chunks),
        )
        for category, item in evidence.items()
    )
    return TechnicalEvidenceInventory(
        items=items,
        fingerprint=fingerprint([item.model_dump(mode="json") for item in items]),
    )
