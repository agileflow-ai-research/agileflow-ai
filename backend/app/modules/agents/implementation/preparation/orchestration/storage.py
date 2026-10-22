from pathlib import Path
from threading import Lock

from app.modules.agents.implementation.infrastructure.sidecar import (
    load_model_sidecar,
    project_sidecar_path,
    save_model_sidecar,
)

from .schemas import ProjectPreparationRecord


class ProjectPreparationStorageError(RuntimeError):
    pass


class ProjectPreparationStorage:
    """Atomic project-scoped orchestration state beside Agent 3 inputs."""

    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(
        self, *, agent_project_id: str, owner_user_id: str
    ) -> ProjectPreparationRecord | None:
        state_path = self._path(agent_project_id)
        record = load_model_sidecar(
            state_path,
            ProjectPreparationRecord,
            error_type=ProjectPreparationStorageError,
            unavailable_message="Project preparation state is unavailable",
        )
        if record is None:
            return None
        if (
            record.agent_project_id != agent_project_id
            or record.owner_user_id != owner_user_id
        ):
            raise ProjectPreparationStorageError(
                "Project preparation state identity is invalid"
            )
        return record

    def save(self, record: ProjectPreparationRecord) -> None:
        save_model_sidecar(
            self._path(record.agent_project_id),
            record,
            lock=self._lock,
            error_type=ProjectPreparationStorageError,
            failure_message="Project preparation state could not be stored",
        )

    def _path(self, agent_project_id: str) -> Path:
        return project_sidecar_path(
            self._root,
            agent_project_id,
            "preparation.json",
            error_type=ProjectPreparationStorageError,
            unsafe_path_message="Unsafe project preparation storage path",
        )
