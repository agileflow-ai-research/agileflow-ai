"""
Versioned N4.3 feasibility policy (FP1).

Each output names the automation surface it needs to be EXECUTABLE_POSSIBLE.
TEST_TRACEABILITY is marked structured_artifact_only: it is a traceability
document, not executable code, so its feasibility is always SPECIFICATION_ONLY.
"""

from dataclasses import dataclass
from types import MappingProxyType

from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode as O


@dataclass(frozen=True, slots=True)
class FeasibilityPolicy:
    """Per-output feasibility requirements: the executable surface and structured-artifact flag."""

    output_code: O
    description: str
    executable_surface: str
    structured_artifact_only: bool = False


_CATALOG = (
    FeasibilityPolicy(O.UNIT_TEST_CASES, "Executable unit tests require a compatible explicit toolchain and localized boundary.", "UNIT"),
    FeasibilityPolicy(O.API_TEST_CASES, "Executable API tests require an operation and compatible explicit API-test toolchain.", "API"),
    FeasibilityPolicy(O.INTEGRATION_TEST_CASES, "Executable integration tests require interface detail and compatible explicit toolchain.", "INTEGRATION"),
    FeasibilityPolicy(O.FUNCTIONAL_TEST_CASES, "Executable functional tests require an explicit API, UI, or service automation surface.", "FUNCTIONAL"),
    FeasibilityPolicy(O.E2E_TEST_CASES, "Executable end-to-end tests require a concrete workflow surface and explicit automation framework.", "E2E"),
    FeasibilityPolicy(O.REGRESSION_TEST_CASES, "Executable regression tests reuse a concrete executable test surface.", "REGRESSION"),
    FeasibilityPolicy(O.SECURITY_TEST_CASES, "Executable security checks require an explicit supported toolchain and concrete target surface.", "SECURITY"),
    FeasibilityPolicy(O.ACCEPTANCE_TEST_CASES, "Executable acceptance tests require an explicit automation surface and framework.", "ACCEPTANCE"),
    FeasibilityPolicy(O.TEST_TRACEABILITY, "Test traceability is a structured non-executable artifact.", "STRUCTURED", True),
)

FEASIBILITY_POLICIES = _CATALOG
FEASIBILITY_POLICY_BY_OUTPUT = MappingProxyType({item.output_code: item for item in _CATALOG})

if tuple(item.output_code for item in _CATALOG) != tuple(O):
    raise RuntimeError("Feasibility policies must follow canonical output order")
