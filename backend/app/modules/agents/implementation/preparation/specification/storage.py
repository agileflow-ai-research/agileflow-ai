from pathlib import Path
from threading import Lock

from app.modules.agents.implementation.infrastructure.sidecar import (
    load_model_sidecar,
    project_sidecar_path,
    save_model_sidecar,
)

from .schemas import ProjectSpecificationRecord


class ProjectSpecificationStorageError(RuntimeError):
    pass


class ProjectSpecificationStorage:
    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(self, agent_project_id: str, owner_user_id: str):
        record = load_model_sidecar(
            self._path(agent_project_id),
            ProjectSpecificationRecord,
            error_type=ProjectSpecificationStorageError,
            unavailable_message="Project specification state is unavailable",
        )
        if record is None:
            return None
        if (
            record.agent_project_id != agent_project_id
            or record.owner_user_id != owner_user_id
        ):
            raise ProjectSpecificationStorageError(
                "Project specification state identity is invalid"
            )
        return record

    def save(self, record: ProjectSpecificationRecord) -> None:
        save_model_sidecar(
            self._path(record.agent_project_id),
            record,
            lock=self._lock,
            error_type=ProjectSpecificationStorageError,
            failure_message="Project specification state could not be stored",
        )

    def _path(self, agent_project_id: str) -> Path:
        return project_sidecar_path(
            self._root,
            agent_project_id,
            "specification.json",
            error_type=ProjectSpecificationStorageError,
            unsafe_path_message="Unsafe project specification storage path",
        )
