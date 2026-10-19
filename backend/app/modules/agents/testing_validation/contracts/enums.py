"""Stable Agent 4 vocabularies from docs/standalone/AGENT_4_TESTING_VALIDATION_CONTRACT.md (v1.1).

Mode A (TEST_GENERATION) and Mode B (VALIDATION) output codes are kept in separate
enums and must never be merged. Do not rename these values; they are frozen.
"""

from enum import StrEnum


class TestGenerationOutputCode(StrEnum):
    UNIT_TEST_CASES = "UNIT_TEST_CASES"
    API_TEST_CASES = "API_TEST_CASES"
    INTEGRATION_TEST_CASES = "INTEGRATION_TEST_CASES"
    FUNCTIONAL_TEST_CASES = "FUNCTIONAL_TEST_CASES"
    E2E_TEST_CASES = "E2E_TEST_CASES"
    REGRESSION_TEST_CASES = "REGRESSION_TEST_CASES"
    SECURITY_TEST_CASES = "SECURITY_TEST_CASES"
    ACCEPTANCE_TEST_CASES = "ACCEPTANCE_TEST_CASES"
    TEST_TRACEABILITY = "TEST_TRACEABILITY"


class ValidationOutputCode(StrEnum):
    TEST_EXECUTION_REPORT = "TEST_EXECUTION_REPORT"
    COVERAGE_REPORT = "COVERAGE_REPORT"
    BUG_REPORTS = "BUG_REPORTS"
    SECURITY_FINDINGS = "SECURITY_FINDINGS"
    CODE_QUALITY_REPORT = "CODE_QUALITY_REPORT"
    ACCEPTANCE_CRITERIA_VALIDATION = "ACCEPTANCE_CRITERIA_VALIDATION"
    FINAL_VALIDATION_REPORT = "FINAL_VALIDATION_REPORT"


class TestRepresentation(StrEnum):
    """What a generated test artifact is. Specification and executable code are never conflated."""

    SPECIFICATION = "SPECIFICATION"
    EXECUTABLE_CODE = "EXECUTABLE_CODE"


class TestExecutionStatus(StrEnum):
    """Generated tests are never executed in TEST_GENERATION. Execution belongs to VALIDATION."""

    NOT_EXECUTED = "NOT_EXECUTED"


class Agent4ArtifactType(StrEnum):
    """Upstream artifact identities accepted as TEST_GENERATION inputs (contract v1.1 §2.4–2.5).

    Names are the canonical Agent 1 and Agent 2 output codes. Other agents' aliases
    (for example Agent 3's UI_WIREFRAMES) are never used here.
    """

    # Normally supplied by Agent 1
    FUNCTIONAL_REQUIREMENTS = "FUNCTIONAL_REQUIREMENTS"
    NON_FUNCTIONAL_REQUIREMENTS = "NON_FUNCTIONAL_REQUIREMENTS"
    USER_STORIES = "USER_STORIES"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    PERSONAS = "PERSONAS"
    QUALITY_FINDINGS = "QUALITY_FINDINGS"
    CLARIFICATION_QUESTIONS = "CLARIFICATION_QUESTIONS"
    SRS = "SRS"
    # Normally supplied by Agent 2
    SYSTEM_ARCHITECTURE = "SYSTEM_ARCHITECTURE"
    UML_DIAGRAMS = "UML_DIAGRAMS"
    DATABASE_SCHEMA = "DATABASE_SCHEMA"
    API_SPECIFICATION = "API_SPECIFICATION"
    WIREFRAMES = "WIREFRAMES"
    UI_FLOW = "UI_FLOW"
    FEATURES = "FEATURES"


class Agent4InputSourceType(StrEnum):
    """How an artifact was supplied. Kept separate from the artifact type."""

    TEXT = "TEXT"
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"


class InputOriginAgent(StrEnum):
    """The upstream agent an artifact is normally produced by. Recorded honestly, never as execution."""

    AGENT_1 = "AGENT_1"
    AGENT_2 = "AGENT_2"


class SuppliedVia(StrEnum):
    STANDALONE_MANUAL_INPUT = "STANDALONE_MANUAL_INPUT"


class InputProcessingStatus(StrEnum):
    """Collection state only. Extraction, normalization, and analysis are later steps."""

    COLLECTED = "COLLECTED"
    UPLOADED = "UPLOADED"
    PENDING_ANALYSIS = "PENDING_ANALYSIS"
