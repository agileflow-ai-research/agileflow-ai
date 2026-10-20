from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from app.common.id_generator import validate_id
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_FILENAME,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4TestGenerationWorkflowRecord,
)


AGENT4_WORKFLOW_STATE_LOCK = RLock()


class Agent4WorkflowStorageError(RuntimeError):
    pass


class Agent4WorkflowStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def load(
        self, *, agent_project_id: str, owner_user_id: str
    ) -> Agent4TestGenerationWorkflowRecord | None:
        path = self._workflow_path(agent_project_id)
        try:
            record = Agent4TestGenerationWorkflowRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            return None
        except (OSError, ValidationError) as exc:
            raise Agent4WorkflowStorageError(
                "Agent 4 workflow could not be loaded"
            ) from exc
        if (
            record.agent_project_id != agent_project_id
            or record.owner_user_id != owner_user_id
        ):
            raise Agent4WorkflowStorageError(
                "Agent 4 workflow identity does not match"
            )
        return record

    def save(self, record: Agent4TestGenerationWorkflowRecord) -> None:
        path = self._workflow_path(record.agent_project_id)
        partial_path = path.with_suffix(path.suffix + ".part")
        with AGENT4_WORKFLOW_STATE_LOCK:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                partial_path.write_text(record.model_dump_json(), encoding="utf-8")
                partial_path.replace(path)
            except OSError as exc:
                try:
                    partial_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise Agent4WorkflowStorageError(
                    "Agent 4 workflow could not be persisted"
                ) from exc

    def _workflow_path(self, agent_project_id: str) -> Path:
        try:
            validate_id(agent_project_id, "AGP")
        except ValueError as exc:
            raise Agent4WorkflowStorageError("Unsafe Agent 4 workflow path") from exc
        project_directory = (self._root / agent_project_id).resolve()
        try:
            project_directory.relative_to(self._root)
        except ValueError as exc:  # pragma: no cover - ID validation is primary
            raise Agent4WorkflowStorageError("Unsafe Agent 4 workflow path") from exc
        return project_directory / AGENT4_TEST_GENERATION_WORKFLOW_FILENAME
