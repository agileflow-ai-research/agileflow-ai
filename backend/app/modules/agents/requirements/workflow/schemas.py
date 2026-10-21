"""Compatibility imports for the pre-R2 workflow contract module.

Current code should import from ``workflow.contracts`` modules directly.
"""

from app.modules.agents.requirements.workflow.contracts.n1 import (
    RequirementN1Confirmation,
    RequirementN1State,
    RequirementOutputCode,
    RequirementOutputSelectionUpdate,
)
from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2Error,
    RequirementN2Execution,
    RequirementN2ResultSummary,
    RequirementN2SourceProgress,
    RequirementN2SourceSnapshot,
    RequirementN2SourceStatus,
    RequirementN2Status,
)
from app.modules.agents.requirements.workflow.contracts.n3 import (
    RequirementN3Error,
    RequirementN3Execution,
    RequirementN3ResultSummary,
    RequirementN3Status,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.contracts.responses import (
    RequirementWorkflowResponse,
)


__all__ = [
    "RequirementN1Confirmation",
    "RequirementN1State",
    "RequirementN2Error",
    "RequirementN2Execution",
    "RequirementN2ResultSummary",
    "RequirementN2SourceProgress",
    "RequirementN2SourceSnapshot",
    "RequirementN2SourceStatus",
    "RequirementN2Status",
    "RequirementN3Error",
    "RequirementN3Execution",
    "RequirementN3ResultSummary",
    "RequirementN3Status",
    "RequirementOutputCode",
    "RequirementOutputSelectionUpdate",
    "RequirementWorkflowRecord",
    "RequirementWorkflowResponse",
]
