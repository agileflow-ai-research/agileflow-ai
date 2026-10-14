from enum import Enum


class TraceabilityRelationType(str, Enum):
    """Initial canonical relation vocabulary for Agent 1 artifacts."""

    DERIVED_FROM = "DERIVED_FROM"
    REFINES = "REFINES"
    ACCEPTANCE_CRITERION_FOR = "ACCEPTANCE_CRITERION_FOR"
    IDENTIFIES_ISSUE_IN = "IDENTIFIES_ISSUE_IN"
    RELATED_TO = "RELATED_TO"
