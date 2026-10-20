"""Canonical N1 input vocabulary and policy for Agent 4 Test Generation."""

from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.agents.design_planning.schemas import DesignPlanningOutputCode
from app.modules.agents.requirements.schemas import RequirementOutputCode


class StrictAgent4InputContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TestGenerationInputArtifactType(StrEnum):
    FUNCTIONAL_REQUIREMENTS = RequirementOutputCode.FUNCTIONAL_REQUIREMENTS.value
    NON_FUNCTIONAL_REQUIREMENTS = RequirementOutputCode.NON_FUNCTIONAL_REQUIREMENTS.value
    USER_STORIES = RequirementOutputCode.USER_STORIES.value
    ACCEPTANCE_CRITERIA = RequirementOutputCode.ACCEPTANCE_CRITERIA.value
    SRS = RequirementOutputCode.SRS.value
    PERSONAS = RequirementOutputCode.PERSONAS.value
    QUALITY_FINDINGS = RequirementOutputCode.QUALITY_FINDINGS.value
    CLARIFICATION_QUESTIONS = RequirementOutputCode.CLARIFICATION_QUESTIONS.value
    SYSTEM_ARCHITECTURE = DesignPlanningOutputCode.SYSTEM_ARCHITECTURE.value
    UML_DIAGRAMS = DesignPlanningOutputCode.UML_DIAGRAMS.value
    DATABASE_SCHEMA = DesignPlanningOutputCode.DATABASE_SCHEMA.value
    API_SPECIFICATION = DesignPlanningOutputCode.API_SPECIFICATION.value
    WIREFRAMES = DesignPlanningOutputCode.WIREFRAMES.value
    UI_FLOW = DesignPlanningOutputCode.UI_FLOW.value
    FEATURES = DesignPlanningOutputCode.FEATURES.value


class TestGenerationInputArtifactGroup(StrEnum):
    REQUIREMENTS_QUALITY = "REQUIREMENTS_QUALITY"
    DESIGN_TECHNICAL = "DESIGN_TECHNICAL"


class TestGenerationInputSourceType(StrEnum):
    TEXT = "TEXT"
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"


class TestGenerationInputOriginAgent(StrEnum):
    AGENT_1 = "AGENT_1"
    AGENT_2 = "AGENT_2"


class TestGenerationInputSuppliedVia(StrEnum):
    STANDALONE_MANUAL_INPUT = "STANDALONE_MANUAL_INPUT"


AGENT1_TEST_GENERATION_INPUT_ARTIFACT_TYPES = (
    TestGenerationInputArtifactType.FUNCTIONAL_REQUIREMENTS,
    TestGenerationInputArtifactType.NON_FUNCTIONAL_REQUIREMENTS,
    TestGenerationInputArtifactType.USER_STORIES,
    TestGenerationInputArtifactType.ACCEPTANCE_CRITERIA,
    TestGenerationInputArtifactType.SRS,
    TestGenerationInputArtifactType.PERSONAS,
    TestGenerationInputArtifactType.QUALITY_FINDINGS,
    TestGenerationInputArtifactType.CLARIFICATION_QUESTIONS,
)

AGENT2_TEST_GENERATION_INPUT_ARTIFACT_TYPES = (
    TestGenerationInputArtifactType.SYSTEM_ARCHITECTURE,
    TestGenerationInputArtifactType.UML_DIAGRAMS,
    TestGenerationInputArtifactType.DATABASE_SCHEMA,
    TestGenerationInputArtifactType.API_SPECIFICATION,
    TestGenerationInputArtifactType.WIREFRAMES,
    TestGenerationInputArtifactType.UI_FLOW,
    TestGenerationInputArtifactType.FEATURES,
    TestGenerationInputArtifactType.USER_STORIES,
)

PRIMARY_FUNCTIONAL_ARTIFACT_TYPES = frozenset(
    {
        TestGenerationInputArtifactType.FUNCTIONAL_REQUIREMENTS,
        TestGenerationInputArtifactType.USER_STORIES,
        TestGenerationInputArtifactType.ACCEPTANCE_CRITERIA,
        TestGenerationInputArtifactType.SRS,
    }
)

_VISUAL_ARTIFACT_TYPES = frozenset(
    {
        TestGenerationInputArtifactType.SYSTEM_ARCHITECTURE,
        TestGenerationInputArtifactType.UML_DIAGRAMS,
        TestGenerationInputArtifactType.DATABASE_SCHEMA,
        TestGenerationInputArtifactType.WIREFRAMES,
        TestGenerationInputArtifactType.UI_FLOW,
    }
)


