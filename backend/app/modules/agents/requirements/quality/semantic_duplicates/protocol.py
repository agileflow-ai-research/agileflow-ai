"""Replaceable embedding boundary for semantic quality analysis."""

from typing import Protocol

from app.modules.agents.requirements.quality.contracts import EmbeddingModelIdentity


Embedding = tuple[float, ...]


class RequirementEmbeddingProviderError(RuntimeError):
    """Safe provider failure without model/cache implementation details."""


class RequirementEmbeddingProvider(Protocol):
    @property
    def model_identity(self) -> EmbeddingModelIdentity: ...

    def encode(self, statements: tuple[str, ...]) -> tuple[Embedding, ...]: ...
