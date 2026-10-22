import json
import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import fitz
import yaml
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.common.document_extraction.schemas import (
    DOCXBlock,
    DOCXBlockType,
    DOCXContent,
    DOCXMetrics,
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    ExtractionWarningLocation,
    MarkdownContent,
    PDFContent,
    PDFMetrics,
    PDFPage,
    StructuredContent,
    StructuredMetrics,
    TextContent,
    TextMetrics,
)


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def extract_pdf(path: Path, *, max_pages: int, max_characters: int):
    pages: list[PDFPage] = []
    parts: list[str] = []
    warnings: list[ExtractionWarning] = []
    with_text = 0
    without_text = 0
    truncated = False
    with fitz.open(path) as document:
        page_count = document.page_count
        process_count = min(page_count, max_pages)
        if page_count > max_pages:
            truncated = True
            warnings.append(
                ExtractionWarning(
                    code=ExtractionWarningCode.CONTENT_TRUNCATED,
                    message=f"Only the first {max_pages} PDF pages were extracted.",
                )
            )
        remaining = max_characters
        for index in range(process_count):
            number = index + 1
            try:
                value = _normalize_text(
                    document.load_page(index).get_text("text")
                )
            except Exception:
                value = ""
                warnings.append(
                    ExtractionWarning(
                        code=ExtractionWarningCode.EXTRACTION_ERROR,
                        message=f"Page {number} could not be extracted.",
                        location=ExtractionWarningLocation(page_number=number),
                    )
                )
            if not value:
                without_text += 1
                pages.append(PDFPage(page_number=number, text=""))
                warnings.append(
                    ExtractionWarning(
                        code=ExtractionWarningCode.NO_TEXT_ON_PAGE,
                        message=f"No extractable text was found on page {number}.",
                        location=ExtractionWarningLocation(page_number=number),
                    )
                )
                continue
            separator = 2 if parts else 0
            extracted = value[: max(remaining - separator, 0)]
            if extracted:
                with_text += 1
                pages.append(PDFPage(page_number=number, text=extracted))
                parts.append(extracted)
                remaining -= len(extracted) + separator
            if len(extracted) < len(value) or remaining <= 0:
                truncated = True
                warnings.append(
                    ExtractionWarning(
                        code=ExtractionWarningCode.CONTENT_TRUNCATED,
                        message="PDF text exceeded the extraction character limit.",
                        location=ExtractionWarningLocation(page_number=number),
                    )
                )
                break
    combined = "\n\n".join(parts)
    if not combined.strip():
        status = ExtractionStatus.FAILED
        warnings.append(
            ExtractionWarning(
                code=ExtractionWarningCode.NO_EXTRACTABLE_TEXT,
                message=(
                    "No reliable textual content could be extracted from this PDF. "
                    "The document may be image-only."
                ),
            )
        )
    elif truncated or without_text or any(
        warning.code is ExtractionWarningCode.EXTRACTION_ERROR
        for warning in warnings
    ):
        status = ExtractionStatus.PARTIAL
    else:
        status = ExtractionStatus.SUCCESS
    return (
        status,
        PDFContent(pages=pages, combined_text=combined),
        PDFMetrics(
            page_count=page_count,
            processed_page_count=len(pages),
            pages_with_text=with_text,
            pages_without_text=without_text,
            extracted_character_count=len(combined),
        ),
        warnings,
    )


