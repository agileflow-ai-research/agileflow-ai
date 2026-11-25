import re
from pathlib import Path, PurePosixPath, PureWindowsPath


_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class UnsafeOutputPathError(ValueError):
    """Raised before an untrusted output path can reach the filesystem."""


def validate_relative_output_path(value: str) -> str:
    """Return a canonical safe relative path without touching the filesystem."""
    if not isinstance(value, str):
        raise UnsafeOutputPathError("Output path must be a string")
    if not value or value != value.strip() or len(value) > 512:
        raise UnsafeOutputPathError("Output path is invalid")
    if _CONTROL_CHARACTERS.search(value):
        raise UnsafeOutputPathError("Output path contains unsupported characters")
    if "\\" in value or "//" in value:
        raise UnsafeOutputPathError("Output path must use canonical '/' separators")

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise UnsafeOutputPathError("Output path must be relative")
    if value in {".", ".."} or any(part in {"", ".", ".."} for part in value.split("/")):
        raise UnsafeOutputPathError("Output path traversal is not allowed")
    if posix_path.as_posix() != value:
        raise UnsafeOutputPathError("Output path must be canonical")

    for part in posix_path.parts:
        if len(part) > 255 or part.endswith((" ", ".")) or ":" in part:
            raise UnsafeOutputPathError("Output path contains an unsafe component")
        if part.split(".", maxsplit=1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise UnsafeOutputPathError("Output path contains a reserved component")
    return value


def resolve_workspace_output_path(
    workspace_root: Path,
    relative_output_path: str,
) -> Path:
    """Resolve a validated path below a server-selected workspace root.

    This function performs no directory creation or file writes. Future writers
    must also reject symlink changes immediately before opening a destination.
    """
    if not workspace_root.is_absolute():
        raise ValueError("Workspace root must be server-controlled and absolute")
    relative = validate_relative_output_path(relative_output_path)
    root = workspace_root.resolve(strict=False)
    candidate = (root / Path(*PurePosixPath(relative).parts)).resolve(strict=False)
    if not candidate.is_relative_to(root):
        raise UnsafeOutputPathError("Output path escapes the workspace")
    return candidate
