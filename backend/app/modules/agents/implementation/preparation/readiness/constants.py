from app.modules.agents.implementation.contracts.schemas import ImplementationArtifactType


MAX_TEXT_INPUTS = 50
MAX_TEXT_INPUT_CHARACTERS = 200_000
MAX_TOTAL_TEXT_CHARACTERS = 1_000_000
MAX_UPLOAD_REFERENCES = 100

REQUIREMENTS_ARTIFACTS = frozenset(
    {
        ImplementationArtifactType.SRS,
        ImplementationArtifactType.FUNCTIONAL_REQUIREMENTS,
        ImplementationArtifactType.NON_FUNCTIONAL_REQUIREMENTS,
        ImplementationArtifactType.USER_STORIES,
        ImplementationArtifactType.ACCEPTANCE_CRITERIA,
    }
)
DESIGN_ARTIFACTS = frozenset(
    {
        ImplementationArtifactType.SYSTEM_ARCHITECTURE,
        ImplementationArtifactType.UML_DIAGRAMS,
        ImplementationArtifactType.DATABASE_SCHEMA,
        ImplementationArtifactType.API_SPECIFICATION,
        ImplementationArtifactType.UI_WIREFRAMES,
        ImplementationArtifactType.UI_FLOW,
    }
)
IMPLEMENTATION_ARTIFACTS = frozenset(
    {
        ImplementationArtifactType.IMPLEMENTATION_TASKS,
        ImplementationArtifactType.PRODUCT_BACKLOG,
        ImplementationArtifactType.TECHNICAL_CONSTRAINTS,
        ImplementationArtifactType.TECHNOLOGY_STACK,
    }
)
TEST_ARTIFACTS = frozenset(
    {
        ImplementationArtifactType.UNIT_TEST_CASES,
        ImplementationArtifactType.API_TEST_CASES,
        ImplementationArtifactType.INTEGRATION_TEST_CASES,
        ImplementationArtifactType.FUNCTIONAL_TEST_CASES,
        ImplementationArtifactType.E2E_TEST_CASES,
        ImplementationArtifactType.SECURITY_TEST_CASES,
        ImplementationArtifactType.ACCEPTANCE_TEST_CASES,
        ImplementationArtifactType.TEST_TRACEABILITY,
    }
)
BEHAVIOR_ARTIFACTS = frozenset(
    {
        ImplementationArtifactType.SRS,
        ImplementationArtifactType.FUNCTIONAL_REQUIREMENTS,
        ImplementationArtifactType.USER_STORIES,
        ImplementationArtifactType.ACCEPTANCE_CRITERIA,
        ImplementationArtifactType.IMPLEMENTATION_TASKS,
        ImplementationArtifactType.PRODUCT_BACKLOG,
    }
)

EFFECTIVE_STACK = {
    "frontend": "React + Vite",
    "styling": "Plain CSS",
    "backend": "Node.js + Express.js",
    "database": "MySQL",
    "language": "JavaScript",
    "api_style": "REST",
}
