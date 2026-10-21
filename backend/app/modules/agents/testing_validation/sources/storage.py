import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from pydantic import ValidationError

from app.common.id_generator import validate_id
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputOriginAgent,
    TestGenerationInputSourceType,
    TestGenerationInputSuppliedVia,
)
from app.modules.agents.testing_validation.sources.constants import (
    DECLARED_MIME_TYPES,
    DOCUMENT_EXTENSIONS,
    DOCUMENT_MAX_SIZE,
    IMAGE_EXTENSIONS,
    IMAGE_MAX_SIZE,
    MIME_TYPES,
    PROJECT_SOURCE_MAX_COUNT,
    PROJECT_TEXT_MAX_CHARACTERS,
    UPLOAD_CHUNK_SIZE,
)
from app.modules.agents.testing_validation.sources.schemas import (
    TestGenerationSourceRecord,
    TestGenerationSourceStatus,
)


SOURCE_ID_PATTERN = re.compile(r"^A4SRC-[0-9a-f]{32}$")
SOURCE_SIDECAR_SUFFIX = ".source.json"
SOURCE_STORAGE_LOCK = RLock()


class Agent4SourceValidationError(ValueError):
    pass


class Agent4SourceCapacityError(ValueError):
    pass


class Agent4SourceNotFoundError(LookupError):
    pass


