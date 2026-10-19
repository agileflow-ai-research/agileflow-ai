from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from .schemas import ProjectConsolidationRecord, TrustedProjectSpecification


class ConsolidationStorageError(RuntimeError):
    pass


class ConsolidationStorage:
    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load_state(self, project_id: str, owner_id: str):
        return self._load(
            self._path(project_id, "project-consolidation.json"),
            ProjectConsolidationRecord,
            project_id,
            owner_id,
        )

    def load_final(self, project_id: str, owner_id: str):
        value = self._load(
            self._path(project_id, "trusted-project-specification.json"),
            TrustedProjectSpecification,
            project_id,
            owner_id,
        )
        return value

    def save_state(self, value: ProjectConsolidationRecord) -> None:
        self._save(
            self._path(value.agent_project_id, "project-consolidation.json"),
            value,
        )

    def save_final(self, value: TrustedProjectSpecification) -> None:
        self._save(
            self._path(
                value.agent_project_id, "trusted-project-specification.json"
            ),
            value,
        )

    def _path(self, project_id: str, name: str) -> Path:
        root = self._root.resolve()
        directory = (root / project_id).resolve()
        try:
            directory.relative_to(root)
        except ValueError as exc:
            raise ConsolidationStorageError(
                "Unsafe project consolidation storage path"
            ) from exc
        return directory / name

    @staticmethod
    def _load(path, model, project_id, owner_id):
        try:
            value = model.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValidationError) as exc:
            raise ConsolidationStorageError(
                "Project consolidation state is unavailable"
            ) from exc
        if value.agent_project_id != project_id:
            raise ConsolidationStorageError(
                "Project consolidation state identity is invalid"
            )
        if isinstance(value, ProjectConsolidationRecord):
            if value.owner_user_id != owner_id:
                raise ConsolidationStorageError(
                    "Project consolidation state identity is invalid"
                )
        return value

    def _save(self, path: Path, value) -> None:
        partial = path.with_suffix(path.suffix + ".part")
        with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                partial.write_text(value.model_dump_json(), encoding="utf-8")
                partial.replace(path)
            except OSError as exc:
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
                raise ConsolidationStorageError(
                    "Project consolidation state could not be stored"
                ) from exc
