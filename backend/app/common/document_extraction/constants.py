"""Generic extraction defaults shared by every agent that reads documents.

Agents may pass their own ExtractionLimits. Keeping the limits as an explicit argument
lets each agent tune them without changing the shared extractors.
"""

from dataclasses import dataclass

EXTRACTOR_VERSION = "1"


@dataclass(frozen=True)
class ExtractionLimits:
    max_pdf_pages: int = 500
    max_extracted_characters: int = 2_000_000
    max_docx_uncompressed_bytes: int = 50 * 1024 * 1024
    max_docx_archive_entries: int = 10_000


DEFAULT_LIMITS = ExtractionLimits()
