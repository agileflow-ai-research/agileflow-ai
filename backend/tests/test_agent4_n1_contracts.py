from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.common.status import AgentStage
from app.modules.agents.design_planning.schemas import DesignPlanningOutputCode
from app.modules.agents.requirements.schemas import RequirementOutputCode
from app.modules.agents.testing_validation.contracts.sources import (
    AGENT1_TEST_GENERATION_INPUT_ARTIFACT_TYPES,
    AGENT2_TEST_GENERATION_INPUT_ARTIFACT_TYPES,
    PRIMARY_FUNCTIONAL_ARTIFACT_TYPES,
    TEST_GENERATION_ARTIFACT_CATALOG,
    TestGenerationInputArtifactGroup as ArtifactGroup,
    TestGenerationInputArtifactType as ArtifactType,
    TestGenerationInputDescriptor as InputDescriptor,
    TestGenerationInputOriginAgent as OriginAgent,
    TestGenerationInputProvenance as InputProvenance,
    TestGenerationInputSourceType as InputSourceType,
    TestGenerationInputSuppliedVia as SuppliedVia,
    get_test_generation_artifact_policy,
    validate_test_generation_input_policy,
)
from app.modules.agents.testing_validation.schemas import (
    TestGenerationOutputCode as OutputCode,
)
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
    AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    AGENT4_TEST_GENERATION_NODE_ORDER,
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4TestGenerationWorkflowRecord,
    Agent4WorkflowNodeState,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from test_standalone_foundation import FakeAgentRunRepository


AGENT1_ARTIFACT_CODES = [
    "FUNCTIONAL_REQUIREMENTS",
    "NON_FUNCTIONAL_REQUIREMENTS",
    "USER_STORIES",
    "ACCEPTANCE_CRITERIA",
    "SRS",
    "PERSONAS",
    "QUALITY_FINDINGS",
    "CLARIFICATION_QUESTIONS",
]

AGENT2_ARTIFACT_CODES = [
    "SYSTEM_ARCHITECTURE",
    "UML_DIAGRAMS",
    "DATABASE_SCHEMA",
    "API_SPECIFICATION",
    "WIREFRAMES",
    "UI_FLOW",
    "FEATURES",
    "USER_STORIES",
]

COMBINED_ARTIFACT_CODES = [
    "FUNCTIONAL_REQUIREMENTS",
    "NON_FUNCTIONAL_REQUIREMENTS",
    "USER_STORIES",
    "ACCEPTANCE_CRITERIA",
    "SRS",
    "PERSONAS",
    "QUALITY_FINDINGS",
    "CLARIFICATION_QUESTIONS",
    "SYSTEM_ARCHITECTURE",
    "UML_DIAGRAMS",
    "DATABASE_SCHEMA",
    "API_SPECIFICATION",
    "WIREFRAMES",
    "UI_FLOW",
    "FEATURES",
]

OUTPUT_CODES = [
    "UNIT_TEST_CASES",
    "API_TEST_CASES",
    "INTEGRATION_TEST_CASES",
    "FUNCTIONAL_TEST_CASES",
    "E2E_TEST_CASES",
    "REGRESSION_TEST_CASES",
    "SECURITY_TEST_CASES",
    "ACCEPTANCE_TEST_CASES",
    "TEST_TRACEABILITY",
]


def descriptor(
    artifact_type: str = "FUNCTIONAL_REQUIREMENTS",
    source_type: str = "TEXT",
    origin: str = "AGENT_1",
) -> InputDescriptor:
    return InputDescriptor.model_validate(
        {
            "artifact_type": artifact_type,
            "source_type": source_type,
            "provenance": {
                "normally_supplied_by": origin,
                "supplied_via": "STANDALONE_MANUAL_INPUT",
            },
        }
    )


def test_agent1_input_artifacts_use_exact_existing_canonical_codes():
    assert [item.value for item in AGENT1_TEST_GENERATION_INPUT_ARTIFACT_TYPES] == (
        AGENT1_ARTIFACT_CODES
    )
    for code in AGENT1_ARTIFACT_CODES:
        assert RequirementOutputCode(code).value == code


