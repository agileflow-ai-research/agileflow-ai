import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.agents.implementation.inputs.extraction.schemas import (
    DOCXBlockType, DocumentExtractionResult, DocumentType,
)
from app.modules.agents.implementation.preparation import constants
from app.modules.agents.implementation.preparation.schemas import ChunkWarningCode
from .tokenizer import count_tokens, normalize_text, sentence_aware_slices


@dataclass
class DraftChunk:
    text: str
    heading_path: list[str] = field(default_factory=list)
    structure_type: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    block_start: int | None = None
    block_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    structured_path: str | None = None
    structural_warning: ChunkWarningCode | None = None


NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+[A-Z][^.!?]{0,100}$")
MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _heading(line: str) -> bool:
    value = line.strip()
    if not value or len(value) > 120 or "\n" in value:
        return False
    words = value.rstrip(":").split()
    return bool(
        NUMBERED_HEADING.match(value)
        or (value.endswith(":") and 1 <= len(words) <= 8)
        or (2 <= len(words) <= 10 and value == value.upper() and any(c.isalpha() for c in value))
    )


def _update_path(path: list[str], title: str, level: int) -> list[str]:
    return path[: level - 1] + [title.strip()]


def _paragraphs(text: str) -> list[str]:
    return [normalize_text(p) for p in re.split(r"\n\s*\n+", normalize_text(text)) if p.strip()]


def _table_text(rows: list[list[str]]) -> str:
    return "TABLE\n" + "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)


def _split_table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    groups, current = [], []
    for row in body or [header]:
        candidate = [header, *current, row] if body else [row]
        if current and count_tokens(_table_text(candidate)) > constants.MAX_CHUNK_TOKENS:
            groups.append(_table_text([header, *current]))
            current = [row]
        else:
            current.append(row)
    if current:
        groups.append(_table_text([header, *current]) if body else _table_text(current))
    return groups


def _bounded(draft: DraftChunk, warning: ChunkWarningCode) -> tuple[list[DraftChunk], list[ChunkWarningCode]]:
    if count_tokens(draft.text) <= constants.MAX_CHUNK_TOKENS:
        return [draft], []
    pieces = sentence_aware_slices(
        draft.text, constants.MAX_CHUNK_TOKENS, constants.OVERLAP_TOKENS
    )
    return [DraftChunk(**{**draft.__dict__, "text": piece, "structural_warning": warning}) for piece in pieces], [warning]


def _pack(units: list[DraftChunk]) -> tuple[list[DraftChunk], list[ChunkWarningCode]]:
    """Pack only adjacent units sharing an exact logical heading context."""
    chunks: list[DraftChunk] = []
    warnings: list[ChunkWarningCode] = []
    current: DraftChunk | None = None
    for unit in units:
        if unit.structural_warning is not None:
            warnings.append(unit.structural_warning)
        split, split_warnings = _bounded(unit, unit.structural_warning or ChunkWarningCode.OVERSIZED_SECTION_SPLIT)
        warnings.extend(split_warnings)
        for part in split:
            if (
                current is not None
                and current.heading_path == part.heading_path
                and current.structure_type == part.structure_type
                and count_tokens(current.text + "\n\n" + part.text) <= constants.TARGET_CHUNK_TOKENS
            ):
                current.text += "\n\n" + part.text
                for name in ("page_end", "block_end", "line_end"):
                    value = getattr(part, name)
                    if value is not None:
                        setattr(current, name, value)
            else:
                current = part
                chunks.append(current)
    # Merge tiny chunks only within the same section and hard maximum.
    index = 1
    while index < len(chunks):
        previous, item = chunks[index - 1], chunks[index]
        if (
            count_tokens(item.text) < constants.MIN_CHUNK_TOKENS
            and previous.heading_path == item.heading_path
            and previous.structure_type == item.structure_type
            and count_tokens(previous.text + "\n\n" + item.text) <= constants.MAX_CHUNK_TOKENS
        ):
            previous.text += "\n\n" + item.text
            previous.page_end = item.page_end or previous.page_end
            previous.block_end = item.block_end or previous.block_end
            previous.line_end = item.line_end or previous.line_end
            chunks.pop(index)
        else:
            index += 1
    return chunks, list(dict.fromkeys(warnings))


