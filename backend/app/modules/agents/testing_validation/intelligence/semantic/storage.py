"""
Disk persistence for the N3 semantic-fact manifest.

Path: <root>/<agent_project_id>/intelligence/<source_id>.semantic-facts.json
Same contract as the other intelligence stores: owner_user_id is checked on
load, writes go through a .part file and an atomic replace, and path IDs are
validated before use.
"""

import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.common.id_generator import validate_id

from .schemas import TestingSemanticManifest, TestingSemanticResult


SOURCE_ID_PATTERN = re.compile(r"^A4SRC-[0-9a-f]{32}$")


class Agent4SemanticStorageError(RuntimeError):
    """Raised for owner mismatch, unsafe paths, or failed persistence."""
    pass


class Agent4SemanticStorage:
    """Reads and writes semantic-fact manifests under the Agent 4 storage root."""

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

    def load_checkpoint(
        self, *, agent_project_id, owner_user_id, source_id,
        chunk_set_fingerprint, hybrid_manifest_fingerprint,
        effective_manifest_fingerprint,
    ):
        path = self._checkpoint_path(agent_project_id, source_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []
        if (
            payload.get("owner_user_id") != owner_user_id
            or payload.get("agent_project_id") != agent_project_id
            or payload.get("source_id") != source_id
            or payload.get("chunk_set_fingerprint") != chunk_set_fingerprint
            or payload.get("hybrid_manifest_fingerprint") != hybrid_manifest_fingerprint
            or payload.get("effective_manifest_fingerprint")
            != effective_manifest_fingerprint
        ):
            return []
        try:
            return [TestingSemanticResult.model_validate(item)
                    for item in payload.get("results", [])]
        except ValidationError:
            return []

    def save_checkpoint(
        self, *, agent_project_id, owner_user_id, source_id,
        chunk_set_fingerprint, hybrid_manifest_fingerprint,
        effective_manifest_fingerprint, results,
    ):
        path = self._checkpoint_path(agent_project_id, source_id)
        partial = path.with_suffix(path.suffix + ".part")
        payload = {
            "owner_user_id": owner_user_id,
            "agent_project_id": agent_project_id,
            "source_id": source_id,
            "chunk_set_fingerprint": chunk_set_fingerprint,
            "hybrid_manifest_fingerprint": hybrid_manifest_fingerprint,
            "effective_manifest_fingerprint": effective_manifest_fingerprint,
            "results": [item.model_dump(mode="json") for item in results],
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
            raise Agent4SemanticStorageError(
                "Agent 4 semantic checkpoint could not be persisted"
            ) from exc

    def clear_checkpoint(self, *, agent_project_id, source_id):
        try:
            self._checkpoint_path(agent_project_id, source_id).unlink(missing_ok=True)
        except OSError as exc:
            raise Agent4SemanticStorageError(
                "Agent 4 semantic checkpoint could not be cleared"
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

    def _checkpoint_path(self, project_id, source_id):
        return self._path(project_id, source_id).with_name(
            f"{source_id}.semantic-facts.checkpoint.json"
        )
