"""Agent 3 extraction constants.

Values come from the shared document extraction defaults. They stay as module attributes
so existing Agent 3 behavior, and tests that tune limits, keep working unchanged.
"""

from app.common.document_extraction.constants import DEFAULT_LIMITS
from app.common.document_extraction.constants import EXTRACTOR_VERSION as SHARED_EXTRACTOR_VERSION

EXTRACTOR_VERSION = SHARED_EXTRACTOR_VERSION
MAX_PDF_PAGES = DEFAULT_LIMITS.max_pdf_pages
MAX_EXTRACTED_CHARACTERS = DEFAULT_LIMITS.max_extracted_characters
MAX_DOCX_UNCOMPRESSED_BYTES = DEFAULT_LIMITS.max_docx_uncompressed_bytes
MAX_DOCX_ARCHIVE_ENTRIES = DEFAULT_LIMITS.max_docx_archive_entries
