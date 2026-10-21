"""Lightweight identity exports for requirement workflow orchestration."""

from typing import Any

from app.modules.agents.requirements.workflow.orchestration.identity import (
    n2_chunk_set_digest,
    n2_execution_key,
)
from app.modules.agents.requirements.workflow.orchestration.n3_identity import n3_execution_key


__all__ = [
    "RequirementN2OrchestrationService",
    "n2_chunk_set_digest",
    "n2_execution_key",
    "RequirementN3OrchestrationService",
    "n3_execution_key",
]


def __getattr__(name: str) -> Any:
    """Resolve legacy service exports only when a caller requests them."""
    if name == "RequirementN2OrchestrationService":
        from app.modules.agents.requirements.workflow.orchestration.n2_service import (
            RequirementN2OrchestrationService,
        )

        return RequirementN2OrchestrationService
    if name == "RequirementN3OrchestrationService":
        from app.modules.agents.requirements.workflow.orchestration.n3_service import (
            RequirementN3OrchestrationService,
        )

        return RequirementN3OrchestrationService
    raise AttributeError(name)
