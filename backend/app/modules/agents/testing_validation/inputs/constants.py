"""Collection limits for Agent 4 TEST_GENERATION inputs.

Document and image sizes and text limits follow Agent 3's proven values so both agents
behave the same for the same kind of input. These are collection limits only.
"""

MAX_SOURCES_PER_PROJECT = 100
MAX_TEXT_SOURCE_CHARACTERS = 200_000
MAX_TOTAL_TEXT_CHARACTERS = 1_000_000
MAX_LABEL_CHARACTERS = 200

DOCUMENT_MAX_SIZE = 10 * 1024 * 1024
IMAGE_MAX_SIZE = 5 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 64 * 1024

# Contract v1.1 §2.8: PDF, DOCX, TXT, MD, JSON, YAML. Nothing is extracted in this step.
DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".txt", ".md", ".json", ".yaml", ".yml"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

TEXT_SOURCE_PREFIX = "LOCAL"
UPLOAD_SOURCE_PREFIX = "A4UP"
