"""Small typed JSON artifact store for future Agent 1 node storage."""

from pathlib import Path
from threading import RLock
from typing import TypeVar

from pydantic import BaseModel

from app.modules.agents.requirements.infrastructure.artifact_paths import (
    ArtifactPathError,
    RequirementArtifactKind,
    RequirementArtifactPaths,
)
from app.modules.agents.requirements.infrastructure.sidecar import (
    load_model_sidecar,
    remove_sidecar,
    save_model_sidecar,
)


ModelT = TypeVar("ModelT", bound=BaseModel)


class JsonArtifactStoreError(RuntimeError):
    pass


class JsonArtifactStore:
    """Persist typed JSON artifacts while keeping paths inside infrastructure."""

    def __init__(self, root: Path) -> None:
        self._paths = RequirementArtifactPaths(root)
        self._lock = RLock()

    def load(
        self,
        *,
        agent_project_id: str,
        kind: RequirementArtifactKind,
        model: type[ModelT],
        source_id: str | None = None,
    ) -> ModelT | None:
        path = self._resolve(agent_project_id, kind, source_id)
        return load_model_sidecar(
            path,
            model,
            error_type=JsonArtifactStoreError,
            unavailable_message="JSON artifact could not be loaded",
        )

    def save(
        self,
        *,
        agent_project_id: str,
        kind: RequirementArtifactKind,
        value: BaseModel,
        source_id: str | None = None,
    ) -> None:
        path = self._resolve(agent_project_id, kind, source_id)
        save_model_sidecar(
            path,
            value,
            lock=self._lock,
            error_type=JsonArtifactStoreError,
            failure_message="JSON artifact could not be persisted",
        )

    def remove(
        self,
        *,
        agent_project_id: str,
        kind: RequirementArtifactKind,
        source_id: str | None = None,
    ) -> None:
        path = self._resolve(agent_project_id, kind, source_id)
        remove_sidecar(
            path,
            lock=self._lock,
            error_type=JsonArtifactStoreError,
            failure_message="JSON artifact could not be removed",
        )

    def _resolve(
        self,
        agent_project_id: str,
        kind: RequirementArtifactKind,
        source_id: str | None,
    ) -> Path:
        try:
            if source_id is None:
                return self._paths.for_project(agent_project_id, kind)
            return self._paths.for_source(agent_project_id, source_id, kind)
        except ArtifactPathError as exc:
            raise JsonArtifactStoreError("JSON artifact path is invalid") from exc
