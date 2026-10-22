from app.modules.agents.implementation.preparation.schemas import ArtifactDetectionLabel

from ..schemas import CanonicalSourceRef
from . import api, architecture, database, other, requirements, tasks, technology, tests, ui_flow


def extract_label(label: ArtifactDetectionLabel, text: str, source: CanonicalSourceRef):
    extractors = {
        ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS: requirements.functional,
        ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS: requirements.non_functional,
        ArtifactDetectionLabel.USER_STORIES: requirements.user_stories,
        ArtifactDetectionLabel.ACCEPTANCE_CRITERIA: requirements.acceptance,
        ArtifactDetectionLabel.SYSTEM_ARCHITECTURE: architecture.extract,
        ArtifactDetectionLabel.DATABASE_SCHEMA: database.extract,
        ArtifactDetectionLabel.API_SPECIFICATION: api.extract,
        ArtifactDetectionLabel.UI_FLOW: ui_flow.extract,
        ArtifactDetectionLabel.TECHNOLOGY_STACK: technology.extract,
        ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS: requirements.constraints,
        ArtifactDetectionLabel.IMPLEMENTATION_TASKS: tasks.extract,
        ArtifactDetectionLabel.TEST_CASES: tests.extract,
        ArtifactDetectionLabel.OTHER_CONTEXT: other.extract,
    }
    return extractors[label](text, source)
