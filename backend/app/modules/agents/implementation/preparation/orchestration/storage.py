from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from .schemas import ProjectPreparationRecord


class ProjectPreparationStorageError(RuntimeError):
    pass


class ProjectPreparationStorage:
    """Atomic project-scoped orchestration state beside Agent 3 inputs."""

    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(
        self, *, agent_project_id: str, owner_user_id: str
    ) -> ProjectPreparationRecord | None:
        state_path, _ = self._paths(agent_project_id)
        try:
            record = ProjectPreparationRecord.model_validate_json(
                state_path.read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            return None
        except (OSError, ValidationError) as exc:
            raise ProjectPreparationStorageError(
                "Project preparation state is unavailable"
            ) from exc
        if (
            record.agent_project_id != agent_project_id
            or record.owner_user_id != owner_user_id
        ):
            raise ProjectPreparationStorageError(
                "Project preparation state identity is invalid"
            )
        return record

    def save(self, record: ProjectPreparationRecord) -> None:
        state_path, partial_path = self._paths(record.agent_project_id)
        with self._lock:
            try:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                partial_path.write_text(
                    record.model_dump_json(), encoding="utf-8"
                )
                partial_path.replace(state_path)
            except OSError as exc:
                try:
                    partial_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise ProjectPreparationStorageError(
                    "Project preparation state could not be stored"
                ) from exc

    def _paths(self, agent_project_id: str) -> tuple[Path, Path]:
        root = self._root.resolve()
        project_directory = (root / agent_project_id).resolve()
        try:
            project_directory.relative_to(root)
        except ValueError as exc:
            raise ProjectPreparationStorageError(
                "Unsafe project preparation storage path"
            ) from exc
        return (
            project_directory / "preparation.json",
            project_directory / "preparation.json.part",
        )
