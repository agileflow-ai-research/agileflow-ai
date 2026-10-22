from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)


ZERO_SHOT_CLASSIFIER_VERSION = "1"
ZERO_SHOT_LABEL_MAP_VERSION = "1"
ZERO_SHOT_TEMPLATE_VERSION = "1"

MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
MODEL_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
MODEL_TASK = "zero-shot-classification"
HYPOTHESIS_TEMPLATE = "This software-engineering text describes {}."

MODEL_DISPLAY_THRESHOLD = 0.50
MAX_DISPLAY_LABELS = 4
INFERENCE_BATCH_SIZE = 4

# This frozen map is part of the research method. Changing any description
# requires incrementing ZERO_SHOT_LABEL_MAP_VERSION.
CANDIDATE_LABELS: dict[ArtifactDetectionLabel, str] = {
    ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS:
        "functional software requirements describing system behavior or capabilities",
    ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS:
        "non-functional software requirements describing quality attributes such as performance, security, availability, or usability",
    ArtifactDetectionLabel.USER_STORIES:
        "agile user stories describing a user role, goal, and benefit",
    ArtifactDetectionLabel.ACCEPTANCE_CRITERIA:
        "acceptance criteria defining conditions that must be satisfied for a feature",
    ArtifactDetectionLabel.SYSTEM_ARCHITECTURE:
        "software system architecture describing components, layers, and interactions",
    ArtifactDetectionLabel.DATABASE_SCHEMA:
        "database schema describing tables, fields, keys, relationships, or data structures",
    ArtifactDetectionLabel.API_SPECIFICATION:
        "API specification describing endpoints, methods, requests, responses, or status codes",
    ArtifactDetectionLabel.UI_FLOW:
        "user interface flow or navigation between screens",
    ArtifactDetectionLabel.TECHNOLOGY_STACK:
        "software technology stack describing frameworks, languages, databases, or tools",
    ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS:
        "technical implementation constraints or restrictions",
    ArtifactDetectionLabel.IMPLEMENTATION_TASKS:
        "software development implementation tasks or work items",
    ArtifactDetectionLabel.TEST_CASES:
        "software test cases or test specifications",
    ArtifactDetectionLabel.OTHER_CONTEXT:
        "general project context that is not one of the software engineering artifacts above",
}
