from pathlib import Path

from app.common.document_extraction.extractors import (
    extract_structured as _extract_structured,
    extract_text as _extract_text,
)
from app.modules.agents.implementation.inputs.extraction import constants
from app.modules.agents.implementation.inputs.extraction.schemas import (
    ExtractionWarning, MarkdownContent, StructuredContent, StructuredMetrics,
    TextContent, TextMetrics,
)


def extract_text(path: Path, *, markdown: bool = False):
    status, content, metrics, warnings = _extract_text(
        path,
        max_characters=constants.MAX_EXTRACTED_CHARACTERS,
        markdown=markdown,
    )
    content_type = MarkdownContent if markdown else TextContent
    return (
        status,
        content_type.model_validate(content.model_dump()),
        TextMetrics.model_validate(metrics.model_dump()),
        [ExtractionWarning.model_validate(item.model_dump()) for item in warnings],
    )


def extract_structured(path: Path, *, yaml_document: bool = False):
    status, content, metrics, warnings = _extract_structured(
        path,
        max_characters=constants.MAX_EXTRACTED_CHARACTERS,
        yaml_document=yaml_document,
    )
    return (
        status,
        StructuredContent.model_validate(content.model_dump()),
        StructuredMetrics.model_validate(metrics.model_dump()),
        [ExtractionWarning.model_validate(item.model_dump()) for item in warnings],
    )