def _heading_level(paragraph: Paragraph) -> int | None:
    try:
        name = paragraph.style.name or ""
    except (AttributeError, KeyError):
        return None
    match = re.fullmatch(r"Heading\s+([1-9])", name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_docx(
    path: Path,
    *,
    max_characters: int,
    max_uncompressed_bytes: int,
    max_archive_entries: int,
):
    warnings: list[ExtractionWarning] = []
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > max_archive_entries or sum(
            entry.file_size for entry in entries
        ) > max_uncompressed_bytes:
            raise ValueError("DOCX expanded content exceeds the extraction safety limit")
        if any(
            entry.filename.startswith(
                ("word/media/", "word/charts/", "word/diagrams/")
            )
            for entry in entries
        ):
            warnings.append(
                ExtractionWarning(
                    code=ExtractionWarningCode.UNSUPPORTED_DOCUMENT_STRUCTURE,
                    message="Embedded images, charts, or diagrams were not interpreted.",
                )
            )

    document = Document(path)
    blocks: list[DOCXBlock] = []
    parts: list[str] = []
    headings = 0
    paragraphs = 0
    tables = 0
    remaining = max_characters
    truncated = False
    for index, child in enumerate(document.element.body.iterchildren(), 1):
        block = None
        rendered = ""
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, document)
            value = _normalize_text(paragraph.text)
            if not value:
                continue
            level = _heading_level(paragraph)
            kind = (
                DOCXBlockType.HEADING
                if level is not None
                else DOCXBlockType.PARAGRAPH
            )
            rendered = value[: max(remaining - (2 if parts else 0), 0)]
            if not rendered:
                truncated = True
                break
            block = DOCXBlock(
                block_index=index, type=kind, text=rendered, level=level
            )
            headings += level is not None
            paragraphs += level is None
            truncated = len(rendered) < len(value)
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            rows = [
                [_normalize_text(cell.text) for cell in row.cells]
                for row in table.rows
            ]
            value = "\n".join("\t".join(row) for row in rows).strip()
            if not value:
                continue
            rendered = value[: max(remaining - (2 if parts else 0), 0)]
            if not rendered:
                truncated = True
                break
            block = DOCXBlock(
                block_index=index,
                type=DOCXBlockType.TABLE,
                rows=[line.split("\t") for line in rendered.split("\n")],
            )
            tables += 1
            truncated = len(rendered) < len(value)
        if block is None:
            continue
        separator = 2 if parts else 0
        blocks.append(block)
        parts.append(rendered)
        remaining -= len(rendered) + separator
        if truncated or remaining <= 0:
            truncated = True
            warnings.append(
                ExtractionWarning(
                    code=ExtractionWarningCode.CONTENT_TRUNCATED,
                    message="DOCX content exceeded the extraction character limit.",
                    location=ExtractionWarningLocation(block_index=index),
                )
            )
            break
    combined = "\n\n".join(parts)
    if not combined.strip():
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
        DOCXContent(blocks=blocks, combined_text=combined),
        DOCXMetrics(
            block_count=len(blocks),
            paragraph_count=paragraphs,
            heading_count=headings,
            table_count=tables,
            extracted_character_count=len(combined),
        ),
        warnings,
    )


def extract_text(path: Path, *, max_characters: int, markdown: bool = False):
    text = _normalize_text(path.read_text(encoding="utf-8-sig"))
    bounded = text[:max_characters]
    truncated = len(text) > max_characters
    warnings: list[ExtractionWarning] = []
    if not bounded:
        status = ExtractionStatus.FAILED
        warnings.append(
            ExtractionWarning(
                code=ExtractionWarningCode.EMPTY_DOCUMENT,
                message="The document contains no non-whitespace text.",
            )
        )
    elif truncated:
        status = ExtractionStatus.PARTIAL
        warnings.append(
            ExtractionWarning(
                code=ExtractionWarningCode.CONTENT_TRUNCATED,
                message="Document text exceeded the extraction character limit.",
            )
        )
    else:
        status = ExtractionStatus.SUCCESS
    content = (
        MarkdownContent(markdown=bounded, combined_text=bounded)
        if markdown
        else TextContent(text=bounded, combined_text=bounded)
    )
    return (
        status,
        content,
        TextMetrics(
            extracted_character_count=len(bounded),
            line_count=len(text.splitlines()) if text else 0,
        ),
        warnings,
    )


def _root_type(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, dict):
        return "OBJECT"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, str):
        return "STRING"
    return "NUMBER"


def extract_structured(
    path: Path, *, max_characters: int, yaml_document: bool = False
):
    source = path.read_text(encoding="utf-8-sig")
    try:
        value = yaml.safe_load(source) if yaml_document else json.loads(source)
        normalized = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    except (json.JSONDecodeError, TypeError, ValueError, yaml.YAMLError) as exc:
        return (
            ExtractionStatus.FAILED,
            StructuredContent(structured_content=None, normalized_text=""),
            StructuredMetrics(root_type="NULL", extracted_character_count=0),
            [
                ExtractionWarning(
                    code=ExtractionWarningCode.INVALID_STRUCTURED_CONTENT,
                    message=(
                        "Structured document could not be safely parsed: "
                        f"{type(exc).__name__}."
                    ),
                )
            ],
        )
    bounded = normalized[:max_characters]
    truncated = len(normalized) > max_characters
    warnings: list[ExtractionWarning] = []
    empty = value is None or value == "" or value == [] or value == {}
    if empty:
        status = ExtractionStatus.FAILED
        warnings.append(
            ExtractionWarning(
                code=ExtractionWarningCode.EMPTY_DOCUMENT,
                message="The structured document contains no useful values.",
            )
        )
    elif truncated:
        status = ExtractionStatus.PARTIAL
        warnings.append(
            ExtractionWarning(
                code=ExtractionWarningCode.CONTENT_TRUNCATED,
                message=(
                    "Normalized structured content exceeded the extraction "
                    "character limit."
                ),
            )
        )
    else:
        status = ExtractionStatus.SUCCESS
    return (
        status,
        StructuredContent(
            structured_content=None if truncated else value,
            normalized_text=bounded,
        ),
        StructuredMetrics(
            root_type=_root_type(value),
            extracted_character_count=len(bounded),
        ),
        warnings,
    )
