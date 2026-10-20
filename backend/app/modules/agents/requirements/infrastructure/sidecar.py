"""Reusable persistence mechanics for typed Agent 1 JSON sidecars."""

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError


ModelT = TypeVar("ModelT", bound=BaseModel)


def load_model_sidecar(
    path: Path,
    model: type[ModelT],
    *,
    error_type: type[RuntimeError],
    unavailable_message: str,
) -> ModelT | None:
    """Load a typed sidecar, distinguishing absence from invalid content."""
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
    """Persist a typed sidecar atomically via the established `.part` file."""
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


def remove_sidecar(
    path: Path,
    *,
    lock,
    error_type: type[RuntimeError],
    failure_message: str,
) -> None:
    """Remove a sidecar and any abandoned partial without leaking I/O errors."""
    partial_path = path.with_suffix(path.suffix + ".part")
    with lock:
        try:
            path.unlink(missing_ok=True)
            partial_path.unlink(missing_ok=True)
        except OSError as exc:
            raise error_type(failure_message) from exc
