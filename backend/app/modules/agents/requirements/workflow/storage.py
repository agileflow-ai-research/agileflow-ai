from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from app.modules.agents.requirements.workflow.schemas import RequirementWorkflowRecord


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
        if not path.exists():
            return None
        try:
            record = RequirementWorkflowRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            if (
                record.agent_project_id != agent_project_id
                or record.owner_user_id != owner_user_id
            ):
                raise RequirementWorkflowStorageError(
                    "Requirement workflow ownership does not match"
                )
            return record
        except RequirementWorkflowStorageError:
            raise
        except (OSError, ValidationError) as exc:
            raise RequirementWorkflowStorageError(
                "Requirement workflow could not be loaded"
            ) from exc

    def save(self, record: RequirementWorkflowRecord) -> None:
        project_directory = self._project_directory(record.agent_project_id)
        path = self._workflow_path(record.agent_project_id)
        partial_path = self._contained(project_directory, "workflow.json.part")
        try:
            project_directory.mkdir(parents=True, exist_ok=True)
            payload = record.model_dump_json()
            with WORKFLOW_STATE_LOCK:
                partial_path.write_text(payload, encoding="utf-8")
                partial_path.replace(path)
        except OSError as exc:
            partial_path.unlink(missing_ok=True)
            raise RequirementWorkflowStorageError(
                "Requirement workflow could not be persisted"
            ) from exc

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
