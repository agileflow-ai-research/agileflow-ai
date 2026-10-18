import re
from dataclasses import dataclass
from typing import Any

from ..schemas import CanonicalSourceRef, CanonicalStatus, UnresolvedItem


@dataclass(frozen=True)
class ExtractionOutcome:
    data: Any
    status: CanonicalStatus
    unresolved_items: list[UnresolvedItem]


def content_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        value = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", raw).strip()
        if value:
            lines.append(value)
    return lines


def unresolved(reason: str, source: CanonicalSourceRef) -> list[UnresolvedItem]:
    return [UnresolvedItem(reason=reason, source_ref=source)]


def unique(values):
    seen = set()
    result = []
    for value in values:
        key = str(value).casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result

