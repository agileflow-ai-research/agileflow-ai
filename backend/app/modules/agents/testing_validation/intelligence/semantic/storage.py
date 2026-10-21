import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.common.id_generator import validate_id

from .schemas import TestingSemanticManifest


SOURCE_ID_PATTERN = re.compile(r"^A4SRC-[0-9a-f]{32}$")


class Agent4SemanticStorageError(RuntimeError):
    pass


class Agent4SemanticStorage:
    def __init__(self, root: Path):
        self._root = Path(root).resolve()

    def load(self, *, agent_project_id, owner_user_id, source_id):
        path = self._path(agent_project_id, source_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            return None
        if payload.pop("owner_user_id", None) != owner_user_id:
            raise Agent4SemanticStorageError("Agent 4 semantic identity does not match")
        try:
            result = TestingSemanticManifest.model_validate(payload)
        except ValidationError:
            return None
        if result.agent_project_id != agent_project_id or result.source_id != source_id:
            return None
        return result

    def save(self, result, *, owner_user_id):
        path = self._path(result.agent_project_id, result.source_id)
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
            raise Agent4SemanticStorageError(
                "Agent 4 semantic facts could not be persisted"
            ) from exc

    def _path(self, project_id, source_id):
        try:
            validate_id(project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4SemanticStorageError("Unsafe Agent 4 intelligence path") from exc
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise Agent4SemanticStorageError("Invalid Agent 4 source identity")
        intelligence = (self._root / project_id / "intelligence").resolve()
        path = (intelligence / f"{source_id}.semantic-facts.json").resolve()
        try:
            intelligence.relative_to(self._root)
            path.relative_to(intelligence)
        except ValueError as exc:
            raise Agent4SemanticStorageError("Unsafe Agent 4 intelligence path") from exc
        return path
