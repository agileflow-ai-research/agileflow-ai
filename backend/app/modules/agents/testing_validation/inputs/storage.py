"""Server-controlled registration of Agent 4 TEST_GENERATION source files and records.

Scope: registration only. This module stores bytes and JSON sidecars, validates the
declared file type, and enforces size limits. It never opens, parses, or extracts
document content. Extraction belongs to a later step.

Relationship to Agent 3: Agent 3 owns its own upload storage and extraction code. Agent 4
does not import it because that would give Agent 4 uploads Agent 3 identities. This is
a deliberate, minimal, temporary duplication of registration logic only. See the
shared-infrastructure decision in the contract (§7.1).
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile

from app.modules.agents.testing_validation.contracts.enums import Agent4InputSourceType
from app.modules.agents.testing_validation.inputs.constants import (
    DOCUMENT_EXTENSIONS,
    DOCUMENT_MAX_SIZE,
    IMAGE_EXTENSIONS,
    IMAGE_MAX_SIZE,
    MIME_TYPES,
    UPLOAD_CHUNK_SIZE,
)

SOURCE_ID_PATTERN = re.compile(r"^(LOCAL|A4UP)-[0-9a-f]{32}$")
STORAGE_DIRECTORY = "test-generation-inputs"


class InputValidationError(ValueError):
    pass


class InputNotFoundError(LookupError):
    pass


class InputStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_source_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class TestGenerationInputStorage:
    def __init__(self, root: Path, clock=utc_now) -> None:
        self._root = Path(root)
        self._clock = clock

    # --- persisted records -------------------------------------------------

    def list_records(self, agent_project_id: str, owner_user_id: str) -> list[dict]:
        directory = self._project_directory(agent_project_id)
        if not directory.is_dir():
            return []
        records = []
        for path in directory.glob("*.json"):
            record = self._load(path)
            if record is None:
                continue
            if record.get("owner_user_id") != owner_user_id:
                continue
            records.append(record)
        return sorted(records, key=lambda item: (item["created_at"], item["source_id"]))

    def write_record(self, agent_project_id: str, owner_user_id: str, record: dict) -> None:
        if not SOURCE_ID_PATTERN.fullmatch(record["source_id"]):
            raise InputStorageError("Invalid source identity")
        directory = self._project_directory(agent_project_id)
        path = self._contained(directory, f"{record['source_id']}.json")
        partial = self._contained(directory, f"{record['source_id']}.json.part")
        sidecar = {**record, "owner_user_id": owner_user_id}
        try:
            directory.mkdir(parents=True, exist_ok=True)
            partial.write_text(json.dumps(sidecar, separators=(",", ":")), encoding="utf-8")
            partial.replace(path)
        except OSError as exc:
            self._cleanup(partial, path)
            raise InputStorageError("Source record could not be stored") from exc

    def delete(self, agent_project_id: str, owner_user_id: str, source_id: str) -> None:
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise InputNotFoundError(source_id)
        directory = self._project_directory(agent_project_id)
        path = self._contained(directory, f"{source_id}.json")
        record = self._load(path)
        if record is None or record.get("owner_user_id") != owner_user_id:
            raise InputNotFoundError(source_id)
        extension = record.get("storage_extension")
        if extension:
            self._cleanup(self._contained(directory, f"{source_id}{extension}"))
        self._cleanup(path)

    # --- file bytes ---------------------------------------------------------

    async def store_file(
        self,
        *,
        agent_project_id: str,
        source_id: str,
        source_type: Agent4InputSourceType,
        upload: UploadFile,
    ) -> dict:
        """Write one validated file under a server-chosen name and return its safe metadata."""
        extension, original_filename = self._validate_name(upload.filename, source_type)
        directory = self._project_directory(agent_project_id)
        stored_path = self._contained(directory, f"{source_id}{extension}")
        partial_path = self._contained(directory, f"{source_id}{extension}.part")
        size_limit = DOCUMENT_MAX_SIZE if source_type is Agent4InputSourceType.DOCUMENT else IMAGE_MAX_SIZE
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with partial_path.open("xb") as destination:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > size_limit:
                        raise InputValidationError(
                            f"{source_type.value} files must not exceed {size_limit // (1024 * 1024)} MB"
                        )
                    digest.update(chunk)
                    destination.write(chunk)
            if size_bytes == 0:
                raise InputValidationError("Uploaded file must not be empty")
            self._validate_content(partial_path, extension)
            partial_path.replace(stored_path)
        except InputValidationError:
            self._cleanup(partial_path, stored_path)
            raise
        except OSError as exc:
            self._cleanup(partial_path, stored_path)
            raise InputStorageError("Uploaded file could not be stored") from exc
        return {
            "original_filename": original_filename,
            "mime_type": MIME_TYPES[extension],
            "size_bytes": size_bytes,
            "sha256": digest.hexdigest(),
            "storage_extension": extension,
        }

    def delete_file(self, agent_project_id: str, source_id: str, extension: str) -> None:
        directory = self._project_directory(agent_project_id)
        self._cleanup(self._contained(directory, f"{source_id}{extension}"))

    # --- paths and validation ----------------------------------------------

    def _project_directory(self, agent_project_id: str) -> Path:
        root = self._root.resolve()
        directory = (root / agent_project_id / STORAGE_DIRECTORY).resolve()
        try:
            directory.relative_to(root)
        except ValueError as exc:
            raise InputStorageError("Unsafe input storage path") from exc
        return directory

    @staticmethod
    def _contained(directory: Path, filename: str) -> Path:
        candidate = (directory / filename).resolve()
        try:
            candidate.relative_to(directory.resolve())
        except ValueError as exc:
            raise InputStorageError("Unsafe input storage path") from exc
        return candidate

    def _load(self, path: Path) -> dict | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) and "source_id" in value else None

    @staticmethod
    def _validate_name(filename: str | None, source_type: Agent4InputSourceType) -> tuple[str, str]:
        normalized = (filename or "").replace("\\", "/").split("/")[-1]
        normalized = "".join(character for character in normalized if character.isprintable()).strip()
        if not normalized or len(normalized) > 255:
            raise InputValidationError("A valid filename is required")
        extension = Path(normalized).suffix.lower()
        allowed = DOCUMENT_EXTENSIONS if source_type is Agent4InputSourceType.DOCUMENT else IMAGE_EXTENSIONS
        if extension not in allowed:
            raise InputValidationError(f"{extension or 'unknown'} file type is not supported for {source_type.value}")
        return extension, normalized

    @staticmethod
    def _validate_content(path: Path, extension: str) -> None:
        with path.open("rb") as source:
            header = source.read(16)
        if extension == ".pdf":
            valid = header.startswith(b"%PDF-")
        elif extension == ".png":
            valid = header.startswith(b"\x89PNG\r\n\x1a\n")
        elif extension in {".jpg", ".jpeg"}:
            valid = header.startswith(b"\xff\xd8\xff")
        elif extension == ".webp":
            valid = len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
        elif extension == ".docx":
            # Only the archive's entry names are read. Nothing is extracted or decompressed.
            try:
                with ZipFile(path) as archive:
                    names = set(archive.namelist())
                valid = "[Content_Types].xml" in names and "word/document.xml" in names
            except BadZipFile:
                valid = False
        else:
            # Text formats must be UTF-8 without NUL bytes. Structure is not parsed in this step.
            try:
                content = path.read_bytes()
                valid = b"\x00" not in content
                if valid:
                    content.decode("utf-8")
            except UnicodeDecodeError:
                valid = False
        if not valid:
            raise InputValidationError(f"File content does not match the declared {extension} type")

    @staticmethod
    def _cleanup(*paths: Path) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
