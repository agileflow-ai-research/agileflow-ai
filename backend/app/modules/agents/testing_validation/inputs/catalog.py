"""Artifact policy for TEST_GENERATION inputs, derived from contract v1.1 §2.4–2.5.

This module decides which artifact types are accepted, which origin agent they are
normally produced by, and which source types are allowed. It does not analyze content.
"""

from app.modules.agents.testing_validation.contracts.enums import (
    Agent4ArtifactType as Artifact,
    Agent4InputSourceType as SourceType,
    InputOriginAgent,
    InputProcessingStatus,
)

REQUIREMENTS_AND_QUALITY = (
    Artifact.FUNCTIONAL_REQUIREMENTS,
    Artifact.NON_FUNCTIONAL_REQUIREMENTS,
    Artifact.USER_STORIES,
    Artifact.ACCEPTANCE_CRITERIA,
    Artifact.PERSONAS,
    Artifact.QUALITY_FINDINGS,
    Artifact.CLARIFICATION_QUESTIONS,
    Artifact.SRS,
)
DESIGN_AND_TECHNICAL = (
    Artifact.SYSTEM_ARCHITECTURE,
    Artifact.UML_DIAGRAMS,
    Artifact.DATABASE_SCHEMA,
    Artifact.API_SPECIFICATION,
    Artifact.WIREFRAMES,
    Artifact.UI_FLOW,
    Artifact.FEATURES,
)

# USER_STORIES is produced by either Agent 1 or Agent 2, so its origin must be chosen.
_ORIGINS: dict[Artifact, tuple[InputOriginAgent, ...]] = {
    **{artifact: (InputOriginAgent.AGENT_1,) for artifact in REQUIREMENTS_AND_QUALITY},
    **{artifact: (InputOriginAgent.AGENT_2,) for artifact in DESIGN_AND_TECHNICAL},
    Artifact.USER_STORIES: (InputOriginAgent.AGENT_1, InputOriginAgent.AGENT_2),
}

# Only visual artifacts may be supplied as images, because image understanding is not implemented.
_IMAGE_ELIGIBLE = frozenset({
    Artifact.SYSTEM_ARCHITECTURE,
    Artifact.UML_DIAGRAMS,
    Artifact.DATABASE_SCHEMA,
    Artifact.WIREFRAMES,
    Artifact.UI_FLOW,
})

# Primary functional-context artifacts. At least one usable one will be required by readiness
# in a later step. This step only records which artifacts belong to that group.
PRIMARY_FUNCTIONAL = frozenset({
    Artifact.FUNCTIONAL_REQUIREMENTS,
    Artifact.USER_STORIES,
    Artifact.ACCEPTANCE_CRITERIA,
    Artifact.SRS,
})


def origins_for(artifact: Artifact) -> tuple[InputOriginAgent, ...]:
    return _ORIGINS[artifact]


def resolve_origin(artifact: Artifact, origin: InputOriginAgent | None) -> InputOriginAgent:
    options = origins_for(artifact)
    if origin is None:
        if len(options) == 1:
            return options[0]
        raise ValueError(f"{artifact.value} requires origin_agent AGENT_1 or AGENT_2")
    if origin not in options:
        allowed = " or ".join(item.value for item in options)
        raise ValueError(f"{artifact.value} can only be normally supplied by {allowed}")
    return origin


def validate_source_type(artifact: Artifact, source_type: SourceType) -> None:
    if source_type is SourceType.IMAGE and artifact not in _IMAGE_ELIGIBLE:
        raise ValueError(f"{artifact.value} cannot be supplied as an IMAGE source")


def processing_status_for(source_type: SourceType) -> InputProcessingStatus:
    # Mirrors contract v1.1 §2.8. IMAGE is never treated as understood.
    if source_type is SourceType.TEXT:
        return InputProcessingStatus.COLLECTED
    if source_type is SourceType.DOCUMENT:
        return InputProcessingStatus.UPLOADED
    return InputProcessingStatus.PENDING_ANALYSIS
