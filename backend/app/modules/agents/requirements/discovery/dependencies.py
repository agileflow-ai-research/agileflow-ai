"""N3-specific construction kept outside the main API dependency module."""

from pathlib import Path

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
