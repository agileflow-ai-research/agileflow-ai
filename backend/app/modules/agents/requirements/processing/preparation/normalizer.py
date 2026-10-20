import re
from dataclasses import dataclass


_EXCESSIVE_BLANK_LINES = re.compile(r"\n(?:[ \t]*\n){2,}")


def normalize_text(value: str) -> str:
    """Apply conservative deterministic whitespace normalization only."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = _EXCESSIVE_BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()


@dataclass(frozen=True)
class NormalizationUnit:
    text: str
    parent_start_offset: int | None = None
    parent_end_offset: int | None = None
    page_numbers: tuple[int, ...] = ()
    document_blocks: tuple[tuple[int, str], ...] = ()
    media_segments: tuple[tuple[int, float, float, int | None, int | None], ...] = ()


def normalize_units(
    units: list[NormalizationUnit], *, separator: str
) -> tuple[str, list[tuple[NormalizationUnit, str, int, int]]]:
    combined = ""
    mapped: list[tuple[NormalizationUnit, str, int, int]] = []
    for unit in units:
        normalized = normalize_text(unit.text)
        if not normalized:
            mapped.append((unit, normalized, len(combined), len(combined)))
            continue
        if combined:
            combined += separator
        start = len(combined)
        combined += normalized
        mapped.append((unit, normalized, start, len(combined)))
    return combined, mapped
