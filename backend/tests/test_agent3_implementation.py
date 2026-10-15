import pytest
from pydantic import ValidationError

from app.modules.agents.implementation.schemas import (
    Agent3WorkspaceRequest,
    ImplementationArtifactType,
    ImplementationInput,
    ImplementationInputSourceType,
    ImplementationOutputCode,
)


SOURCE_TYPES = ["TEXT", "DOCUMENT", "IMAGE"]
ARTIFACT_TYPES = [
    "SRS",
    "FUNCTIONAL_REQUIREMENTS",
    "NON_FUNCTIONAL_REQUIREMENTS",
    "USER_STORIES",
    "ACCEPTANCE_CRITERIA",
    "SYSTEM_ARCHITECTURE",
    "UML_DIAGRAMS",
    "DATABASE_SCHEMA",
    "API_SPECIFICATION",
    "UI_WIREFRAMES",
    "UI_FLOW",
    "IMPLEMENTATION_TASKS",
    "PRODUCT_BACKLOG",
    "TECHNICAL_CONSTRAINTS",
    "TECHNOLOGY_STACK",
    "UNIT_TEST_CASES",
    "API_TEST_CASES",
    "INTEGRATION_TEST_CASES",
    "FUNCTIONAL_TEST_CASES",
    "E2E_TEST_CASES",
    "SECURITY_TEST_CASES",
    "ACCEPTANCE_TEST_CASES",
    "TEST_TRACEABILITY",
]
OUTPUT_CODES = [
    "PROJECT_STRUCTURE",
    "FRONTEND_CODE",
    "BACKEND_CODE",
    "DATABASE_IMPLEMENTATION",
    "API_IMPLEMENTATION",
    "CONFIGURATION_FILES",
    "CONTAINER_CONFIGURATION",
    "GIT_SUMMARY",
]


def valid_input(**overrides):
    return {
        "source_type": "TEXT",
        "artifact_type": "FUNCTIONAL_REQUIREMENTS",
        "content": "Customers can create bookings.",
        **overrides,
    }


def test_frozen_enum_values_are_exact():
    assert [item.value for item in ImplementationInputSourceType] == SOURCE_TYPES
    assert [item.value for item in ImplementationArtifactType] == ARTIFACT_TYPES
    assert [item.value for item in ImplementationOutputCode] == OUTPUT_CODES


def test_valid_text_input_is_trimmed_and_accepted():
    item = ImplementationInput(**valid_input(content="  Build a booking API.  ", label="  API scope  "))
    assert item.content == "Build a booking API."
    assert item.label == "API scope"


@pytest.mark.parametrize(
    "payload",
    [
        valid_input(content="   "),
        valid_input(artifact_type="UNKNOWN"),
        valid_input(extra_field="not allowed"),
        valid_input(source_type="DOCUMENT", content="C:/fake/spec.pdf"),
        valid_input(source_type="IMAGE", content="fake-image-reference"),
    ],
)
def test_invalid_or_unsupported_inputs_are_rejected(payload):
    with pytest.raises(ValidationError):
        ImplementationInput(**payload)


@pytest.mark.parametrize(
    "overrides",
    [
        {"selected_outputs": ["UNKNOWN"]},
        {"selected_outputs": ["PROJECT_STRUCTURE", "PROJECT_STRUCTURE"]},
        {"selected_outputs": []},
        {"inputs": []},
        {"unexpected": True},
    ],
)
def test_workspace_request_rejects_invalid_shape(overrides):
    payload = {
        "inputs": [valid_input()],
        "selected_outputs": ["PROJECT_STRUCTURE"],
        **overrides,
    }
    with pytest.raises(ValidationError):
        Agent3WorkspaceRequest(**payload)


def test_workspace_request_accepts_valid_contract_without_fabricating_ids():
    request = Agent3WorkspaceRequest(
        inputs=[valid_input()], selected_outputs=["PROJECT_STRUCTURE", "BACKEND_CODE"]
    )
    assert request.model_dump(mode="json") == {
        "inputs": [
            {
                "source_type": "TEXT",
                "artifact_type": "FUNCTIONAL_REQUIREMENTS",
                "content": "Customers can create bookings.",
                "label": None,
            }
        ],
        "selected_outputs": ["PROJECT_STRUCTURE", "BACKEND_CODE"],
    }