class TestGenerationArtifactPolicy(StrictAgent4InputContract):
    artifact_type: TestGenerationInputArtifactType
    group: TestGenerationInputArtifactGroup
    allowed_origin_agents: tuple[TestGenerationInputOriginAgent, ...]
    allowed_source_types: tuple[TestGenerationInputSourceType, ...]
    primary_functional: bool


def _policy_for(
    artifact_type: TestGenerationInputArtifactType,
) -> TestGenerationArtifactPolicy:
    agent1_artifacts = set(AGENT1_TEST_GENERATION_INPUT_ARTIFACT_TYPES)
    agent2_artifacts = set(AGENT2_TEST_GENERATION_INPUT_ARTIFACT_TYPES)
    origins = tuple(
        origin
        for origin, membership in (
            (TestGenerationInputOriginAgent.AGENT_1, agent1_artifacts),
            (TestGenerationInputOriginAgent.AGENT_2, agent2_artifacts),
        )
        if artifact_type in membership
    )
    source_types = (
        TestGenerationInputSourceType.TEXT,
        TestGenerationInputSourceType.DOCUMENT,
        *(
            (TestGenerationInputSourceType.IMAGE,)
            if artifact_type in _VISUAL_ARTIFACT_TYPES
            else ()
        ),
    )
    return TestGenerationArtifactPolicy(
        artifact_type=artifact_type,
        group=(
            TestGenerationInputArtifactGroup.REQUIREMENTS_QUALITY
            if artifact_type in agent1_artifacts
            else TestGenerationInputArtifactGroup.DESIGN_TECHNICAL
        ),
        allowed_origin_agents=origins,
        allowed_source_types=source_types,
        primary_functional=artifact_type in PRIMARY_FUNCTIONAL_ARTIFACT_TYPES,
    )


TEST_GENERATION_ARTIFACT_CATALOG = tuple(
    _policy_for(artifact_type) for artifact_type in TestGenerationInputArtifactType
)

_ARTIFACT_POLICY_BY_TYPE = MappingProxyType(
    {policy.artifact_type: policy for policy in TEST_GENERATION_ARTIFACT_CATALOG}
)


def get_test_generation_artifact_policy(
    artifact_type: TestGenerationInputArtifactType | str,
) -> TestGenerationArtifactPolicy:
    canonical_type = TestGenerationInputArtifactType(artifact_type)
    return _ARTIFACT_POLICY_BY_TYPE[canonical_type]


def validate_test_generation_input_policy(
    *,
    artifact_type: TestGenerationInputArtifactType | str,
    source_type: TestGenerationInputSourceType | str,
    normally_supplied_by: TestGenerationInputOriginAgent | str,
) -> TestGenerationArtifactPolicy:
    canonical_type = TestGenerationInputArtifactType(artifact_type)
    canonical_source = TestGenerationInputSourceType(source_type)
    canonical_origin = TestGenerationInputOriginAgent(normally_supplied_by)
    policy = get_test_generation_artifact_policy(canonical_type)
    if canonical_origin not in policy.allowed_origin_agents:
        raise ValueError(
            f"{canonical_type.value} cannot declare origin "
            f"{canonical_origin.value}"
        )
    if canonical_source not in policy.allowed_source_types:
        raise ValueError(
            f"{canonical_type.value} cannot be supplied as {canonical_source.value}"
        )
    return policy


class TestGenerationInputProvenance(StrictAgent4InputContract):
    normally_supplied_by: TestGenerationInputOriginAgent
    supplied_via: TestGenerationInputSuppliedVia = (
        TestGenerationInputSuppliedVia.STANDALONE_MANUAL_INPUT
    )


class TestGenerationInputDescriptor(StrictAgent4InputContract):
    artifact_type: TestGenerationInputArtifactType
    source_type: TestGenerationInputSourceType
    provenance: TestGenerationInputProvenance
    label: str | None = Field(default=None, max_length=200)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_policy(self) -> "TestGenerationInputDescriptor":
        validate_test_generation_input_policy(
            artifact_type=self.artifact_type,
            source_type=self.source_type,
            normally_supplied_by=self.provenance.normally_supplied_by,
        )
        return self