def _pdf(extraction: DocumentExtractionResult):
    units: list[DraftChunk] = []
    path: list[str] = []
    for page in extraction.content.pages:
        paragraphs = _paragraphs(page.text)
        for paragraph in paragraphs:
            lines = paragraph.splitlines()
            if lines and _heading(lines[0]):
                path = [lines[0].strip().rstrip(":")]
                remainder = normalize_text("\n".join(lines[1:]))
                if not remainder:
                    continue
                paragraph = remainder
            units.append(DraftChunk(paragraph, path.copy(), "PARAGRAPH", page_start=page.page_number, page_end=page.page_number))
    return _pack(units)


def _docx(extraction: DocumentExtractionResult):
    units: list[DraftChunk] = []
    path: list[str] = []
    for block in extraction.content.blocks:
        if block.type is DOCXBlockType.HEADING:
            path = _update_path(path, block.text or "", block.level or 1)
            continue
        if block.type is DOCXBlockType.TABLE:
            texts = _split_table(block.rows or [])
            warning = ChunkWarningCode.OVERSIZED_TABLE_SPLIT if len(texts) > 1 else None
            units.extend(DraftChunk(text, path.copy(), "TABLE", block_start=block.block_index, block_end=block.block_index, structural_warning=warning) for text in texts)
        elif normalize_text(block.text or ""):
            units.append(DraftChunk(normalize_text(block.text or ""), path.copy(), "PARAGRAPH", block_start=block.block_index, block_end=block.block_index))
    return _pack(units)


def _text_or_markdown(extraction: DocumentExtractionResult, markdown: bool):
    source = extraction.content.markdown if markdown else extraction.content.text
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    units: list[DraftChunk] = []
    path: list[str] = []
    start = 0
    buffer: list[str] = []
    in_fence = False

    def flush(end: int, structure: str = "PARAGRAPH"):
        nonlocal buffer, start
        value = normalize_text("\n".join(buffer))
        if value:
            warning = (
                ChunkWarningCode.OVERSIZED_CODE_BLOCK_SPLIT
                if structure == "CODE_BLOCK" and count_tokens(value) > constants.MAX_CHUNK_TOKENS
                else None
            )
            units.append(DraftChunk(value, path.copy(), structure, line_start=start + 1, line_end=end, structural_warning=warning))
        buffer = []

    for index, line in enumerate(lines):
        md_match = MARKDOWN_HEADING.match(line) if markdown and not in_fence else None
        if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
            if not buffer:
                start = index
            buffer.append(line)
            in_fence = not in_fence
            if not in_fence:
                flush(index + 1, "CODE_BLOCK")
            continue
        if in_fence:
            buffer.append(line)
            continue
        if md_match or (not markdown and _heading(line)):
            flush(index)
            title = (md_match.group(2) if md_match else line).strip().rstrip(":")
            level = len(md_match.group(1)) if md_match else 1
            path = _update_path(path, title, level)
            start = index + 1
            continue
        if not line.strip():
            flush(index)
            start = index + 1
        else:
            if not buffer:
                start = index
            buffer.append(line)
    flush(len(lines), "CODE_BLOCK" if in_fence else "PARAGRAPH")
    return _pack(units)


def chunk_unstructured(extraction: DocumentExtractionResult):
    if extraction.document_type is DocumentType.PDF:
        return _pdf(extraction)
    if extraction.document_type is DocumentType.DOCX:
        return _docx(extraction)
    return _text_or_markdown(extraction, extraction.document_type is DocumentType.MD)
