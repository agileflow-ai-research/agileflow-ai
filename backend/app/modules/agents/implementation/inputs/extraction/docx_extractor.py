from pathlib import Path

from app.common.document_extraction.extractors import extract_docx as _extract_docx
from app.modules.agents.implementation.inputs.extraction import constants
from app.modules.agents.implementation.inputs.extraction.schemas import (
    DOCXContent, DOCXMetrics, ExtractionWarning,
)


def extract_docx(path: Path):
    status, content, metrics, warnings = _extract_docx(
        path,
        max_characters=constants.MAX_EXTRACTED_CHARACTERS,
        max_uncompressed_bytes=constants.MAX_DOCX_UNCOMPRESSED_BYTES,
        max_archive_entries=constants.MAX_DOCX_ARCHIVE_ENTRIES,
    )
    return (
        status,
        DOCXContent.model_validate(content.model_dump()),
        DOCXMetrics.model_validate(metrics.model_dump()),
        [ExtractionWarning.model_validate(item.model_dump()) for item in warnings],
    )
