from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.agents.implementation.contracts.schemas import (
    Agent3WorkspaceRequest,
    ImplementationArtifactType,
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


def text_input(**overrides):
    return {
        "source_type": "TEXT",
        "artifact_type": "FUNCTIONAL_REQUIREMENTS",
        "content": "Customers can create bookings.",
        **overrides,
    }


def uploaded_file(source_type="DOCUMENT", artifact_type="API_SPECIFICATION"):
    return {
        "upload_id": "A3UP-0123456789abcdef0123456789abcdef",
        "source_type": source_type,
        "artifact_type": artifact_type,
        "label": "API",
        "original_filename": "api.pdf" if source_type == "DOCUMENT" else "flow.png",
        "mime_type": "application/pdf" if source_type == "DOCUMENT" else "image/png",
        "extension": ".pdf" if source_type == "DOCUMENT" else ".png",
        "size_bytes": 42,
        "sha256": "a" * 64,
        "created_at": datetime(2026, 10, 15, tzinfo=timezone.utc).isoformat(),
    }


def workspace(input_item):
    return Agent3WorkspaceRequest(
        inputs=[input_item], selected_outputs=["PROJECT_STRUCTURE"]
    )


def test_frozen_enum_values_are_exact():
    assert [item.value for item in ImplementationInputSourceType] == SOURCE_TYPES
    assert [item.value for item in ImplementationArtifactType] == ARTIFACT_TYPES
    assert [item.value for item in ImplementationOutputCode] == OUTPUT_CODES


def test_text_requires_trimmed_content_and_rejects_file():
    request = workspace(text_input(content="  Build a booking API.  ", label=" API "))
    assert request.inputs[0].content == "Build a booking API."
    assert request.inputs[0].label == "API"
    with pytest.raises(ValidationError):
        workspace(text_input(content=" "))
    with pytest.raises(ValidationError):
        workspace(text_input(file=uploaded_file()))


def test_document_requires_matching_uploaded_metadata_and_rejects_content():
    item = {
        "source_type": "DOCUMENT",
        "artifact_type": "API_SPECIFICATION",
        "file": uploaded_file(),
    }
    assert workspace(item).inputs[0].file.upload_id.startswith("A3UP-")
    with pytest.raises(ValidationError):
        workspace({key: value for key, value in item.items() if key != "file"})
    with pytest.raises(ValidationError):
        workspace({**item, "content": "Pretend PDF data"})
    with pytest.raises(ValidationError):
        workspace({**item, "file": uploaded_file("IMAGE", "API_SPECIFICATION")})


def test_image_requires_matching_uploaded_metadata_and_rejects_content():
    item = {
        "source_type": "IMAGE",
        "artifact_type": "UI_WIREFRAMES",
        "file": uploaded_file("IMAGE", "UI_WIREFRAMES"),
    }
    assert workspace(item).inputs[0].file.source_type == "IMAGE"
    with pytest.raises(ValidationError):
        workspace({key: value for key, value in item.items() if key != "file"})
    with pytest.raises(ValidationError):
        workspace({**item, "content": "Pretend image data"})
    with pytest.raises(ValidationError):
        workspace({**item, "artifact_type": "API_SPECIFICATION"})


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
        "inputs": [text_input()],
        "selected_outputs": ["PROJECT_STRUCTURE"],
        **overrides,
    }
    with pytest.raises(ValidationError):
        Agent3WorkspaceRequest(**payload)


def test_input_and_workspace_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        workspace(text_input(unexpected=True))
    with pytest.raises(ValidationError):
        Agent3WorkspaceRequest(
            inputs=[text_input()],
            selected_outputs=["PROJECT_STRUCTURE"],
            unexpected=True,
        )
