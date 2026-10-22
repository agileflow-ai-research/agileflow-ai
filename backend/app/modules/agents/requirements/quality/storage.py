from app.modules.agents.requirements.infrastructure.artifact_paths import RequirementArtifactKind
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStoreError
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256


class QualityStorageError(RuntimeError): pass


class QualityStorage:
    def __init__(self, artifacts): self._artifacts = artifacts

    def save(self, project, execution_id, kind, value):
        try:
            existing = self._artifacts.load(agent_project_id=project, execution_id=execution_id,
                                            kind=kind, model=type(value))
            if existing is not None and existing != value:
                raise QualityStorageError("Historical quality artifact cannot be overwritten")
            if existing is None:
                self._artifacts.save(agent_project_id=project, execution_id=execution_id,
                                     kind=kind, value=value)
            return stable_json_sha256(value.model_dump(mode="json"))
        except JsonArtifactStoreError as exc:
            raise QualityStorageError("Quality artifact could not be persisted") from exc

    def load(self, project, execution_id, kind, model):
        try:
            value = self._artifacts.load(agent_project_id=project, execution_id=execution_id,
                                         kind=kind, model=model)
        except JsonArtifactStoreError as exc:
            raise QualityStorageError("Quality artifact is unavailable") from exc
        if value is None: raise QualityStorageError("Quality artifact is unavailable")
        return value

    def save_input(self, p, e, v): return self.save(p, e, RequirementArtifactKind.QUALITY_INPUT, v)
    def save_exact(self, p, e, v): return self.save(p, e, RequirementArtifactKind.QUALITY_EXACT_DUPLICATES, v)
    def save_semantic(self, p, e, v): return self.save(p, e, RequirementArtifactKind.QUALITY_SEMANTIC_DUPLICATES, v)
    def save_conflicts(self, p, e, v): return self.save(p, e, RequirementArtifactKind.QUALITY_CONFLICTS, v)
    def save_clarity(self, p, e, v): return self.save(p, e, RequirementArtifactKind.QUALITY_CLARITY, v)
    def save_findings(self, p, e, v): return self.save(p, e, RequirementArtifactKind.QUALITY_FINDINGS, v)
