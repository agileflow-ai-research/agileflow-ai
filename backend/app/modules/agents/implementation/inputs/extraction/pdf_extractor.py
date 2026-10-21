from pathlib import Path

from app.common.document_extraction.extractors import extract_pdf as _extract_pdf
from app.modules.agents.implementation.inputs.extraction import constants
from app.modules.agents.implementation.inputs.extraction.schemas import (
    ExtractionWarning, PDFContent, PDFMetrics,
)


def extract_pdf(path: Path):
    status, content, metrics, warnings = _extract_pdf(
        path,
        max_pages=constants.MAX_PDF_PAGES,
        max_characters=constants.MAX_EXTRACTED_CHARACTERS,
    )
    return (
        status,
        PDFContent.model_validate(content.model_dump()),
        PDFMetrics.model_validate(metrics.model_dump()),
        [ExtractionWarning.model_validate(item.model_dump()) for item in warnings],
    )
