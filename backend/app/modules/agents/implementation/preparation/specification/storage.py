from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from .schemas import ProjectSpecificationRecord


class ProjectSpecificationStorageError(RuntimeError):
    pass


class ProjectSpecificationStorage:
    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(self, agent_project_id: str, owner_user_id: str):
        path, _ = self._paths(agent_project_id)
        try:
            record = ProjectSpecificationRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            return None
        except (OSError, ValidationError) as exc:
            raise ProjectSpecificationStorageError(
                "Project specification state is unavailable"
            ) from exc
        if (
            record.agent_project_id != agent_project_id
            or record.owner_user_id != owner_user_id
        ):
            raise ProjectSpecificationStorageError(
                "Project specification state identity is invalid"
            )
        return record

    def save(self, record: ProjectSpecificationRecord) -> None:
        path, partial = self._paths(record.agent_project_id)
        with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                partial.write_text(record.model_dump_json(), encoding="utf-8")
                partial.replace(path)
            except OSError as exc:
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
                raise ProjectSpecificationStorageError(
                    "Project specification state could not be stored"
                ) from exc

    def _paths(self, agent_project_id: str):
        root = self._root.resolve()
        directory = (root / agent_project_id).resolve()
        try:
            directory.relative_to(root)
        except ValueError as exc:
            raise ProjectSpecificationStorageError(
                "Unsafe project specification storage path"
            ) from exc
        return directory / "specification.json", directory / "specification.json.part"
