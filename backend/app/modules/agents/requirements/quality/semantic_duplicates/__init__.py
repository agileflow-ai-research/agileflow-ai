"""Semantic duplicate detection using replaceable local embeddings."""

from app.modules.agents.requirements.quality.semantic_duplicates.protocol import (
    RequirementEmbeddingProvider,
    RequirementEmbeddingProviderError,
)
from app.modules.agents.requirements.quality.semantic_duplicates.service import (
    SemanticDuplicateError,
    SemanticDuplicateErrorCode,
    SemanticDuplicateService,
)
from app.modules.agents.requirements.quality.semantic_duplicates.transformer import (
    SentenceTransformerEmbeddingProvider,
)

__all__ = [
    "RequirementEmbeddingProvider",
    "RequirementEmbeddingProviderError",
    "SemanticDuplicateError",
    "SemanticDuplicateErrorCode",
    "SemanticDuplicateService",
    "SentenceTransformerEmbeddingProvider",
]
