"""N3-specific construction kept outside the main API dependency module."""

from pathlib import Path

from app.core.config import settings
from app.modules.agents.requirements.discovery.classification.service import (
    RequirementClassificationService,
)
from app.modules.agents.requirements.discovery.classification.transformer import (
    TransformerRequirementClassifier,
)
from app.modules.agents.requirements.discovery.input import DiscoveryInputLoader
from app.modules.agents.requirements.discovery.storage import DiscoveryStorage
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


def build_discovery_storage(root: Path) -> DiscoveryStorage:
    return DiscoveryStorage(JsonArtifactStore(root))


def build_discovery_input_loader(root: Path) -> DiscoveryInputLoader:
    return DiscoveryInputLoader(
        RequirementWorkflowStorage(root), build_discovery_storage(root)
    )


def build_requirement_classification_service() -> RequirementClassificationService:
    classifier = TransformerRequirementClassifier(
        model_id=settings.agent1_classifier_model_id,
        revision=settings.agent1_classifier_model_revision or None,
        device=settings.agent1_classifier_device,
        batch_size=settings.agent1_classifier_batch_size,
        local_files_only=settings.agent1_classifier_local_files_only,
    )
    return RequirementClassificationService(
        classifier,
        minimum_confidence=settings.agent1_classifier_minimum_confidence,
        minimum_margin=settings.agent1_classifier_minimum_margin,
    )
