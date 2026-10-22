"""Deterministic digest primitives for Agent 1 persisted identities."""

import hashlib
import json
from typing import Any


def stable_json_sha256(value: Any) -> str:
    """Hash Agent 1's existing canonical JSON representation exactly."""
    canonical = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
