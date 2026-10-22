"""
Constants for the N4.4 Context Decision (CD1) stage.

Decision vocabulary (ContextDecisionStatus):
  PROCEED                 planning can continue with no context warning
  PROCEED_WITH_WARNINGS   planning allowed, with warnings recorded
  BLOCKED                 deterministic context problem (TB1 NOT_READY). Planning is not allowed.
BLOCKED is a context decision. A processing error is a separate, operational FAILED state.
"""

from enum import StrEnum


CONTEXT_DECISION_SCHEMA_VERSION = "1"
CONTEXT_DECISION_ENGINE_VERSION = "CD1"
CONTEXT_DECISION_POLICY_VERSION = "CP1"


class ContextDecisionStatus(StrEnum):
    PROCEED = "PROCEED"
    PROCEED_WITH_WARNINGS = "PROCEED_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class ConsolidatedFindingSeverity(StrEnum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"


class ConsolidatedFindingOrigin(StrEnum):
    TESTABILITY = "TESTABILITY"
    FEASIBILITY = "FEASIBILITY"