def test_agent2_input_artifacts_use_exact_existing_canonical_codes():
    assert [item.value for item in AGENT2_TEST_GENERATION_INPUT_ARTIFACT_TYPES] == (
        AGENT2_ARTIFACT_CODES
    )
    for code in AGENT2_ARTIFACT_CODES:
        assert DesignPlanningOutputCode(code).value == code


def test_combined_artifact_vocabulary_is_exact_and_deduplicated():
    assert [item.value for item in ArtifactType] == (
        COMBINED_ARTIFACT_CODES
    )
    assert [policy.artifact_type.value for policy in TEST_GENERATION_ARTIFACT_CATALOG] == (
        COMBINED_ARTIFACT_CODES
    )


@pytest.mark.parametrize("source_type", ["TEXT", "DOCUMENT", "IMAGE"])
def test_source_type_vocabulary_is_exact(source_type):
    assert [item.value for item in InputSourceType] == ["TEXT", "DOCUMENT", "IMAGE"]
    assert InputSourceType(source_type).value == source_type


def test_unknown_source_type_is_rejected():
    with pytest.raises(ValidationError):
        descriptor(source_type="PDF")


def test_unknown_origin_agent_is_rejected():
    with pytest.raises(ValidationError):
        descriptor(origin="AGENT_3")


def test_agent1_only_artifact_accepts_agent1_and_rejects_agent2():
    assert descriptor().provenance.normally_supplied_by is (
        OriginAgent.AGENT_1
    )
    with pytest.raises(ValidationError, match="cannot declare origin AGENT_2"):
        descriptor(origin="AGENT_2")


def test_agent2_only_artifact_accepts_agent2_and_rejects_agent1():
    assert descriptor("API_SPECIFICATION", origin="AGENT_2").artifact_type is (
        ArtifactType.API_SPECIFICATION
    )
    with pytest.raises(ValidationError, match="cannot declare origin AGENT_1"):
        descriptor("API_SPECIFICATION", origin="AGENT_1")


def test_user_stories_has_one_artifact_code_and_both_real_producer_origins():
    policy = get_test_generation_artifact_policy(
        ArtifactType.USER_STORIES
    )
    assert policy.allowed_origin_agents == (
        OriginAgent.AGENT_1,
        OriginAgent.AGENT_2,
    )
    assert descriptor("USER_STORIES", origin="AGENT_1")
    assert descriptor("USER_STORIES", origin="AGENT_2")


def test_supplied_via_is_exact_and_rejects_false_generation_provenance():
    assert [item.value for item in SuppliedVia] == [
        "STANDALONE_MANUAL_INPUT"
    ]
    provenance = InputProvenance(
        normally_supplied_by=OriginAgent.AGENT_1
    )
    assert provenance.supplied_via is (
        SuppliedVia.STANDALONE_MANUAL_INPUT
    )
    with pytest.raises(ValidationError):
        InputProvenance.model_validate(
            {
                "normally_supplied_by": "AGENT_1",
                "supplied_via": "GENERATED_BY_AGENT_1",
            }
        )


def test_artifact_groups_are_derived_by_the_catalog():
    assert get_test_generation_artifact_policy(
        ArtifactType.QUALITY_FINDINGS
    ).group is ArtifactGroup.REQUIREMENTS_QUALITY
    assert get_test_generation_artifact_policy(
        ArtifactType.DATABASE_SCHEMA
    ).group is ArtifactGroup.DESIGN_TECHNICAL


@pytest.mark.parametrize(
    "artifact_type",
    ["FUNCTIONAL_REQUIREMENTS", "USER_STORIES", "ACCEPTANCE_CRITERIA", "SRS"],
)
def test_primary_functional_policy_identifies_required_types(artifact_type):
    artifact = ArtifactType(artifact_type)
    assert artifact in PRIMARY_FUNCTIONAL_ARTIFACT_TYPES
    assert get_test_generation_artifact_policy(artifact).primary_functional is True


