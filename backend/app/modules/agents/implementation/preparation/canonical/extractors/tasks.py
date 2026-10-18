import re

from ..schemas import (
    CanonicalSourceRef, CanonicalStatus, ImplementationTaskItem,
    ImplementationTasksData,
)
from .common import ExtractionOutcome, unresolved


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    tasks = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        match = re.match(r"^(?:(TASK[- ]?\d+|TODO)\s*[:.-]?\s*|[-*+]\s+)(.+)$", line, re.I)
        if not match:
            continue
        raw_id, content = match.group(1), match.group(2).strip()
        if not content:
            continue
        item_id = None
        if raw_id and raw_id.upper() != "TODO":
            item_id = f"TASK-{re.search(r'\d+', raw_id).group().zfill(3)}"
        title, separator, description = content.partition(":")
        key = (item_id or "", content.casefold())
        if key in seen:
            continue
        seen.add(key)
        tasks.append(ImplementationTaskItem(
            id=item_id, title=title.strip(),
            description=description.strip() if separator and description.strip() else None,
            source_refs=[source],
        ))
    if not tasks:
        return ExtractionOutcome(ImplementationTasksData(tasks=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_IMPLEMENTATION_TASK", source))
    return ExtractionOutcome(ImplementationTasksData(tasks=tasks), CanonicalStatus.COMPLETE, [])

