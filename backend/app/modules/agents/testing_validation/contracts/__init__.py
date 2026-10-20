"""Public domain contracts for the Testing / Validation Agent."""

from app.modules.agents.testing_validation.contracts.sources import (
    AGENT1_TEST_GENERATION_INPUT_ARTIFACT_TYPES,
    AGENT2_TEST_GENERATION_INPUT_ARTIFACT_TYPES,
    PRIMARY_FUNCTIONAL_ARTIFACT_TYPES,
    TEST_GENERATION_ARTIFACT_CATALOG,
    TestGenerationArtifactPolicy,
    TestGenerationInputArtifactGroup,
    TestGenerationInputArtifactType,
    TestGenerationInputDescriptor,
    TestGenerationInputOriginAgent,
    TestGenerationInputProvenance,
    TestGenerationInputSourceType,
    TestGenerationInputSuppliedVia,
    get_test_generation_artifact_policy,
    validate_test_generation_input_policy,
)

__all__ = [
    "AGENT1_TEST_GENERATION_INPUT_ARTIFACT_TYPES",
    "AGENT2_TEST_GENERATION_INPUT_ARTIFACT_TYPES",
    "PRIMARY_FUNCTIONAL_ARTIFACT_TYPES",
    "TEST_GENERATION_ARTIFACT_CATALOG",
    "TestGenerationArtifactPolicy",
    "TestGenerationInputArtifactGroup",
    "TestGenerationInputArtifactType",
    "TestGenerationInputDescriptor",
    "TestGenerationInputOriginAgent",
    "TestGenerationInputProvenance",
    "TestGenerationInputSourceType",
    "TestGenerationInputSuppliedVia",
    "get_test_generation_artifact_policy",
    "validate_test_generation_input_policy",
]
