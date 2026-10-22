import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.common.id_generator import validate_id
from app.modules.agents.testing_validation.preparation.normalization.schemas import (
    NormalizedTestingArtifact,
)


NORMALIZED_SIDECAR_SUFFIX = ".normalized.json"
SOURCE_ID_PATTERN = re.compile(r"^A4SRC-[0-9a-f]{32}$")


class Agent4NormalizationStorageError(RuntimeError):
    pass


class Agent4NormalizationStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def load(
        self, *, agent_project_id: str, owner_user_id: str, source_id: str
    ) -> NormalizedTestingArtifact | None:
        path = self._path(agent_project_id, source_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise Agent4NormalizationStorageError(
                "Agent 4 normalized artifact could not be loaded"
            ) from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if payload.get("owner_user_id") != owner_user_id:
            raise Agent4NormalizationStorageError(
                "Agent 4 normalized artifact identity does not match"
            )
        payload.pop("owner_user_id", None)
        try:
            artifact = NormalizedTestingArtifact.model_validate(payload)
        except ValidationError:
            return None
        if (
            artifact.agent_project_id != agent_project_id
            or artifact.source_id != source_id
        ):
            return None
        return artifact

    def save(
        self, artifact: NormalizedTestingArtifact, *, owner_user_id: str
    ) -> None:
        path = self._path(artifact.agent_project_id, artifact.source_id)
        partial = path.with_suffix(path.suffix + ".part")
        payload = {
            **artifact.model_dump(mode="json"),
            "owner_user_id": owner_user_id,
        }
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
            raise Agent4NormalizationStorageError(
                "Agent 4 normalized artifact could not be persisted"
            ) from exc

    def _path(self, agent_project_id: str, source_id: str) -> Path:
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4NormalizationStorageError(
                "Unsafe Agent 4 normalized artifact path"
            ) from exc
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise Agent4NormalizationStorageError(
                "Invalid Agent 4 source identity"
            )
        project = (self._root / agent_project_id).resolve()
        preparation = (project / "preparation").resolve()
        candidate = (
            preparation / f"{source_id}{NORMALIZED_SIDECAR_SUFFIX}"
        ).resolve()
        try:
            project.relative_to(self._root)
            candidate.relative_to(preparation)
        except ValueError as exc:
            raise Agent4NormalizationStorageError(
                "Unsafe Agent 4 normalized artifact path"
            ) from exc
        return candidate
