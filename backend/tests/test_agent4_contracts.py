import pytest
from pydantic import ValidationError

from app.common.status import AgentRunMode
from app.modules.agents.testing_validation.contracts import enums as contract_enums
from app.modules.agents.testing_validation.contracts import schemas as contract_schemas
from app.modules.agents.testing_validation import schemas as legacy_schemas

MODE_A_CODES = [
    "UNIT_TEST_CASES", "API_TEST_CASES", "INTEGRATION_TEST_CASES",
    "FUNCTIONAL_TEST_CASES", "E2E_TEST_CASES", "REGRESSION_TEST_CASES",
    "SECURITY_TEST_CASES", "ACCEPTANCE_TEST_CASES", "TEST_TRACEABILITY",
]
MODE_B_CODES = [
    "TEST_EXECUTION_REPORT", "COVERAGE_REPORT", "BUG_REPORTS", "SECURITY_FINDINGS",
    "CODE_QUALITY_REPORT", "ACCEPTANCE_CRITERIA_VALIDATION", "FINAL_VALIDATION_REPORT",
]


def test_mode_a_output_vocabulary_is_exactly_the_nine_frozen_codes():
    assert [code.value for code in contract_enums.TestGenerationOutputCode] == MODE_A_CODES


def test_mode_b_output_vocabulary_is_exactly_the_frozen_codes():
    assert [code.value for code in contract_enums.ValidationOutputCode] == MODE_B_CODES


def test_mode_output_vocabularies_never_overlap():
    assert not set(MODE_A_CODES) & set(MODE_B_CODES)


def test_default_run_mode_is_rejected_for_agent_4():
    from app.modules.agents.testing_validation.schemas import Agent4RunRequest

    with pytest.raises(ValidationError):
        Agent4RunRequest(run_mode=AgentRunMode.DEFAULT, selected_outputs=["UNIT_TEST_CASES"])


def test_legacy_schema_imports_resolve_to_contract_objects():
    assert legacy_schemas.TestGenerationOutputCode is contract_enums.TestGenerationOutputCode
    assert legacy_schemas.ValidationOutputCode is contract_enums.ValidationOutputCode
    assert legacy_schemas.GeneratedTestCase is contract_schemas.GeneratedTestCase
    assert legacy_schemas.TEST_OUTPUT_MODELS is contract_schemas.TEST_OUTPUT_MODELS


def test_generated_tests_default_to_not_executed_and_specification_cannot_claim_code():
    specification = contract_schemas.GeneratedTestCase(
        id="TEST-001", title="Duplicate email", purpose="Reject duplicates",
        preconditions=[], test_data=["existing@example.com"], steps=["Register"],
        expected_result="Registration fails", source_refs=["SRC-001"],
        representation="SPECIFICATION", executable=False, framework=None, code=None,
    )
    assert specification.execution_status == "NOT_EXECUTED"

    with pytest.raises(ValidationError):
        contract_schemas.GeneratedTestCase(
            id="TEST-002", title="Fake", purpose="Claims code without any",
            preconditions=[], test_data=[], steps=["Run"], expected_result="Pass",
            source_refs=["SRC-001"], representation="SPECIFICATION", executable=False,
            framework="pytest", code="def test_x(): pass",
        )


def test_agent_4_router_keeps_its_prefix_and_run_endpoint():
    from app.modules.agents.testing_validation.router import router

    assert router.prefix == "/agents/testing-validation"
    assert any(getattr(route, "path", None) == "/agents/testing-validation/{agent_project_id}/run" for route in router.routes)
