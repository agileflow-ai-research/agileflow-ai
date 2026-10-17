"""
Content extraction pipeline for Agent 1 requirement sources.

Supported extraction:
  DOCUMENT  (.pdf)   — pypdf text layer
  DOCUMENT  (.docx)  — python-docx paragraph text
  DOCUMENT  (.txt)   — raw UTF-8 read

Honest non-support:
  AUDIO / VIDEO — raises ExtractionUnsupportedError; callers must produce a
                  WARNING and exclude the source from the engine context rather
                  than fail the whole run.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable

from app.modules.agent1.schemas import RequirementSourceType


# ---------------------------------------------------------------------------
# Public error types
# ---------------------------------------------------------------------------


class ExtractionError(RuntimeError):
    """Text could not be extracted from the source file."""


class ExtractionUnsupportedError(ExtractionError):
    """The source type / format has no extraction implementation yet."""


class ExtractionEmptyError(ExtractionError):
    """Extraction succeeded mechanically but yielded no usable text."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_pdf(data: bytes) -> str:
    try:
        import pypdf  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise ExtractionUnsupportedError(
            "pypdf is not installed; PDF extraction is unavailable"
        ) from exc

    reader = pypdf.PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def _extract_docx(data: bytes) -> str:
    try:
        import docx  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise ExtractionUnsupportedError(
            "python-docx is not installed; DOCX extraction is unavailable"
        ) from exc

    from docx.table import Table  # noqa: PLC0415
    from docx.text.paragraph import Paragraph  # noqa: PLC0415

    doc = docx.Document(io.BytesIO(data))
    parts: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            text = Paragraph(child, doc).text.strip()
            if text:
                parts.append(text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append("\t".join(cells))
    return "\n".join(parts)


def _extract_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Could not decode text file with any supported encoding")


_DOCUMENT_EXTRACTORS: dict[str, Callable[[bytes], str]] = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".txt": _extract_txt,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


MIN_EXTRACTED_CHARS = 10


def extract_text(
    *,
    source_type: RequirementSourceType,
    file_path: str | Path,
) -> str:
    """
    Extract plain text from *file_path* for the given *source_type*.

    Returns the extracted text (may contain whitespace; callers normalize).

    Raises:
        ExtractionUnsupportedError: AUDIO / VIDEO or unknown extension.
        ExtractionEmptyError: File parsed but yielded no usable text.
        ExtractionError: Any other extraction failure.
    """
    if source_type in (RequirementSourceType.AUDIO, RequirementSourceType.VIDEO):
        raise ExtractionUnsupportedError(
            f"{source_type.value} transcription is not yet supported; "
            "upload a DOCUMENT source or enter text manually."
        )

    path = Path(file_path)
    ext = path.suffix.lower()
    extractor = _DOCUMENT_EXTRACTORS.get(ext)
    if extractor is None:
        raise ExtractionUnsupportedError(
            f"No extractor is available for extension '{ext}'"
        )

    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ExtractionError(
            f"Could not read source file at '{file_path}': {exc}"
        ) from exc

    try:
        text = extractor(data)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(
            f"Extraction failed for '{path.name}': {exc}"
        ) from exc

    if len(text.strip()) < MIN_EXTRACTED_CHARS:
        raise ExtractionEmptyError(
            f"Source '{path.name}' yielded no readable text after extraction"
        )

    return text
