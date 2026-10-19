from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from .schemas import TrustedReadinessSnapshot


class TrustedReadinessStorageError(RuntimeError):
    pass


class TrustedReadinessStorage:
    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(self, project_id: str) -> TrustedReadinessSnapshot | None:
        path = self._path(project_id)
        try:
            value = TrustedReadinessSnapshot.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            return None
        except (OSError, ValidationError) as exc:
            raise TrustedReadinessStorageError(
                "Trusted readiness state is unavailable"
            ) from exc
        if value.agent_project_id != project_id:
            raise TrustedReadinessStorageError(
                "Trusted readiness state identity is invalid"
            )
        return value

    def save(self, value: TrustedReadinessSnapshot) -> None:
        path = self._path(value.agent_project_id)
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
                raise TrustedReadinessStorageError(
                    "Trusted readiness state could not be stored"
                ) from exc

    def _path(self, project_id: str) -> Path:
        root = self._root.resolve()
        directory = (root / project_id).resolve()
        try:
            directory.relative_to(root)
        except ValueError as exc:
            raise TrustedReadinessStorageError(
                "Unsafe trusted readiness storage path"
            ) from exc
        return directory / "implementation-readiness.json"
