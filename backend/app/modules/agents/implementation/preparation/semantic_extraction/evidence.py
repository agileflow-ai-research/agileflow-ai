from dataclasses import dataclass

from . import constants
from .schemas import EvidenceSpan


@dataclass(frozen=True)
class EvidenceValidation:
    valid: bool
    evidence: EvidenceSpan | None
    reason: str | None = None


def normalize_source_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def validate_evidence(
    evidence: EvidenceSpan, *, trusted_chunk_id: str, trusted_source_text: str
) -> EvidenceValidation:
    source = normalize_source_text(trusted_source_text)
    quote = normalize_source_text(evidence.quote).strip()
    if not quote:
        return EvidenceValidation(False, None, "EMPTY_EVIDENCE_QUOTE")
    if len(quote) > constants.MAX_EVIDENCE_QUOTE_CHARACTERS:
        return EvidenceValidation(False, None, "EVIDENCE_QUOTE_TOO_LARGE")
    if evidence.chunk_id != trusted_chunk_id:
        return EvidenceValidation(False, None, "WRONG_EVIDENCE_CHUNK")
    if evidence.start_char is not None:
        start, end = evidence.start_char, evidence.end_char
        if end is None or end > len(source) or source[start:end] != quote:
            return EvidenceValidation(False, None, "EVIDENCE_OFFSET_MISMATCH")
        return EvidenceValidation(True, EvidenceSpan(
            chunk_id=evidence.chunk_id, quote=quote,
            start_char=start, end_char=end,
        ))
    locations, cursor = [], 0
    while True:
        position = source.find(quote, cursor)
        if position < 0:
            break
        locations.append(position)
        cursor = position + 1
    if not locations:
        return EvidenceValidation(False, None, "EVIDENCE_QUOTE_NOT_FOUND")
    if len(locations) > 1:
        return EvidenceValidation(False, None, "AMBIGUOUS_EVIDENCE_QUOTE")
    start = locations[0]
    return EvidenceValidation(True, EvidenceSpan(
        chunk_id=evidence.chunk_id, quote=quote,
        start_char=start, end_char=start + len(quote),
    ))
