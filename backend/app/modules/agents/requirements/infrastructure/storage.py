import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from pydantic import ValidationError

from app.modules.agents.requirements.contracts.schemas import (
    RequirementSourceMetadata,
    RequirementSourceType,
)
from app.modules.agents.requirements.infrastructure.artifact_paths import (
    ArtifactPathError,
    RequirementArtifactKind,
    RequirementArtifactPaths,
    SOURCE_ID_PATTERN,
)


DOCUMENT_MAX_SIZE = 10 * 1024 * 1024
AUDIO_MAX_SIZE = 50 * 1024 * 1024
VIDEO_MAX_SIZE = 200 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 64 * 1024

EXTENSIONS = {
    RequirementSourceType.DOCUMENT: frozenset({".pdf", ".docx", ".txt"}),
    RequirementSourceType.AUDIO: frozenset({".mp3", ".wav", ".m4a"}),
    RequirementSourceType.VIDEO: frozenset({".mp4", ".mov", ".webm"}),
}
PREFIXES = {
    RequirementSourceType.DOCUMENT: "DOC",
    RequirementSourceType.AUDIO: "AUD",
    RequirementSourceType.VIDEO: "VID",
}
SIZE_LIMITS = {
    RequirementSourceType.DOCUMENT: DOCUMENT_MAX_SIZE,
    RequirementSourceType.AUDIO: AUDIO_MAX_SIZE,
    RequirementSourceType.VIDEO: VIDEO_MAX_SIZE,
}
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}
DECLARED_MIME_TYPES = {
    extension: frozenset({mime_type, "application/octet-stream"})
    for extension, mime_type in MIME_TYPES.items()
}
DECLARED_MIME_TYPES[".wav"] = frozenset(
    {"audio/wav", "audio/x-wav", "application/octet-stream"}
)
DECLARED_MIME_TYPES[".m4a"] = frozenset(
    {"audio/mp4", "audio/x-m4a", "application/octet-stream"}
)
_ALLOCATION_LOCK = Lock()


class SourceValidationError(ValueError):
    pass


class SourceNotFoundError(LookupError):
    pass


class SourceStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredRequirementSource:
    """Compatibility view for N1/N2; future nodes must use artifact storage."""

    metadata: RequirementSourceMetadata
    file_path: Path
    processing_path: Path
    processing_partial_path: Path
    result_path: Path
    result_partial_path: Path
    audio_processing_path: Path
    audio_processing_partial_path: Path
    audio_result_path: Path
    audio_result_partial_path: Path
    video_processing_path: Path
    video_processing_partial_path: Path
    video_result_path: Path
    video_result_partial_path: Path
    preparation_path: Path
    preparation_partial_path: Path
    normalized_result_path: Path
    normalized_result_partial_path: Path
    chunk_result_path: Path
    chunk_result_partial_path: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RequirementSourceStorage:
    def __init__(self, root: Path, clock=utc_now) -> None:
        self._artifact_paths = RequirementArtifactPaths(root)
        self._clock = clock

    async def store(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        source_type: RequirementSourceType,
        upload: UploadFile,
    ) -> RequirementSourceMetadata:
        extension, original_filename = self._validate_name(
            upload.filename, source_type
        )
        self._validate_declared_mime(upload.content_type, extension)
        project_directory = self._project_directory(agent_project_id)
        partial_path: Path | None = None
        stored_path: Path | None = None
        metadata_path: Path | None = None
        metadata_partial_path: Path | None = None

        try:
            project_directory.mkdir(parents=True, exist_ok=True)
            with _ALLOCATION_LOCK:
                source_id = self._next_source_id(project_directory, source_type)
                stored_path = self._source_artifact_path(
                    agent_project_id,
                    source_id,
                    RequirementArtifactKind.UPLOADED_SOURCE,
                    extension=extension,
                )
                partial_path = self._source_artifact_path(
                    agent_project_id,
                    source_id,
                    RequirementArtifactKind.UPLOADED_SOURCE,
                    extension=extension,
                    partial=True,
                )
                partial_path.touch(exist_ok=False)
            metadata_path = self._source_artifact_path(
                agent_project_id,
                source_id,
                RequirementArtifactKind.SOURCE_METADATA,
            )
            metadata_partial_path = self._source_artifact_path(
                agent_project_id,
                source_id,
                RequirementArtifactKind.SOURCE_METADATA,
                partial=True,
            )
            digest = hashlib.sha256()
            size_bytes = 0
            with partial_path.open("wb") as destination:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > SIZE_LIMITS[source_type]:
                        limit_mb = SIZE_LIMITS[source_type] // (1024 * 1024)
                        raise SourceValidationError(
                            f"{source_type.value} files must not exceed {limit_mb} MB"
                        )
                    digest.update(chunk)
                    destination.write(chunk)
            if size_bytes == 0:
                raise SourceValidationError("Uploaded file must not be empty")
            self._validate_content(partial_path, extension)
            partial_path.replace(stored_path)
            metadata = RequirementSourceMetadata(
                source_id=source_id,
                source_type=source_type,
                original_filename=original_filename,
                mime_type=MIME_TYPES[extension],
                extension=extension,
                size_bytes=size_bytes,
                sha256=digest.hexdigest(),
                created_at=self._clock(),
            )
            sidecar = {
                **metadata.model_dump(mode="json"),
                "agent_project_id": agent_project_id,
                "owner_user_id": owner_user_id,
            }
            metadata_partial_path.write_text(
                json.dumps(sidecar, separators=(",", ":")), encoding="utf-8"
            )
            metadata_partial_path.replace(metadata_path)
            self._record_allocated_id(project_directory, source_id)
            return metadata
        except SourceValidationError:
            self._cleanup(partial_path, stored_path, metadata_partial_path, metadata_path)
            raise
        except SourceStorageError:
            self._cleanup(partial_path, stored_path, metadata_partial_path, metadata_path)
            raise
        except (OSError, ValidationError) as exc:
            self._cleanup(partial_path, stored_path, metadata_partial_path, metadata_path)
            raise SourceStorageError("Requirement source could not be stored") from exc

    def list_for_project(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
    ) -> list[RequirementSourceMetadata]:
        project_directory = self._project_directory(agent_project_id)
        if not project_directory.exists():
            return []
        try:
            sources = []
            for metadata_path in project_directory.glob("*.metadata.json"):
                source_id = metadata_path.name.removesuffix(".metadata.json")
                if not SOURCE_ID_PATTERN.fullmatch(source_id):
                    continue
                metadata = self._load_metadata(
                    metadata_path, agent_project_id, owner_user_id, source_id
                )
                stored_path = self._source_artifact_path(
                    agent_project_id,
                    source_id,
                    RequirementArtifactKind.UPLOADED_SOURCE,
                    extension=metadata.extension,
                )
                if not stored_path.is_file():
                    raise SourceStorageError(
                        "Requirement source metadata references a missing file"
                    )
                sources.append(metadata)
            return sorted(sources, key=lambda item: (item.created_at, item.source_id))
        except SourceStorageError:
            raise
        except OSError as exc:
            raise SourceStorageError("Requirement sources could not be listed") from exc

    def delete(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        source_id: str,
    ) -> None:
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise SourceNotFoundError(source_id)
        metadata_path = self._source_artifact_path(
            agent_project_id,
            source_id,
            RequirementArtifactKind.SOURCE_METADATA,
        )
        metadata = self._load_metadata(
            metadata_path, agent_project_id, owner_user_id, source_id
        )
        cleanup_paths = self._source_cleanup_paths(
            agent_project_id, source_id, metadata.extension
        )
        try:
            for artifact_path in cleanup_paths[:-1]:
                artifact_path.unlink(missing_ok=True)
            cleanup_paths[-1].unlink()
        except FileNotFoundError as exc:
            raise SourceNotFoundError(source_id) from exc
        except OSError as exc:
            raise SourceStorageError("Requirement source could not be removed") from exc

    def locate(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        source_id: str,
        require_file: bool = True,
    ) -> StoredRequirementSource:
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise SourceNotFoundError(source_id)
        metadata_path = self._source_artifact_path(
            agent_project_id,
            source_id,
            RequirementArtifactKind.SOURCE_METADATA,
        )
        metadata = self._load_metadata(
            metadata_path, agent_project_id, owner_user_id, source_id
        )
        file_path = self._source_artifact_path(
            agent_project_id,
            source_id,
            RequirementArtifactKind.UPLOADED_SOURCE,
            extension=metadata.extension,
        )
        if require_file and not file_path.is_file():
            raise SourceStorageError(
                "Requirement source metadata references a missing file"
            )

        def artifact(kind: RequirementArtifactKind, *, partial: bool = False) -> Path:
            return self._source_artifact_path(
                agent_project_id, source_id, kind, partial=partial
            )

        return StoredRequirementSource(
            metadata=metadata,
            file_path=file_path,
            processing_path=artifact(RequirementArtifactKind.DOCUMENT_PROCESSING),
            processing_partial_path=artifact(
                RequirementArtifactKind.DOCUMENT_PROCESSING, partial=True
            ),
            result_path=artifact(RequirementArtifactKind.DOCUMENT_RESULT),
            result_partial_path=artifact(
                RequirementArtifactKind.DOCUMENT_RESULT, partial=True
            ),
            audio_processing_path=artifact(
                RequirementArtifactKind.AUDIO_PROCESSING
            ),
            audio_processing_partial_path=artifact(
                RequirementArtifactKind.AUDIO_PROCESSING, partial=True
            ),
            audio_result_path=artifact(RequirementArtifactKind.AUDIO_RESULT),
            audio_result_partial_path=artifact(
                RequirementArtifactKind.AUDIO_RESULT, partial=True
            ),
            video_processing_path=artifact(
                RequirementArtifactKind.VIDEO_PROCESSING
            ),
            video_processing_partial_path=artifact(
                RequirementArtifactKind.VIDEO_PROCESSING, partial=True
            ),
            video_result_path=artifact(RequirementArtifactKind.VIDEO_RESULT),
            video_result_partial_path=artifact(
                RequirementArtifactKind.VIDEO_RESULT, partial=True
            ),
            preparation_path=artifact(
                RequirementArtifactKind.EVIDENCE_PREPARATION
            ),
            preparation_partial_path=artifact(
                RequirementArtifactKind.EVIDENCE_PREPARATION, partial=True
            ),
            normalized_result_path=artifact(RequirementArtifactKind.NORMALIZED_RESULT),
            normalized_result_partial_path=artifact(
                RequirementArtifactKind.NORMALIZED_RESULT, partial=True
            ),
            chunk_result_path=artifact(RequirementArtifactKind.CHUNK_RESULT),
            chunk_result_partial_path=artifact(
                RequirementArtifactKind.CHUNK_RESULT, partial=True
            ),
        )

    def _next_source_id(
        self, directory: Path, source_type: RequirementSourceType
    ) -> str:
        prefix = PREFIXES[source_type]
        maximum = 0
        sequence_path = self._contained(directory, ".source-id-sequences.json")
        if sequence_path.exists():
            try:
                sequences = json.loads(sequence_path.read_text(encoding="utf-8"))
                maximum = int(sequences.get(prefix, 0))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise SourceStorageError(
                    "Requirement source ID sequence is unavailable"
                ) from exc
        for path in directory.glob(f"{prefix}-*.metadata.json"):
            candidate = path.name.removesuffix(".metadata.json")
            match = SOURCE_ID_PATTERN.fullmatch(candidate)
            if match and match.group(1) == prefix:
                maximum = max(maximum, int(match.group(2)))
        for path in directory.glob(f"{prefix}-*.part"):
            candidate = path.name.split(".", maxsplit=1)[0]
            match = SOURCE_ID_PATTERN.fullmatch(candidate)
            if match:
                maximum = max(maximum, int(match.group(2)))
        return f"{prefix}-{maximum + 1:03d}"

    def _record_allocated_id(self, directory: Path, source_id: str) -> None:
        match = SOURCE_ID_PATTERN.fullmatch(source_id)
        if match is None:
            raise SourceStorageError("Requirement source ID is invalid")
        prefix, sequence_text = match.groups()
        sequence_path = self._contained(directory, ".source-id-sequences.json")
        partial_path = self._contained(directory, ".source-id-sequences.json.part")
        try:
            with _ALLOCATION_LOCK:
                if sequence_path.exists():
                    sequences = json.loads(sequence_path.read_text(encoding="utf-8"))
                else:
                    sequences = {}
                sequences[prefix] = max(
                    int(sequences.get(prefix, 0)), int(sequence_text)
                )
                partial_path.write_text(
                    json.dumps(sequences, separators=(",", ":")), encoding="utf-8"
                )
                partial_path.replace(sequence_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._cleanup(partial_path)
            raise SourceStorageError(
                "Requirement source ID sequence could not be persisted"
            ) from exc

    @staticmethod
    def _load_metadata(
        metadata_path: Path,
        agent_project_id: str,
        owner_user_id: str,
        source_id: str,
    ) -> RequirementSourceMetadata:
        try:
            sidecar = json.loads(metadata_path.read_text(encoding="utf-8"))
            public_metadata = {
                field: sidecar[field]
                for field in RequirementSourceMetadata.model_fields
                if field in sidecar
            }
            metadata = RequirementSourceMetadata.model_validate(public_metadata)
        except FileNotFoundError as exc:
            raise SourceNotFoundError(source_id) from exc
        except (OSError, json.JSONDecodeError, ValidationError, KeyError) as exc:
            raise SourceStorageError("Requirement source metadata is unavailable") from exc
        if (
            sidecar.get("agent_project_id") != agent_project_id
            or sidecar.get("owner_user_id") != owner_user_id
            or metadata.source_id != source_id
        ):
            raise SourceNotFoundError(source_id)
        return metadata

    def _project_directory(self, agent_project_id: str) -> Path:
        try:
            return self._artifact_paths.inputs_directory(agent_project_id)
        except ArtifactPathError as exc:
            raise SourceStorageError("Unsafe requirement source storage path") from exc

    def _source_artifact_path(
        self,
        agent_project_id: str,
        source_id: str,
        kind: RequirementArtifactKind,
        *,
        extension: str | None = None,
        partial: bool = False,
    ) -> Path:
        try:
            return self._artifact_paths.for_source(
                agent_project_id,
                source_id,
                kind,
                extension=extension,
                partial=partial,
            )
        except ArtifactPathError as exc:
            raise SourceStorageError("Unsafe requirement source storage path") from exc

    def _source_cleanup_paths(
        self, agent_project_id: str, source_id: str, extension: str
    ) -> tuple[Path, ...]:
        try:
            return self._artifact_paths.source_cleanup_paths(
                agent_project_id, source_id, extension
            )
        except ArtifactPathError as exc:
            raise SourceStorageError("Unsafe requirement source storage path") from exc

    @staticmethod
    def _contained(directory: Path, filename: str) -> Path:
        candidate = (directory / filename).resolve()
        try:
            candidate.relative_to(directory)
        except ValueError as exc:
            raise SourceStorageError("Unsafe requirement source storage path") from exc
        return candidate

    @staticmethod
    def _validate_name(
        filename: str | None,
        source_type: RequirementSourceType,
    ) -> tuple[str, str]:
        normalized = (filename or "").replace("\\", "/").split("/")[-1]
        normalized = "".join(
            character for character in normalized if character.isprintable()
        ).strip()
        if not normalized or len(normalized) > 255:
            raise SourceValidationError("A valid filename is required")
        extension = Path(normalized).suffix.lower()
        if extension not in EXTENSIONS[source_type]:
            raise SourceValidationError(
                f"{extension or 'unknown'} file type is not supported for "
                f"{source_type.value}"
            )
        return extension, normalized

    @staticmethod
    def _validate_declared_mime(content_type: str | None, extension: str) -> None:
        normalized = (content_type or "").lower().split(";", maxsplit=1)[0].strip()
        if normalized and normalized not in DECLARED_MIME_TYPES[extension]:
            raise SourceValidationError(
                f"Declared MIME type does not match the {extension} file type"
            )

    @staticmethod
    def _validate_content(path: Path, extension: str) -> None:
        with path.open("rb") as source:
            header = source.read(32)
        valid = False
        if extension == ".pdf":
            valid = header.startswith(b"%PDF-")
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
        elif extension == ".txt":
            try:
                content = path.read_bytes()
                if content.startswith((b"\xff\xfe", b"\xfe\xff")):
                    content.decode("utf-16")
                    valid = True
                else:
                    valid = b"\x00" not in content
                    content.decode("utf-8-sig")
            except (UnicodeDecodeError, UnicodeError):
                valid = False
        elif extension == ".mp3":
            valid = header.startswith(b"ID3") or (
                len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
            )
        elif extension == ".wav":
            valid = (
                len(header) >= 12
                and header[:4] == b"RIFF"
                and header[8:12] == b"WAVE"
            )
        elif extension in {".m4a", ".mp4", ".mov"}:
            valid = len(header) >= 12 and header[4:8] == b"ftyp"
        elif extension == ".webm":
            valid = header.startswith(b"\x1aE\xdf\xa3")
        if not valid:
            raise SourceValidationError(
                f"File content does not match the declared {extension} type"
            )

    @staticmethod
    def _cleanup(*paths: Path | None) -> None:
        for path in paths:
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

