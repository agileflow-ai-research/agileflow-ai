"""
Disk persistence for the N4.4 context decision.

Path: <root>/<agent_project_id>/context-testability/context-decision.json
This is one file per project, not per source. It is written only after TR1, TB1,
and FB1 are all current, and it holds the consolidated CD1 decision. Writes are
atomic (.part then replace), so a failed write never leaves a partial trusted decision.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.common.id_generator import validate_id

from .schemas import Agent4ContextDecisionResult


class Agent4ContextDecisionStorageError(RuntimeError):
    """Raised for owner mismatch, unsafe paths, or failed persistence."""
    pass


class Agent4ContextDecisionStorage:
    """Reads and writes the single CD1 decision file for a project."""

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
            raise Agent4ContextDecisionStorageError("Agent 4 context decision identity does not match")
        try:
            result = Agent4ContextDecisionResult.model_validate(payload)
        except ValidationError:
            return None
        return result if result.agent_project_id == agent_project_id else None

    def save(self, result: Agent4ContextDecisionResult, *, owner_user_id: str):
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
            raise Agent4ContextDecisionStorageError(
                "Agent 4 context decision could not be persisted"
            ) from exc

    def _path(self, agent_project_id: str):
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4ContextDecisionStorageError("Unsafe Agent 4 context decision path") from exc
        project = (self._root / agent_project_id).resolve()
        directory = (project / "context-testability").resolve()
        path = (directory / "context-decision.json").resolve()
        try:
            project.relative_to(self._root)
            path.relative_to(directory)
        except ValueError as exc:
            raise Agent4ContextDecisionStorageError("Unsafe Agent 4 context decision path") from exc
        return path