@pytest.mark.parametrize(
    "artifact_type",
    sorted(set(COMBINED_ARTIFACT_CODES) - {
        "FUNCTIONAL_REQUIREMENTS", "USER_STORIES", "ACCEPTANCE_CRITERIA", "SRS"
    }),
)
def test_primary_functional_policy_does_not_mark_other_types(artifact_type):
    artifact = ArtifactType(artifact_type)
    assert artifact not in PRIMARY_FUNCTIONAL_ARTIFACT_TYPES
    assert get_test_generation_artifact_policy(artifact).primary_functional is False


@pytest.mark.parametrize(
    "artifact_type",
    ["SYSTEM_ARCHITECTURE", "UML_DIAGRAMS", "DATABASE_SCHEMA", "WIREFRAMES", "UI_FLOW"],
)
def test_image_policy_accepts_only_semantically_visual_artifacts(artifact_type):
    result = descriptor(artifact_type, source_type="IMAGE", origin="AGENT_2")
    assert result.source_type is InputSourceType.IMAGE


@pytest.mark.parametrize(
    ("artifact_type", "origin"),
    [("FUNCTIONAL_REQUIREMENTS", "AGENT_1"), ("API_SPECIFICATION", "AGENT_2")],
)
def test_image_policy_rejects_clearly_non_visual_artifacts(artifact_type, origin):
    with pytest.raises(ValidationError, match="cannot be supplied as IMAGE"):
        descriptor(artifact_type, source_type="IMAGE", origin=origin)


def test_policy_helper_rejects_mismatched_origin_directly():
    with pytest.raises(ValueError, match="cannot declare origin AGENT_2"):
        validate_test_generation_input_policy(
            artifact_type=ArtifactType.SRS,
            source_type=InputSourceType.DOCUMENT,
            normally_supplied_by=OriginAgent.AGENT_2,
        )


def test_existing_test_generation_output_vocabulary_remains_the_nine_codes():
    assert [item.value for item in OutputCode] == OUTPUT_CODES


@pytest.mark.parametrize(
    "alias",
    ["UI_WIREFRAMES", "IMPLEMENTATION_TASKS", "TEST_CASES", "PRODUCT_BACKLOG"],
)
def test_unknown_or_out_of_scope_artifact_aliases_are_rejected(alias):
    with pytest.raises(ValidationError):
        descriptor(alias)


def test_descriptor_serialization_is_deterministic_and_contains_no_processing_state():
    source = InputDescriptor.model_validate(
        {
            "artifact_type": "ACCEPTANCE_CRITERIA",
            "source_type": "DOCUMENT",
            "provenance": {"normally_supplied_by": "AGENT_1"},
            "label": "  Checkout criteria  ",
        }
    )
    assert source.model_dump(mode="json") == {
        "artifact_type": "ACCEPTANCE_CRITERIA",
        "source_type": "DOCUMENT",
        "provenance": {
            "normally_supplied_by": "AGENT_1",
            "supplied_via": "STANDALONE_MANUAL_INPUT",
        },
        "label": "Checkout criteria",
    }


def test_contract_use_creates_no_agent_run_and_does_not_mutate_workflow(tmp_path):
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    record = Agent4TestGenerationWorkflowRecord(
        schema_version=AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
        workflow_version=AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
        agent_project_id="AGP-001",
        owner_user_id="USR-001",
        agent_stage=AgentStage.TEST_GENERATION,
        pipeline_status=Agent4PipelineStatus.WAITING_FOR_HUMAN,
        current_node_id=Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP,
        nodes=[
            Agent4WorkflowNodeState(
                node_id=node_id,
                status=(
                    Agent4WorkflowNodeStatus.WAITING_FOR_HUMAN
                    if node_id is Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP
                    else Agent4WorkflowNodeStatus.LOCKED
                ),
                updated_at=now,
            )
            for node_id in AGENT4_TEST_GENERATION_NODE_ORDER
        ],
        created_at=now,
        updated_at=now,
    )
    storage = Agent4WorkflowStorage(tmp_path)
    storage.save(record)
    workflow_path = tmp_path / "AGP-001" / "workflow.json"
    before = workflow_path.read_bytes()
    runs = FakeAgentRunRepository()

    descriptor("FUNCTIONAL_REQUIREMENTS", "TEXT", "AGENT_1")

    assert workflow_path.read_bytes() == before
    assert runs.documents == {}
