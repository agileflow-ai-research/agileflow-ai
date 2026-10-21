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
from app.modules.agents.requirements.discovery.contracts import (
    RequirementCandidateSet,
    RequirementClassificationSet,
    StructuredRequirementSet,
)
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256


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

    def save_candidates(self, agent_project_id, execution_id, value):
        return self._save_execution(agent_project_id, execution_id, RequirementArtifactKind.DISCOVERY_CANDIDATES, value)

    def load_candidates(self, agent_project_id, execution_id):
        return self._load_execution(agent_project_id, execution_id, RequirementArtifactKind.DISCOVERY_CANDIDATES, RequirementCandidateSet)

    def save_classifications(self, agent_project_id, execution_id, value):
        return self._save_execution(agent_project_id, execution_id, RequirementArtifactKind.DISCOVERY_CLASSIFICATIONS, value)

    def load_classifications(self, agent_project_id, execution_id):
        return self._load_execution(agent_project_id, execution_id, RequirementArtifactKind.DISCOVERY_CLASSIFICATIONS, RequirementClassificationSet)

    def save_structured_requirements(self, agent_project_id, execution_id, value):
        return self._save_execution(agent_project_id, execution_id, RequirementArtifactKind.DISCOVERY_STRUCTURED, value)

    def load_structured_requirements(self, agent_project_id, execution_id):
        return self._load_execution(agent_project_id, execution_id, RequirementArtifactKind.DISCOVERY_STRUCTURED, StructuredRequirementSet)

    def _save_execution(self, project_id, execution_id, kind, value):
        try:
            existing = self._artifacts.load(agent_project_id=project_id, execution_id=execution_id, kind=kind, model=type(value))
            if existing is not None:
                if existing != value:
                    raise DiscoveryStorageError("Historical discovery artifact cannot be overwritten")
                return stable_json_sha256(value.model_dump(mode="json"))
            self._artifacts.save(agent_project_id=project_id, execution_id=execution_id, kind=kind, value=value)
            return stable_json_sha256(value.model_dump(mode="json"))
        except JsonArtifactStoreError as exc:
            raise DiscoveryStorageError("Discovery artifact could not be persisted") from exc

    def _load_execution(self, project_id, execution_id, kind, model):
        try:
            value = self._artifacts.load(agent_project_id=project_id, execution_id=execution_id, kind=kind, model=model)
        except JsonArtifactStoreError as exc:
            raise DiscoveryStorageError("Discovery artifact is unavailable") from exc
        if value is None:
            raise DiscoveryStorageError("Discovery artifact is unavailable")
        return value

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
