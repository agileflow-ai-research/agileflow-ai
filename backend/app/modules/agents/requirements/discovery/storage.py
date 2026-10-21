"""N3 storage boundary built solely on the shared typed artifact store."""

from app.modules.agents.requirements.infrastructure.artifact_paths import RequirementArtifactKind
from app.modules.agents.requirements.infrastructure.artifact_store import (
    JsonArtifactStore,
    JsonArtifactStoreError,
)
from app.modules.agents.requirements.processing.preparation.schemas import (
    EvidenceChunkResult,
    EvidencePreparationRecord,
)


class DiscoveryStorageError(RuntimeError):
    """Safe storage failure without exposing paths or parser details."""


class DiscoveryStorage:
    """Read N2 evidence sidecars; later N3 artifacts can extend this boundary."""

    def __init__(self, artifacts: JsonArtifactStore) -> None:
        self._artifacts = artifacts

    def load_preparation(self, agent_project_id: str, source_id: str) -> EvidencePreparationRecord | None:
        return self._load(
            agent_project_id, source_id, RequirementArtifactKind.EVIDENCE_PREPARATION,
            EvidencePreparationRecord,
        )

    def load_chunks(self, agent_project_id: str, source_id: str) -> EvidenceChunkResult | None:
        return self._load(
            agent_project_id, source_id, RequirementArtifactKind.CHUNK_RESULT,
            EvidenceChunkResult,
        )

    def _load(self, agent_project_id, source_id, kind, model):
        try:
            return self._artifacts.load(
                agent_project_id=agent_project_id,
                source_id=source_id,
                kind=kind,
                model=model,
            )
        except JsonArtifactStoreError as exc:
            raise DiscoveryStorageError("Discovery evidence artifact is unavailable") from exc
