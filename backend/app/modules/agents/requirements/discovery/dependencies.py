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
from app.modules.agents.requirements.discovery.candidate_detection import RequirementCandidateDetector
from app.modules.agents.requirements.discovery.structuring import RequirementStructuringService
from app.modules.agents.requirements.discovery.storage import DiscoveryStorage
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore
from app.modules.agents.requirements.workflow.orchestration.n3_service import (
    RequirementN3OrchestrationService,
)
from app.modules.agents.requirements.workflow.orchestration.progression import (
    N4ProgressionCoordinator, WorkflowProgressionCoordinator,
)
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


def build_n3_orchestration_service(root: Path, *, progression=None) -> RequirementN3OrchestrationService:
    workflows = RequirementWorkflowStorage(root)
    storage = build_discovery_storage(root)
    return RequirementN3OrchestrationService(
        workflows,
        DiscoveryInputLoader(workflows, storage),
        RequirementCandidateDetector(),
        build_requirement_classification_service(),
        RequirementStructuringService(),
        storage,
        progression=progression,
    )


def build_workflow_progression(root: Path) -> WorkflowProgressionCoordinator:
    from app.modules.agents.requirements.quality.dependencies import build_n4_orchestration_service
    states = RequirementWorkflowStorage(root)
    n4_progression = N4ProgressionCoordinator(states, build_n4_orchestration_service(root))
    return WorkflowProgressionCoordinator(
        states, build_n3_orchestration_service(root, progression=n4_progression)
    )
