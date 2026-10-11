import re

from app.core.constants import APPROVED_ID_PREFIXES


ID_PATTERN = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<sequence>\d{3,})$")


def generate_id(prefix: str, sequence: int) -> str:
    """Generate an approved, deterministic AgileFlow AI identifier."""
    if prefix not in APPROVED_ID_PREFIXES:
        raise ValueError(f"Unsupported ID prefix: {prefix!r}")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("ID sequence must be a positive integer")

    return f"{prefix}-{sequence:03d}"


def validate_id(value: str, expected_prefix: str | None = None) -> str:
    """Validate an AgileFlow AI identifier and optionally require one prefix."""
    if expected_prefix is not None and expected_prefix not in APPROVED_ID_PREFIXES:
        raise ValueError(f"Unsupported expected ID prefix: {expected_prefix!r}")

    match = ID_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("ID must use the format PREFIX-001")

    prefix = match.group("prefix")
    if prefix not in APPROVED_ID_PREFIXES:
        raise ValueError(f"Unsupported ID prefix: {prefix!r}")
    if expected_prefix is not None and prefix != expected_prefix:
        raise ValueError(f"ID must use the {expected_prefix} prefix")
    if int(match.group("sequence")) < 1:
        raise ValueError("ID sequence must be positive")

    return value
