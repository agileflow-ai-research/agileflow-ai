"""Shared mechanics for project-scoped Pydantic JSON sidecars."""

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError


ModelT = TypeVar("ModelT", bound=BaseModel)


def project_sidecar_path(
    root: Path,
    project_id: str,
    filename: str,
    *,
    error_type: type[RuntimeError],
    unsafe_path_message: str,
) -> Path:
    """Resolve a project sidecar while enforcing containment below its root."""
    resolved_root = Path(root).resolve()
    project_directory = (resolved_root / project_id).resolve()
    try:
        project_directory.relative_to(resolved_root)
    except ValueError as exc:
        raise error_type(unsafe_path_message) from exc
    return project_directory / filename


def load_model_sidecar(
    path: Path,
    model: type[ModelT],
    *,
    error_type: type[RuntimeError],
    unavailable_message: str,
) -> ModelT | None:
    """Load and validate a sidecar, treating absence differently from corruption."""
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValidationError) as exc:
        raise error_type(unavailable_message) from exc


def save_model_sidecar(
    path: Path,
    value: BaseModel,
    *,
    lock,
    error_type: type[RuntimeError],
    failure_message: str,
) -> None:
    """Atomically replace a sidecar using the established `.part` convention."""
    partial_path = path.with_suffix(path.suffix + ".part")
    with lock:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            partial_path.write_text(value.model_dump_json(), encoding="utf-8")
            partial_path.replace(path)
        except OSError as exc:
            try:
                partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise error_type(failure_message) from exc