class Agent4SourceStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Agent4SourceStorage:
    def __init__(self, root: Path, clock=utc_now) -> None:
        self._root = Path(root).resolve()
        self._clock = clock

    def create_text(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        artifact_type: TestGenerationInputArtifactType,
        normally_supplied_by: TestGenerationInputOriginAgent,
        label: str | None,
        content: str,
    ) -> TestGenerationSourceRecord:
        with SOURCE_STORAGE_LOCK:
            existing = self.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=owner_user_id,
            )
            self._check_capacity(existing, added_text_characters=len(content))
            record = TestGenerationSourceRecord(
                source_id=self._new_source_id(),
                agent_project_id=agent_project_id,
                artifact_type=artifact_type,
                source_type=TestGenerationInputSourceType.TEXT,
                normally_supplied_by=normally_supplied_by,
                supplied_via=TestGenerationInputSuppliedVia.STANDALONE_MANUAL_INPUT,
                label=label,
                collection_status=TestGenerationSourceStatus.READY,
                created_at=self._clock(),
                text_content=content,
            )
            with SOURCE_STORAGE_LOCK:
                current = self.list_for_project(
                    agent_project_id=agent_project_id,
                    owner_user_id=owner_user_id,
                )
                self._check_capacity(current)
                self._write_sidecar(record, owner_user_id)
            return record

    async def create_file(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        artifact_type: TestGenerationInputArtifactType,
        source_type: TestGenerationInputSourceType,
        normally_supplied_by: TestGenerationInputOriginAgent,
        label: str | None,
        upload: UploadFile,
    ) -> TestGenerationSourceRecord:
        if source_type not in {
            TestGenerationInputSourceType.DOCUMENT,
            TestGenerationInputSourceType.IMAGE,
        }:
            raise Agent4SourceValidationError(
                "File uploads require DOCUMENT or IMAGE source_type"
            )
        extension, original_filename = self._validate_name(
            upload.filename, source_type
        )
        self._validate_declared_mime(upload.content_type, extension)
        existing = self.list_for_project(
            agent_project_id=agent_project_id,
            owner_user_id=owner_user_id,
        )
        self._check_capacity(existing)
        source_id = self._new_source_id()
        inputs_directory = self._inputs_directory(agent_project_id)
        stored_path = self._contained(inputs_directory, f"{source_id}{extension}")
        partial_path = self._contained(
            inputs_directory, f"{source_id}{extension}.part"
        )
        metadata_path = self._sidecar_path(agent_project_id, source_id)
        metadata_partial_path = metadata_path.with_suffix(
            metadata_path.suffix + ".part"
        )
        size_limit = (
            DOCUMENT_MAX_SIZE
            if source_type is TestGenerationInputSourceType.DOCUMENT
            else IMAGE_MAX_SIZE
        )
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            inputs_directory.mkdir(parents=True, exist_ok=True)
            with partial_path.open("xb") as destination:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > size_limit:
                        raise Agent4SourceValidationError(
                            f"{source_type.value} files must not exceed "
                            f"{size_limit // (1024 * 1024)} MB"
                        )
                    digest.update(chunk)
                    destination.write(chunk)
            if size_bytes == 0:
                raise Agent4SourceValidationError("Uploaded file must not be empty")
            self._validate_content(partial_path, extension)
            partial_path.replace(stored_path)
            record = TestGenerationSourceRecord(
                source_id=source_id,
                agent_project_id=agent_project_id,
                artifact_type=artifact_type,
                source_type=source_type,
                normally_supplied_by=normally_supplied_by,
                supplied_via=TestGenerationInputSuppliedVia.STANDALONE_MANUAL_INPUT,
                label=label,
                collection_status=(
                    TestGenerationSourceStatus.UPLOADED
                    if source_type is TestGenerationInputSourceType.DOCUMENT
                    else TestGenerationSourceStatus.PENDING_ANALYSIS
                ),
                created_at=self._clock(),
                original_filename=original_filename,
                extension=extension,
                mime_type=MIME_TYPES[extension],
                size_bytes=size_bytes,
                sha256=digest.hexdigest(),
            )
            self._write_sidecar(record, owner_user_id)
            return record
        except (Agent4SourceValidationError, Agent4SourceCapacityError):
            self._cleanup(
                partial_path, stored_path, metadata_partial_path, metadata_path
            )
            raise
        except Agent4SourceStorageError:
            self._cleanup(
                partial_path, stored_path, metadata_partial_path, metadata_path
            )
            raise
        except (OSError, ValidationError) as exc:
            self._cleanup(
                partial_path, stored_path, metadata_partial_path, metadata_path
            )
            raise Agent4SourceStorageError(
                "Agent 4 source could not be stored"
            ) from exc

    def list_for_project(
        self, *, agent_project_id: str, owner_user_id: str
    ) -> list[TestGenerationSourceRecord]:
        inputs_directory = self._inputs_directory(agent_project_id)
        if not inputs_directory.exists():
            return []
        try:
            records = []
            for path in inputs_directory.glob(f"A4SRC-*{SOURCE_SIDECAR_SUFFIX}"):
                source_id = path.name.removesuffix(SOURCE_SIDECAR_SUFFIX)
                if not SOURCE_ID_PATTERN.fullmatch(source_id):
                    continue
                record = self._load_sidecar(
                    path, agent_project_id, owner_user_id, source_id
                )
                if record.source_type is not TestGenerationInputSourceType.TEXT:
                    file_path = self._contained(
                        inputs_directory, f"{source_id}{record.extension}"
                    )
                    if not file_path.is_file():
                        raise Agent4SourceStorageError(
                            "Agent 4 source metadata references a missing file"
                        )
                records.append(record)
            return sorted(records, key=lambda item: (item.created_at, item.source_id))
        except (Agent4SourceStorageError, Agent4SourceNotFoundError):
            raise
        except OSError as exc:
            raise Agent4SourceStorageError(
                "Agent 4 sources could not be listed"
            ) from exc

    def delete(
        self, *, agent_project_id: str, owner_user_id: str, source_id: str
    ) -> None:
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise Agent4SourceNotFoundError(source_id)
        sidecar_path = self._sidecar_path(agent_project_id, source_id)
        record = self._load_sidecar(
            sidecar_path, agent_project_id, owner_user_id, source_id
        )
        inputs_directory = self._inputs_directory(agent_project_id)
        cleanup_paths = [
            sidecar_path.with_suffix(sidecar_path.suffix + ".part"),
        ]
        if record.extension is not None:
            file_path = self._contained(
                inputs_directory, f"{source_id}{record.extension}"
            )
            cleanup_paths.extend(
                [file_path, file_path.with_suffix(file_path.suffix + ".part")]
            )
        try:
            with SOURCE_STORAGE_LOCK:
                for path in cleanup_paths:
                    path.unlink(missing_ok=True)
                sidecar_path.unlink()
        except FileNotFoundError as exc:
            raise Agent4SourceNotFoundError(source_id) from exc
        except OSError as exc:
            raise Agent4SourceStorageError(
                "Agent 4 source could not be removed"
            ) from exc

    def _write_sidecar(
        self, record: TestGenerationSourceRecord, owner_user_id: str
    ) -> None:
        path = self._sidecar_path(record.agent_project_id, record.source_id)
        partial_path = path.with_suffix(path.suffix + ".part")
        payload = {
            **record.model_dump(mode="json"),
            "owner_user_id": owner_user_id,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            partial_path.write_text(
                json.dumps(payload, separators=(",", ":")), encoding="utf-8"
            )
            partial_path.replace(path)
        except OSError as exc:
            self._cleanup(partial_path)
            raise Agent4SourceStorageError(
                "Agent 4 source metadata could not be persisted"
            ) from exc

    @staticmethod
    def _load_sidecar(
        path: Path,
        agent_project_id: str,
        owner_user_id: str,
        source_id: str,
    ) -> TestGenerationSourceRecord:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            public_payload = {
                field: payload[field]
                for field in TestGenerationSourceRecord.model_fields
                if field in payload
            }
            record = TestGenerationSourceRecord.model_validate(public_payload)
        except FileNotFoundError as exc:
            raise Agent4SourceNotFoundError(source_id) from exc
        except (OSError, json.JSONDecodeError, ValidationError, KeyError) as exc:
            raise Agent4SourceStorageError(
                "Agent 4 source metadata is unavailable"
            ) from exc
        if (
            payload.get("owner_user_id") != owner_user_id
            or record.agent_project_id != agent_project_id
            or record.source_id != source_id
        ):
            raise Agent4SourceNotFoundError(source_id)
        return record

    @staticmethod
    def _check_capacity(
        existing: list[TestGenerationSourceRecord],
        *,
        added_text_characters: int = 0,
    ) -> None:
        if len(existing) >= PROJECT_SOURCE_MAX_COUNT:
            raise Agent4SourceCapacityError(
                f"A project may contain at most {PROJECT_SOURCE_MAX_COUNT} sources"
            )
        total_text = sum(len(item.text_content or "") for item in existing)
        if total_text + added_text_characters > PROJECT_TEXT_MAX_CHARACTERS:
            raise Agent4SourceCapacityError(
                "Project TEXT sources must not exceed "
                f"{PROJECT_TEXT_MAX_CHARACTERS} characters in total"
            )

    def _inputs_directory(self, agent_project_id: str) -> Path:
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4SourceStorageError("Unsafe Agent 4 source path") from exc
        return self._contained(self._root, agent_project_id) / "inputs"

    def _sidecar_path(self, agent_project_id: str, source_id: str) -> Path:
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise Agent4SourceStorageError("Invalid Agent 4 source identity")
        return self._contained(
            self._inputs_directory(agent_project_id),
            f"{source_id}{SOURCE_SIDECAR_SUFFIX}",
        )

    @staticmethod
    def _contained(directory: Path, filename: str) -> Path:
        directory = directory.resolve()
        candidate = (directory / filename).resolve()
        try:
            candidate.relative_to(directory)
        except ValueError as exc:
            raise Agent4SourceStorageError("Unsafe Agent 4 source path") from exc
        return candidate

    @staticmethod
    def _new_source_id() -> str:
        return f"A4SRC-{uuid4().hex}"

    @staticmethod
    def _validate_name(
        filename: str | None, source_type: TestGenerationInputSourceType
    ) -> tuple[str, str]:
        normalized = (filename or "").replace("\\", "/").split("/")[-1]
        normalized = "".join(
            character for character in normalized if character.isprintable()
        ).strip()
        if not normalized or len(normalized) > 255:
            raise Agent4SourceValidationError("A valid filename is required")
        extension = Path(normalized).suffix.lower()
        allowed = (
            DOCUMENT_EXTENSIONS
            if source_type is TestGenerationInputSourceType.DOCUMENT
            else IMAGE_EXTENSIONS
        )
        if extension not in allowed:
            raise Agent4SourceValidationError(
                f"{extension or 'unknown'} file type is not supported for "
                f"{source_type.value}"
            )
        return extension, normalized

    @staticmethod
    def _validate_declared_mime(content_type: str | None, extension: str) -> None:
        normalized = (content_type or "").lower().split(";", maxsplit=1)[0].strip()
        if normalized and normalized not in DECLARED_MIME_TYPES[extension]:
            raise Agent4SourceValidationError(
                f"Declared MIME type does not match the {extension} file type"
            )

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
            valid = (
                len(header) >= 12
                and header[:4] == b"RIFF"
                and header[8:12] == b"WEBP"
            )
        elif extension == ".docx":
            try:
                with ZipFile(path) as archive:
                    names = set(archive.namelist())
                valid = (
                    "[Content_Types].xml" in names
                    and "word/document.xml" in names
                )
            except BadZipFile:
                valid = False
        else:
            try:
                content = path.read_bytes()
                valid = b"\x00" not in content
                decoded = content.decode("utf-8-sig")
                if extension == ".json":
                    json.loads(decoded)
            except (UnicodeDecodeError, UnicodeError, json.JSONDecodeError):
                valid = False
        if not valid:
            raise Agent4SourceValidationError(
                f"File content does not match the declared {extension} type"
            )

    @staticmethod
    def _cleanup(*paths: Path) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
