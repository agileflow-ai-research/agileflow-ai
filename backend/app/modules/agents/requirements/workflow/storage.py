from pathlib import Path
from threading import RLock

from app.modules.agents.requirements.infrastructure.sidecar import (
    load_model_sidecar,
    save_model_sidecar,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)


WORKFLOW_STATE_LOCK = RLock()


class RequirementWorkflowStorageError(RuntimeError):
    pass


class RequirementWorkflowStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(
        self, *, agent_project_id: str, owner_user_id: str
    ) -> RequirementWorkflowRecord | None:
        path = self._workflow_path(agent_project_id)
        record = load_model_sidecar(
            path,
            RequirementWorkflowRecord,
            error_type=RequirementWorkflowStorageError,
            unavailable_message="Requirement workflow could not be loaded",
        )
        if record is None:
            return None
        if (
            record.agent_project_id != agent_project_id
            or record.owner_user_id != owner_user_id
        ):
            raise RequirementWorkflowStorageError(
                "Requirement workflow ownership does not match"
            )
        return record

    def save(self, record: RequirementWorkflowRecord) -> None:
        path = self._workflow_path(record.agent_project_id)
        save_model_sidecar(
            path,
            record,
            lock=WORKFLOW_STATE_LOCK,
            error_type=RequirementWorkflowStorageError,
            failure_message="Requirement workflow could not be persisted",
        )

    def _project_directory(self, agent_project_id: str) -> Path:
        return self._contained(self._root, agent_project_id)

    def _workflow_path(self, agent_project_id: str) -> Path:
        return self._contained(
            self._project_directory(agent_project_id), "workflow.json"
        )

    @staticmethod
    def _contained(directory: Path, filename: str) -> Path:
        directory = directory.resolve()
        candidate = (directory / filename).resolve()
        if candidate.parent != directory:
            raise RequirementWorkflowStorageError("Unsafe workflow storage path")
        return candidate
