"""Focused construction for the N3-to-N4 quality input boundary."""

from pathlib import Path

from app.modules.agents.requirements.discovery.dependencies import (
    build_discovery_input_loader,
    build_discovery_storage,
)
from app.modules.agents.requirements.quality.input import QualityInputLoader
from app.modules.agents.requirements.quality.semantic_duplicates.service import (
    DEFAULT_SEMANTIC_DUPLICATE_THRESHOLD,
    SemanticDuplicateService,
)
from app.modules.agents.requirements.quality.semantic_duplicates.transformer import (
    DEFAULT_EMBEDDING_MODEL_ID,
    SentenceTransformerEmbeddingProvider,
)
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


def build_quality_input_loader(root: Path) -> QualityInputLoader:
    return QualityInputLoader(
        RequirementWorkflowStorage(root),
        build_discovery_input_loader(root),
        build_discovery_storage(root),
    )


def build_semantic_duplicate_service(
    *, model_id: str = DEFAULT_EMBEDDING_MODEL_ID,
    revision: str | None = None, device: str = "cpu", batch_size: int = 32,
    local_files_only: bool = False,
    threshold: float = DEFAULT_SEMANTIC_DUPLICATE_THRESHOLD,
) -> SemanticDuplicateService:
    provider = SentenceTransformerEmbeddingProvider(
        model_id=model_id, revision=revision, device=device,
        batch_size=batch_size, local_files_only=local_files_only,
    )
    return SemanticDuplicateService(provider, threshold=threshold)
