import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.common.id_generator import validate_id
from app.modules.agents.testing_validation.preparation.extraction.schemas import (
    Agent4DocumentExtractionResult,
)


EXTRACTION_SIDECAR_SUFFIX = ".extraction.json"
SOURCE_ID_PATTERN = re.compile(r"^A4SRC-[0-9a-f]{32}$")


class Agent4ExtractionStorageError(RuntimeError):
    pass


class Agent4ExtractionStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def load(
        self, *, agent_project_id: str, owner_user_id: str, source_id: str
    ) -> Agent4DocumentExtractionResult | None:
        path = self._path(agent_project_id, source_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise Agent4ExtractionStorageError(
                "Agent 4 extraction result could not be loaded"
            ) from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if payload.get("owner_user_id") != owner_user_id:
            raise Agent4ExtractionStorageError(
                "Agent 4 extraction identity does not match"
            )
        payload.pop("owner_user_id", None)
        try:
            result = Agent4DocumentExtractionResult.model_validate(payload)
        except ValidationError:
            return None
        if (
            result.agent_project_id != agent_project_id
            or result.source_id != source_id
        ):
            return None
        return result

    def save(
        self, result: Agent4DocumentExtractionResult, *, owner_user_id: str
    ) -> None:
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
            raise Agent4ExtractionStorageError(
                "Agent 4 extraction result could not be persisted"
            ) from exc

    def _path(self, agent_project_id: str, source_id: str) -> Path:
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4ExtractionStorageError("Unsafe Agent 4 extraction path") from exc
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise Agent4ExtractionStorageError("Invalid Agent 4 source identity")
        project = (self._root / agent_project_id).resolve()
        preparation = (project / "preparation").resolve()
        candidate = (preparation / f"{source_id}{EXTRACTION_SIDECAR_SUFFIX}").resolve()
        try:
            project.relative_to(self._root)
            candidate.relative_to(preparation)
        except ValueError as exc:
            raise Agent4ExtractionStorageError("Unsafe Agent 4 extraction path") from exc
        return candidate
