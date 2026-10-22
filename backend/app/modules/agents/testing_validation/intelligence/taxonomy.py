"""Canonical Agent 4 testing-intelligence taxonomy.

This module is deliberately policy-only. Rules, model thresholds, and hybrid
decision logic are versioned by the later stages that implement them.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


AGENT4_TESTING_TAXONOMY_VERSION = "T1"
AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION = "ZL1"


class TestingIntelligenceLabel(StrEnum):
    FUNCTIONAL_BEHAVIOR = "FUNCTIONAL_BEHAVIOR"
    INPUT_VALIDATION = "INPUT_VALIDATION"
    BOUNDARY_CONSTRAINT = "BOUNDARY_CONSTRAINT"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    API_CONTRACT = "API_CONTRACT"
    UI_WORKFLOW = "UI_WORKFLOW"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    SECURITY_CONTROL = "SECURITY_CONTROL"
    PERFORMANCE_SLO = "PERFORMANCE_SLO"
    RELIABILITY_RECOVERY = "RELIABILITY_RECOVERY"
    ERROR_HANDLING = "ERROR_HANDLING"
    ACCEPTANCE_CONDITION = "ACCEPTANCE_CONDITION"
    STATE_PERSISTENCE = "STATE_PERSISTENCE"
    NON_TESTABLE_CONTEXT = "NON_TESTABLE_CONTEXT"


TESTING_INTELLIGENCE_LABEL_ORDER = tuple(TestingIntelligenceLabel)


@dataclass(frozen=True, slots=True)
class TestingTaxonomyEntry:
    code: TestingIntelligenceLabel
    definition: str
    model_description: str
    evaluation_definition: str
    exclusion_notes: tuple[str, ...] = ()


_CATALOG = {
    TestingIntelligenceLabel.FUNCTIONAL_BEHAVIOR: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.FUNCTIONAL_BEHAVIOR,
        definition="Observable system or business behavior or capability.",
        model_description=(
            "observable software or business behavior and system capabilities"
        ),
        evaluation_definition=(
            "Use when evidence states an externally observable behavior or "
            "capability, rather than only background or implementation detail."
        ),
    ),
    TestingIntelligenceLabel.INPUT_VALIDATION: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.INPUT_VALIDATION,
        definition="Rules constraining the validity of supplied input.",
        model_description="validation rules for user or system input",
        evaluation_definition=(
            "Use for required formats, presence, admissibility, or other general "
            "input-validity rules. Explicit quantitative limits may also carry "
            "BOUNDARY_CONSTRAINT."
        ),
    ),
    TestingIntelligenceLabel.BOUNDARY_CONSTRAINT: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.BOUNDARY_CONSTRAINT,
        definition="Explicit minimum, maximum, range, length, or threshold constraints.",
        model_description=(
            "minimum, maximum, range, length, or numeric boundary constraints"
        ),
        evaluation_definition=(
            "Use when evidence supplies a testable quantitative or ordinal boundary."
        ),
    ),
    TestingIntelligenceLabel.DATA_INTEGRITY: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.DATA_INTEGRITY,
        definition="Uniqueness, consistency, referential, or data-correctness constraints.",
        model_description=(
            "data uniqueness, consistency, referential integrity, and correctness constraints"
        ),
        evaluation_definition=(
            "Use for evidence that stored or exchanged data must remain correct, "
            "consistent, unique, or referentially valid."
        ),
        exclusion_notes=("Uniqueness is a subtype, not a separate taxonomy label.",),
    ),
    TestingIntelligenceLabel.API_CONTRACT: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.API_CONTRACT,
        definition="Endpoint, request, response, status, or interface-contract information.",
        model_description=(
            "API endpoints, requests, responses, status codes, and interface contracts"
        ),
        evaluation_definition=(
            "Use for externally defined API/interface behavior; it may coexist with "
            "behavioral, validation, error, or security labels."
        ),
    ),
    TestingIntelligenceLabel.UI_WORKFLOW: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.UI_WORKFLOW,
        definition="User-interface navigation, interaction, or screen-flow behavior.",
        model_description=(
            "user-interface interactions, navigation, screens, and user flows"
        ),
        evaluation_definition=(
            "Use when evidence describes observable UI actions, transitions, or flows."
        ),
    ),
    TestingIntelligenceLabel.AUTHENTICATION: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.AUTHENTICATION,
        definition="Identity verification, login, session, or access-token requirements.",
        model_description=(
            "identity verification, login, session, and access-token requirements"
        ),
        evaluation_definition=(
            "Use for proving or maintaining identity, distinct from deciding permissions."
        ),
    ),
    TestingIntelligenceLabel.AUTHORIZATION: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.AUTHORIZATION,
        definition="Permission, role, or ownership-based access restrictions.",
        model_description="access permissions, roles, and ownership-based restrictions",
        evaluation_definition=(
            "Use when an identified actor's permission depends on role, ownership, "
            "scope, or an access-control decision."
        ),
    ),
    TestingIntelligenceLabel.SECURITY_CONTROL: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.SECURITY_CONTROL,
        definition="Security requirements beyond basic authentication or authorization.",
        model_description=(
            "security protections such as encryption, rate limiting, lockout, CSRF, "
            "or security headers"
        ),
        evaluation_definition=(
            "Use for broader protective controls; it may coexist with AUTHENTICATION "
            "or AUTHORIZATION when both concerns are explicit."
        ),
    ),
    TestingIntelligenceLabel.PERFORMANCE_SLO: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.PERFORMANCE_SLO,
        definition="Latency, throughput, capacity, timing, or measurable performance objectives.",
        model_description=(
            "latency, throughput, capacity, timing, and measurable performance objectives"
        ),
        evaluation_definition=(
            "Use for a performance characteristic or service-level objective that can "
            "be evaluated through measurement."
        ),
    ),
    TestingIntelligenceLabel.RELIABILITY_RECOVERY: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.RELIABILITY_RECOVERY,
        definition=(
            "Availability, retry, recovery, resilience, continuity, or failure-tolerance requirements."
        ),
        model_description=(
            "availability, retries, recovery, resilience, continuity, and fault tolerance"
        ),
        evaluation_definition=(
            "Use for sustained operation or restoration across failures, rather than "
            "only the response to one invalid operation."
        ),
    ),
    TestingIntelligenceLabel.ERROR_HANDLING: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.ERROR_HANDLING,
        definition="Required behavior for invalid operations, failures, or error responses.",
        model_description=(
            "required behavior for invalid operations, failures, and error responses"
        ),
        evaluation_definition=(
            "Use for the immediate observable handling or response to an error condition."
        ),
    ),
    TestingIntelligenceLabel.ACCEPTANCE_CONDITION: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.ACCEPTANCE_CONDITION,
        definition="An explicit condition of satisfaction or acceptance for a feature or story.",
        model_description=(
            "explicit acceptance criteria and conditions of satisfaction for a feature"
        ),
        evaluation_definition=(
            "Use when evidence explicitly defines what must be true for stakeholder acceptance."
        ),
    ),
    TestingIntelligenceLabel.STATE_PERSISTENCE: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.STATE_PERSISTENCE,
        definition="Required storage, state-transition, or persistence behavior.",
        model_description=(
            "storage, persisted state, and required state-transition behavior"
        ),
        evaluation_definition=(
            "Use for requirements about retaining, retrieving, or transitioning system state."
        ),
    ),
    TestingIntelligenceLabel.NON_TESTABLE_CONTEXT: TestingTaxonomyEntry(
        code=TestingIntelligenceLabel.NON_TESTABLE_CONTEXT,
        definition=(
            "Contextual or descriptive information without a direct testable concern under taxonomy T1."
        ),
        model_description=(
            "general contextual or descriptive material without a direct testable concern"
        ),
        evaluation_definition=(
            "Use for preserved context that does not directly support another T1 concern. "
            "It is evidence, not an error or failed classification."
        ),
        exclusion_notes=(
            "Normally do not accept this label alongside a strong testable concern; "
            "the N3.4 hybrid policy owns that final decision.",
        ),
    ),
}

TESTING_INTELLIGENCE_TAXONOMY: Mapping[
    TestingIntelligenceLabel, TestingTaxonomyEntry
] = MappingProxyType(_CATALOG)
del _CATALOG


def get_testing_taxonomy_entry(
    label: TestingIntelligenceLabel | str,
) -> TestingTaxonomyEntry:
    """Return one canonical entry, rejecting aliases and unknown values."""

    return TESTING_INTELLIGENCE_TAXONOMY[TestingIntelligenceLabel(label)]

