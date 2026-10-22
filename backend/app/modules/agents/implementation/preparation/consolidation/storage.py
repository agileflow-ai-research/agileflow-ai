from pathlib import Path
from threading import Lock

from app.modules.agents.implementation.infrastructure.sidecar import (
    load_model_sidecar,
    project_sidecar_path,
    save_model_sidecar,
)

from .schemas import ProjectConsolidationRecord, TrustedProjectSpecification


class ConsolidationStorageError(RuntimeError):
    pass


class ConsolidationStorage:
    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load_state(self, project_id: str, owner_id: str):
        return self._load(
            self._path(project_id, "project-consolidation.json"),
            ProjectConsolidationRecord,
            project_id,
            owner_id,
        )

    def load_final(self, project_id: str, owner_id: str):
        value = self._load(
            self._path(project_id, "trusted-project-specification.json"),
            TrustedProjectSpecification,
            project_id,
            owner_id,
        )
        return value

    def save_state(self, value: ProjectConsolidationRecord) -> None:
        self._save(
            self._path(value.agent_project_id, "project-consolidation.json"),
            value,
        )

    def save_final(self, value: TrustedProjectSpecification) -> None:
        self._save(
            self._path(
                value.agent_project_id, "trusted-project-specification.json"
            ),
            value,
        )

    def _path(self, project_id: str, name: str) -> Path:
        return project_sidecar_path(
            self._root,
            project_id,
            name,
            error_type=ConsolidationStorageError,
            unsafe_path_message="Unsafe project consolidation storage path",
        )

    @staticmethod
    def _load(path, model, project_id, owner_id):
        value = load_model_sidecar(
            path,
            model,
            error_type=ConsolidationStorageError,
            unavailable_message="Project consolidation state is unavailable",
        )
        if value is None:
            return None
        if value.agent_project_id != project_id:
            raise ConsolidationStorageError(
                "Project consolidation state identity is invalid"
            )
        if isinstance(value, ProjectConsolidationRecord):
            if value.owner_user_id != owner_id:
                raise ConsolidationStorageError(
                    "Project consolidation state identity is invalid"
                )
        return value

    def _save(self, path: Path, value) -> None:
        save_model_sidecar(
            path,
            value,
            lock=self._lock,
            error_type=ConsolidationStorageError,
            failure_message="Project consolidation state could not be stored",
        )
