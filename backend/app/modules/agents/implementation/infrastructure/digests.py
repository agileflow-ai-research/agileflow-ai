"""Deterministic hashing primitives shared by Agent 3 domains."""

import hashlib
import json
from typing import Any


def stable_json_sha256(value: Any) -> str:
    """Hash a canonical JSON representation without defining domain fields."""
    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
