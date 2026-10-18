import re

from ..schemas import ApiEndpointItem, ApiSpecificationData, CanonicalSourceRef, CanonicalStatus
from .common import ExtractionOutcome, unique, unresolved


_ENDPOINT = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[^\s,;)}\]]+)", re.I)


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    matches = list(_ENDPOINT.finditer(text))
    if not matches:
        return ExtractionOutcome(ApiSpecificationData(endpoints=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_API_ENDPOINT", source))
    statuses = unique(int(value) for value in re.findall(
        r"\b(?:HTTP|status(?:\s+code)?|returns?|responds?\s+with)\s*[:=]?\s*([1-5]\d{2})\b",
        text, re.I,
    ))
    fields = []
    field_match = re.search(r"\brequest\s+fields?\s*[:=]\s*([^\n]+)", text, re.I)
    if field_match:
        fields = unique(value.strip(" `\"'") for value in re.split(r"[,|]", field_match.group(1)) if value.strip())
    endpoints = []
    seen = set()
    for match in matches:
        method, path = match.group(1).upper(), match.group(2).rstrip(".")
        key = (method, path, source.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        line_end = text.find("\n", match.end())
        tail = text[match.end(): line_end if line_end >= 0 else len(text)].strip(" :-")
        endpoints.append(ApiEndpointItem(
            method=method, path=path, description=tail or None,
            request_fields=fields, response_statuses=statuses,
            source_refs=[source],
        ))
    missing = []
    if not fields:
        missing.extend(unresolved("API_REQUEST_STRUCTURE_NOT_EXPLICIT", source))
    if not statuses:
        missing.extend(unresolved("API_RESPONSE_STATUS_NOT_EXPLICIT", source))
    return ExtractionOutcome(
        ApiSpecificationData(endpoints=endpoints),
        CanonicalStatus.COMPLETE if not missing else CanonicalStatus.PARTIAL,
        missing,
    )

