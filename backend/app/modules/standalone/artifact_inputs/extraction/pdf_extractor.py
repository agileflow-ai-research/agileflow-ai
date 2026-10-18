from pathlib import Path

import fitz

from app.modules.standalone.artifact_inputs.extraction import constants
from app.modules.standalone.artifact_inputs.extraction.schemas import (
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    ExtractionWarningLocation,
    PDFContent,
    PDFMetrics,
    PDFPage,
)


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def extract_pdf(path: Path):
    pages: list[PDFPage] = []
    combined_parts: list[str] = []
    warnings: list[ExtractionWarning] = []
    pages_with_text = 0
    pages_without_text = 0
    truncated = False

    with fitz.open(path) as document:
        page_count = document.page_count
        process_count = min(page_count, constants.MAX_PDF_PAGES)
        if page_count > constants.MAX_PDF_PAGES:
            truncated = True
            warnings.append(
                ExtractionWarning(
                    code=ExtractionWarningCode.CONTENT_TRUNCATED,
                    message=(
                        f"Only the first {constants.MAX_PDF_PAGES} PDF pages "
                        "were extracted."
                    ),
                )
            )
        remaining = constants.MAX_EXTRACTED_CHARACTERS
        for page_index in range(process_count):
            page_number = page_index + 1
            try:
                text = _normalize_text(document.load_page(page_index).get_text("text"))
            except Exception:
                text = ""
                warnings.append(
                    ExtractionWarning(
                        code=ExtractionWarningCode.EXTRACTION_ERROR,
                        message=f"Page {page_number} could not be extracted.",
                        location=ExtractionWarningLocation(page_number=page_number),
                    )
                )
            if not text:
                pages_without_text += 1
                pages.append(PDFPage(page_number=page_number, text=""))
                warnings.append(
                    ExtractionWarning(
                        code=ExtractionWarningCode.NO_TEXT_ON_PAGE,
                        message=(
                            f"No extractable text was found on page {page_number}."
                        ),
                        location=ExtractionWarningLocation(page_number=page_number),
                    )
                )
                continue
            separator_size = 2 if combined_parts else 0
            available = max(remaining - separator_size, 0)
            extracted = text[:available]
            if extracted:
                pages_with_text += 1
                pages.append(PDFPage(page_number=page_number, text=extracted))
                combined_parts.append(extracted)
                remaining -= len(extracted) + separator_size
            if len(extracted) < len(text) or remaining <= 0:
                truncated = True
                warnings.append(
                    ExtractionWarning(
                        code=ExtractionWarningCode.CONTENT_TRUNCATED,
                        message="PDF text exceeded the extraction character limit.",
                        location=ExtractionWarningLocation(page_number=page_number),
                    )
                )
                break

    combined_text = "\n\n".join(combined_parts)
    if not combined_text.strip():
        status = ExtractionStatus.FAILED
        if not any(
            warning.code is ExtractionWarningCode.NO_EXTRACTABLE_TEXT
            for warning in warnings
        ):
            warnings.append(
                ExtractionWarning(
                    code=ExtractionWarningCode.NO_EXTRACTABLE_TEXT,
                    message=(
                        "No reliable textual content could be extracted from this PDF. "
                        "The document may be image-only."
                    ),
                )
            )
    elif truncated or pages_without_text or any(
        warning.code is ExtractionWarningCode.EXTRACTION_ERROR
        for warning in warnings
    ):
        status = ExtractionStatus.PARTIAL
    else:
        status = ExtractionStatus.SUCCESS
    return (
        status,
        PDFContent(pages=pages, combined_text=combined_text),
        PDFMetrics(
            page_count=page_count,
            processed_page_count=len(pages),
            pages_with_text=pages_with_text,
            pages_without_text=pages_without_text,
            extracted_character_count=len(combined_text),
        ),
        warnings,
    )
