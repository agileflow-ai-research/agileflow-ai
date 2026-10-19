import json
from pathlib import Path
from typing import Any

import yaml

from app.common.document_extraction.constants import DEFAULT_LIMITS, ExtractionLimits
from app.common.document_extraction.schemas import (
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    MarkdownContent,
    StructuredContent,
    StructuredMetrics,
    TextContent,
    TextMetrics,
)


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _bounded(value: str, limit: int):
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def extract_text(
    path: Path,
    *,
    markdown: bool = False,
    limits: ExtractionLimits = DEFAULT_LIMITS,
):
    text = _normalize_text(path.read_text(encoding="utf-8-sig"))
    bounded, truncated = _bounded(text, limits.max_extracted_characters)
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


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def extract_structured(
    path: Path,
    *,
    yaml_document: bool = False,
    limits: ExtractionLimits = DEFAULT_LIMITS,
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
                    message=f"Structured document could not be safely parsed: {type(exc).__name__}.",
                )
            ],
        )

    bounded, truncated = _bounded(normalized, limits.max_extracted_characters)
    warnings: list[ExtractionWarning] = []
    if _is_empty(value):
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
                message="Normalized structured content exceeded the extraction character limit.",
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
