"""Focused construction for the N3-to-N4 quality input boundary."""

from pathlib import Path

from app.modules.agents.requirements.discovery.dependencies import (
    build_discovery_input_loader,
    build_discovery_storage,
)
from app.modules.agents.requirements.quality.input import QualityInputLoader
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


def build_quality_input_loader(root: Path) -> QualityInputLoader:
    return QualityInputLoader(
        RequirementWorkflowStorage(root),
        build_discovery_input_loader(root),
        build_discovery_storage(root),
    )
