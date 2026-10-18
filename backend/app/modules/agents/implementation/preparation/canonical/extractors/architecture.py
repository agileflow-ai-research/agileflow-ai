import re

from ..schemas import (
    ArchitectureComponent, ArchitectureRelationship, ArchitectureStatement,
    CanonicalSourceRef, CanonicalStatus, SystemArchitectureData,
)
from .common import ExtractionOutcome, content_lines, unresolved


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    components, relationships, raw = [], [], []
    seen_components = set()
    for line in content_lines(text):
        if "->" in line or "→" in line:
            parts = [part.strip() for part in re.split(r"\s*(?:->|→)\s*", line) if part.strip()]
            for part in parts:
                key = part.casefold()
                if key not in seen_components:
                    seen_components.add(key)
                    components.append(ArchitectureComponent(name=part, source_refs=[source]))
            for left, right in zip(parts, parts[1:]):
                relationships.append(ArchitectureRelationship(
                    **{"from": left, "to": right, "source_refs": [source]}
                ))
            continue
        component = re.match(r"^(?:Component|Service|Layer)\s*[:=-]\s*(.+)$", line, re.I)
        if component:
            name = component.group(1).strip()
            if name.casefold() not in seen_components:
                seen_components.add(name.casefold())
                components.append(ArchitectureComponent(name=name, source_refs=[source]))
        else:
            raw.append(ArchitectureStatement(statement=line, source_refs=[source]))
    data = SystemArchitectureData(
        components=components, relationships=relationships,
        raw_architecture_statements=raw,
    )
    if not components and not relationships:
        if raw:
            return ExtractionOutcome(data, CanonicalStatus.PARTIAL,
                                     unresolved("ARCHITECTURE_COMPONENTS_NOT_EXPLICIT", source))
        return ExtractionOutcome(data, CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_ARCHITECTURE_STRUCTURE", source))
    return ExtractionOutcome(data, CanonicalStatus.COMPLETE, [])

