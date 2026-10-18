import json
import re

import yaml

from ..schemas import CanonicalSourceRef, CanonicalStatus, TechnologyStackData
from .common import ExtractionOutcome, unique, unresolved


_KEYS = {
    "frontend": "frontend", "front-end": "frontend", "styling": "styling", "css": "styling",
    "backend": "backend", "back-end": "backend", "database": "database", "db": "database",
    "language": "languages", "languages": "languages", "api style": "api_styles",
    "api_style": "api_styles", "api": "api_styles", "other": "other",
}


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    buckets = {value: [] for value in set(_KEYS.values())}
    buckets.setdefault("other", [])
    try:
        structured = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            structured = yaml.safe_load(text)
        except (TypeError, ValueError, yaml.YAMLError):
            structured = None
    if isinstance(structured, dict):
        for key, value in structured.items():
            target = _KEYS.get(str(key).casefold())
            if target:
                buckets[target].extend(_values(value))
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z _-]+)\s*[:=]\s*(.+)$", line)
        if not match:
            continue
        target = _KEYS.get(match.group(1).strip().casefold())
        if target:
            buckets[target].extend(_values(match.group(2)))
    buckets = {key: unique(value.strip() for value in values if value.strip())
               for key, values in buckets.items()}
    data = TechnologyStackData(
        frontend=buckets.get("frontend", []), styling=buckets.get("styling", []),
        backend=buckets.get("backend", []), database=buckets.get("database", []),
        languages=buckets.get("languages", []), api_styles=buckets.get("api_styles", []),
        other=buckets.get("other", []), source_refs=[source],
    )
    if not any(buckets.values()):
        return ExtractionOutcome(data, CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_TECHNOLOGY_DECLARATION", source))
    return ExtractionOutcome(data, CanonicalStatus.COMPLETE, [])


def _values(value):
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items()]
    return [item.strip() for item in re.split(r"[,|]", str(value))]

