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
