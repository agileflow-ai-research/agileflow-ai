DOCUMENT_MAX_SIZE = 10 * 1024 * 1024
IMAGE_MAX_SIZE = 5 * 1024 * 1024
TEXT_MAX_CHARACTERS = 200_000
PROJECT_TEXT_MAX_CHARACTERS = 1_000_000
PROJECT_SOURCE_MAX_COUNT = 100
UPLOAD_CHUNK_SIZE = 64 * 1024

DOCUMENT_EXTENSIONS = frozenset(
    {".pdf", ".docx", ".txt", ".md", ".json", ".yaml", ".yml"}
)
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
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

DECLARED_MIME_TYPES = {
    extension: frozenset({mime_type, "application/octet-stream"})
    for extension, mime_type in MIME_TYPES.items()
}
DECLARED_MIME_TYPES[".md"] = frozenset(
    {"text/markdown", "text/plain", "application/octet-stream"}
)
for yaml_extension in (".yaml", ".yml"):
    DECLARED_MIME_TYPES[yaml_extension] = frozenset(
        {
            "application/yaml",
            "application/x-yaml",
            "text/yaml",
            "text/x-yaml",
            "text/plain",
            "application/octet-stream",
        }
    )
