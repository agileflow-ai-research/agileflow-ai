"""Replaceable sequence-pair NLI boundary for requirement conflicts."""

from typing import Protocol

from app.modules.agents.requirements.quality.contracts import NliScoreVector


class RequirementConflictProviderError(RuntimeError):
    """Safe NLI provider failure without implementation details."""


class RequirementConflictProvider(Protocol):
    @property
    def configuration(self) -> dict[str, object]: ...

    def evaluate(
        self, pairs: tuple[tuple[str, str], ...]
    ) -> tuple[NliScoreVector, ...]: ...
