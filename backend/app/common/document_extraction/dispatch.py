"""Format dispatch and failure outcomes for the shared extractors.

Callers that need to keep control of which extractor function runs (for example to
count or patch calls in tests) should dispatch to the format functions directly.
"""

from pathlib import Path

from app.common.document_extraction.constants import DEFAULT_LIMITS, ExtractionLimits
from app.common.document_extraction.docx_extractor import extract_docx
from app.common.document_extraction.pdf_extractor import extract_pdf
from app.common.document_extraction.schemas import (
    DOCXContent,
    DOCXMetrics,
    DocumentType,
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    MarkdownContent,
    PDFContent,
    PDFMetrics,
    StructuredContent,
    StructuredMetrics,
    TextContent,
    TextMetrics,
)
from app.common.document_extraction.structured_extractors import extract_structured, extract_text

DOCUMENT_TYPES = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".txt": DocumentType.TXT,
    ".md": DocumentType.MD,
    ".json": DocumentType.JSON,
    ".yaml": DocumentType.YAML,
    ".yml": DocumentType.YAML,
}


def document_type_for_extension(extension: str) -> DocumentType | None:
    return DOCUMENT_TYPES.get(extension)


def extract_document(path: Path, document_type: DocumentType, *, limits: ExtractionLimits = DEFAULT_LIMITS):
    """Run the extractor for one document type. Parser errors propagate to the caller."""
    if document_type is DocumentType.PDF:
        return extract_pdf(path, limits=limits)
    if document_type is DocumentType.DOCX:
        return extract_docx(path, limits=limits)
    if document_type is DocumentType.TXT:
        return extract_text(path, limits=limits)
    if document_type is DocumentType.MD:
        return extract_text(path, markdown=True, limits=limits)
    if document_type is DocumentType.JSON:
        return extract_structured(path, limits=limits)
    return extract_structured(path, yaml_document=True, limits=limits)


def extract_document_safely(path: Path, document_type: DocumentType, *, limits: ExtractionLimits = DEFAULT_LIMITS):
    """Like extract_document, but a parser failure becomes a FAILED outcome, never an exception."""
    try:
        return extract_document(path, document_type, limits=limits)
    except Exception:
        return failed_outcome(document_type)


def failed_outcome(document_type: DocumentType):
    warning = ExtractionWarning(
        code=ExtractionWarningCode.EXTRACTION_ERROR,
        message="The document could not be extracted safely.",
    )
    if document_type is DocumentType.PDF:
        return (
            ExtractionStatus.FAILED,
            PDFContent(pages=[], combined_text=""),
            PDFMetrics(
                page_count=0,
                processed_page_count=0,
                pages_with_text=0,
                pages_without_text=0,
                extracted_character_count=0,
            ),
            [warning],
        )
    if document_type is DocumentType.DOCX:
        return (
            ExtractionStatus.FAILED,
            DOCXContent(blocks=[], combined_text=""),
            DOCXMetrics(
                block_count=0,
                paragraph_count=0,
                heading_count=0,
                table_count=0,
                extracted_character_count=0,
            ),
            [warning],
        )
    if document_type is DocumentType.MD:
        content = MarkdownContent(markdown="", combined_text="")
        metrics = TextMetrics(extracted_character_count=0, line_count=0)
    elif document_type is DocumentType.TXT:
        content = TextContent(text="", combined_text="")
        metrics = TextMetrics(extracted_character_count=0, line_count=0)
    else:
        content = StructuredContent(structured_content=None, normalized_text="")
        metrics = StructuredMetrics(root_type="NULL", extracted_character_count=0)
    return ExtractionStatus.FAILED, content, metrics, [warning]
