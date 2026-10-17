import re
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

from app.modules.agents.implementation.extraction import constants
from app.modules.agents.implementation.extraction.schemas import (
    DOCXBlock,
    DOCXBlockType,
    DOCXContent,
    DOCXMetrics,
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    ExtractionWarningLocation,
)


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _heading_level(paragraph: Paragraph) -> int | None:
    try:
        name = paragraph.style.name or ""
    except (AttributeError, KeyError):
        return None
    match = re.fullmatch(r"Heading\s+([1-9])", name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_docx(path: Path):
    warnings: list[ExtractionWarning] = []
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if (
            len(entries) > constants.MAX_DOCX_ARCHIVE_ENTRIES
            or sum(entry.file_size for entry in entries)
            > constants.MAX_DOCX_UNCOMPRESSED_BYTES
        ):
            raise ValueError("DOCX expanded content exceeds the extraction safety limit")
        names = {entry.filename for entry in entries}
        if any(
            name.startswith(("word/media/", "word/charts/", "word/diagrams/"))
            for name in names
        ):
            warnings.append(
                ExtractionWarning(
                    code=ExtractionWarningCode.UNSUPPORTED_DOCUMENT_STRUCTURE,
                    message=(
                        "Embedded images, charts, or diagrams were not interpreted."
                    ),
                )
            )

    document = Document(path)
    blocks: list[DOCXBlock] = []
    combined_parts: list[str] = []
    headings = 0
    paragraphs = 0
    tables = 0
    remaining = constants.MAX_EXTRACTED_CHARACTERS
    truncated = False

    for block_index, child in enumerate(document.element.body.iterchildren(), 1):
        block = None
        rendered = ""
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, document)
            text = _normalize_text(paragraph.text)
            if not text:
                continue
            level = _heading_level(paragraph)
            block_type = (
                DOCXBlockType.HEADING if level is not None else DOCXBlockType.PARAGRAPH
            )
            separator_size = 2 if combined_parts else 0
            available = max(remaining - separator_size, 0)
            rendered = text[:available]
            if not rendered:
                truncated = True
                break
            block = DOCXBlock(
                block_index=block_index,
                type=block_type,
                text=rendered,
                level=level,
            )
            if level is not None:
                headings += 1
            else:
                paragraphs += 1
            if len(rendered) < len(text):
                truncated = True
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            rows = [
                [_normalize_text(cell.text) for cell in row.cells]
                for row in table.rows
            ]
            source_rendered = "\n".join("\t".join(row) for row in rows).strip()
            if not source_rendered:
                continue
            separator_size = 2 if combined_parts else 0
            available = max(remaining - separator_size, 0)
            rendered = source_rendered[:available]
            if not rendered:
                truncated = True
                break
            bounded_rows = [line.split("\t") for line in rendered.split("\n")]
            block = DOCXBlock(
                block_index=block_index,
                type=DOCXBlockType.TABLE,
                rows=bounded_rows,
            )
            tables += 1
            if len(rendered) < len(source_rendered):
                truncated = True
        if block is None:
            continue
        separator_size = 2 if combined_parts else 0
        blocks.append(block)
        combined_parts.append(rendered)
        remaining -= len(rendered) + separator_size
        if truncated or remaining <= 0:
            truncated = True
            warnings.append(
                ExtractionWarning(
                    code=ExtractionWarningCode.CONTENT_TRUNCATED,
                    message="DOCX content exceeded the extraction character limit.",
                    location=ExtractionWarningLocation(block_index=block_index),
                )
            )
            break

    combined_text = "\n\n".join(combined_parts)
    if not combined_text.strip():
        status = ExtractionStatus.FAILED
        warnings.append(
            ExtractionWarning(
                code=ExtractionWarningCode.EMPTY_DOCUMENT,
                message="No useful paragraphs, headings, or tables were found.",
            )
        )
    elif truncated or warnings:
        status = ExtractionStatus.PARTIAL
    else:
        status = ExtractionStatus.SUCCESS
    return (
        status,
        DOCXContent(blocks=blocks, combined_text=combined_text),
        DOCXMetrics(
            block_count=len(blocks),
            paragraph_count=paragraphs,
            heading_count=headings,
            table_count=tables,
            extracted_character_count=len(combined_text),
        ),
        warnings,
    )
