"""Provider-neutral requirement classification boundary."""

from dataclasses import dataclass
from typing import Protocol

from app.modules.agents.requirements.discovery.contracts import (
    ClassificationScore,
    RequirementCandidate,
    RequirementClassificationLabel,
)


class RequirementClassifierError(RuntimeError):
    """Safe provider failure exposed to the classification service."""


@dataclass(frozen=True)
class ClassifierConfiguration:
    provider_type: str
    provider_version: str
    model_id: str
    requested_revision: str | None
    resolved_revision: str | None
    task: str
    label_descriptions: dict[RequirementClassificationLabel, str]
    hypothesis_template: str
    device: str
    batch_size: int
    local_files_only: bool


@dataclass(frozen=True)
class ProviderClassification:
    candidate_id: str
    winner: RequirementClassificationLabel
    scores: tuple[ClassificationScore, ...]


class RequirementClassifier(Protocol):
    @property
    def configuration(self) -> ClassifierConfiguration: ...

    def classify(
        self, candidates: tuple[RequirementCandidate, ...]
    ) -> tuple[ProviderClassification, ...]: ...
