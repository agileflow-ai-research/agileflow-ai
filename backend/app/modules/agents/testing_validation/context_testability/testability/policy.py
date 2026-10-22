from dataclasses import dataclass
from types import MappingProxyType

from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode as O

from .constants import EvidenceCategory as E


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    requirement_id: str
    categories: tuple[E, ...]
    description: str


@dataclass(frozen=True, slots=True)
class OutputTestabilityPolicy:
    output_code: O
    description: str
    mandatory: tuple[EvidenceRequirement, ...]
    supporting: tuple[EvidenceRequirement, ...]


def _any(requirement_id, description, *categories):
    return EvidenceRequirement(requirement_id, tuple(categories), description)


_CATALOG = (
    OutputTestabilityPolicy(
        O.UNIT_TEST_CASES,
        "Plan isolated checks from localized behavior or constraints.",
        (_any("UNIT_LOCALIZED_BEHAVIOR", "localized behavior or constraint", E.FUNCTIONAL_BEHAVIOR_EVIDENCE, E.INPUT_VALIDATION_EVIDENCE, E.BOUNDARY_EVIDENCE, E.DATA_INTEGRITY_EVIDENCE, E.STATE_PERSISTENCE_EVIDENCE),),
        (_any("UNIT_BOUNDARY_CONTEXT", "component, feature, operation, or data boundary", E.ARCHITECTURE_COMPONENT_EVIDENCE, E.FEATURE_BOUNDARY_EVIDENCE, E.API_ENDPOINT_EVIDENCE, E.DATA_ENTITY_EVIDENCE, E.DATA_FIELD_EVIDENCE),),
    ),
    OutputTestabilityPolicy(
        O.API_TEST_CASES,
        "Plan API checks from a grounded operation contract.",
        (_any("API_USABLE_OPERATION", "API operation with method and path", E.API_ENDPOINT_EVIDENCE),),
        (_any("API_OPERATION_DETAILS", "validation, error, or access-control detail", E.INPUT_VALIDATION_EVIDENCE, E.ERROR_HANDLING_EVIDENCE, E.AUTHENTICATION_EVIDENCE, E.AUTHORIZATION_EVIDENCE),),
    ),
    OutputTestabilityPolicy(
        O.INTEGRATION_TEST_CASES,
        "Plan interaction checks from an explicit trusted system boundary.",
        (_any("INTEGRATION_INTERACTION", "explicit integration interaction", E.INTEGRATION_BOUNDARY_EVIDENCE),),
        (
            _any("INTEGRATION_STRUCTURE", "contract, component, or data detail", E.API_CONTRACT_EVIDENCE, E.ARCHITECTURE_COMPONENT_EVIDENCE, E.DATA_ENTITY_EVIDENCE),
            _any("INTEGRATION_BEHAVIOR", "persistence, error, or recovery behavior", E.STATE_PERSISTENCE_EVIDENCE, E.ERROR_HANDLING_EVIDENCE, E.RELIABILITY_EVIDENCE),
        ),
    ),
    OutputTestabilityPolicy(
        O.FUNCTIONAL_TEST_CASES,
        "Plan observable behavior checks from functional or satisfaction evidence.",
        (_any("FUNCTIONAL_BEHAVIOR_BASELINE", "functional behavior baseline", E.FUNCTIONAL_REQUIREMENT_EVIDENCE, E.FUNCTIONAL_BEHAVIOR_EVIDENCE, E.USER_STORY_EVIDENCE, E.ACCEPTANCE_EVIDENCE),),
        (_any("FUNCTIONAL_SUPPORT", "acceptance, validation, state, error, or traceability detail", E.ACCEPTANCE_EVIDENCE, E.INPUT_VALIDATION_EVIDENCE, E.BOUNDARY_EVIDENCE, E.STATE_PERSISTENCE_EVIDENCE, E.ERROR_HANDLING_EVIDENCE, E.TRACEABILITY_LINK_EVIDENCE),),
    ),
    OutputTestabilityPolicy(
        O.E2E_TEST_CASES,
        "Plan end-to-end checks from a grounded business or UI workflow.",
        (_any("E2E_WORKFLOW", "end-to-end business or UI workflow", E.UI_WORKFLOW_EVIDENCE, E.BUSINESS_WORKFLOW_EVIDENCE),),
        (_any("E2E_TECHNICAL_PATH", "API, persistence, authentication, or acceptance path detail", E.API_ENDPOINT_EVIDENCE, E.STATE_PERSISTENCE_EVIDENCE, E.AUTHENTICATION_EVIDENCE, E.ACCEPTANCE_EVIDENCE),),
    ),
    OutputTestabilityPolicy(
        O.REGRESSION_TEST_CASES,
        "Plan regression coverage from a stable current behavior baseline.",
        (_any("REGRESSION_BASELINE", "stable behavioral baseline", E.FUNCTIONAL_REQUIREMENT_EVIDENCE, E.USER_STORY_EVIDENCE, E.ACCEPTANCE_EVIDENCE, E.FUNCTIONAL_BEHAVIOR_EVIDENCE),),
        (_any("REGRESSION_CHANGE_CONTEXT", "connected traceability or risk context", E.TRACEABILITY_LINK_EVIDENCE, E.NON_FUNCTIONAL_REQUIREMENT_EVIDENCE),),
    ),
    OutputTestabilityPolicy(
        O.SECURITY_TEST_CASES,
        "Plan security checks only from explicit project security evidence.",
        (_any("SECURITY_CONCERN", "grounded authentication, authorization, or security control", E.AUTHENTICATION_EVIDENCE, E.AUTHORIZATION_EVIDENCE, E.SECURITY_CONTROL_EVIDENCE),),
        (_any("SECURITY_SUPPORT", "contract, error, acceptance, or non-functional context", E.API_CONTRACT_EVIDENCE, E.ERROR_HANDLING_EVIDENCE, E.ACCEPTANCE_EVIDENCE, E.NON_FUNCTIONAL_REQUIREMENT_EVIDENCE),),
    ),
    OutputTestabilityPolicy(
        O.ACCEPTANCE_TEST_CASES,
        "Plan acceptance checks from explicit satisfaction conditions.",
        (_any("ACCEPTANCE_CONDITION", "explicit acceptance condition", E.ACCEPTANCE_EVIDENCE),),
        (_any("ACCEPTANCE_SUPPORT", "story, requirement, workflow, or API context", E.USER_STORY_EVIDENCE, E.FUNCTIONAL_REQUIREMENT_EVIDENCE, E.UI_WORKFLOW_EVIDENCE, E.BUSINESS_WORKFLOW_EVIDENCE, E.API_ENDPOINT_EVIDENCE),),
    ),
    OutputTestabilityPolicy(
        O.TEST_TRACEABILITY,
        "Plan traceability from stable requirement identities and the valid TR1 graph.",
        (_any("TRACEABILITY_ANCHOR", "stable requirement, story, or acceptance identity", E.TRACEABLE_REQUIREMENT_IDENTITY),),
        (_any("TRACEABILITY_RELATIONSHIP", "resolved traceability relationship", E.TRACEABILITY_LINK_EVIDENCE),),
    ),
)

OUTPUT_TESTABILITY_POLICIES = _CATALOG
OUTPUT_POLICY_BY_CODE = MappingProxyType({item.output_code: item for item in _CATALOG})

if tuple(item.output_code for item in _CATALOG) != tuple(O):
    raise RuntimeError("Output testability policies must follow canonical output order")
