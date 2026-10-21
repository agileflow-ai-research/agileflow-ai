import json
from pathlib import Path

from pydantic import ValidationError

from app.common.id_generator import validate_id

from .schemas import Agent4FeasibilityResult


class Agent4FeasibilityStorageError(RuntimeError):
    pass


class Agent4FeasibilityStorage:
    def __init__(self, root: Path):
        self._root = Path(root).resolve()

    def load(self, *, agent_project_id: str, owner_user_id: str):
        path = self._path(agent_project_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            return None
        if payload.pop("owner_user_id", None) != owner_user_id:
            raise Agent4FeasibilityStorageError("Agent 4 feasibility identity does not match")
        try:
            result = Agent4FeasibilityResult.model_validate(payload)
        except ValidationError:
            return None
        return result if result.agent_project_id == agent_project_id else None

    def save(self, result: Agent4FeasibilityResult, *, owner_user_id: str):
        path = self._path(result.agent_project_id)
        partial = path.with_suffix(path.suffix + ".part")
        payload = {**result.model_dump(mode="json"), "owner_user_id": owner_user_id}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            partial.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            partial.replace(path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
            raise Agent4FeasibilityStorageError(
                "Agent 4 feasibility could not be persisted"
            ) from exc

    def _path(self, agent_project_id: str):
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4FeasibilityStorageError("Unsafe Agent 4 feasibility path") from exc
        project = (self._root / agent_project_id).resolve()
        directory = (project / "context-testability").resolve()
        path = (directory / "feasibility.json").resolve()
        try:
            project.relative_to(self._root)
            path.relative_to(directory)
        except ValueError as exc:
            raise Agent4FeasibilityStorageError("Unsafe Agent 4 feasibility path") from exc
        return path
