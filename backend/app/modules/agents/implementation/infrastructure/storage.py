import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from pydantic import ValidationError

from app.modules.agents.implementation.contracts.schemas import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)


DOCUMENT_MAX_SIZE = 10 * 1024 * 1024
IMAGE_MAX_SIZE = 5 * 1024 * 1024
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
UPLOAD_ID_PATTERN = re.compile(r"^A3UP-[0-9a-f]{32}$")


class UploadValidationError(ValueError):
    pass


class UploadNotFoundError(LookupError):
    pass


class UploadStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StagedUpload:
    metadata: UploadedFileMetadata
    file_path: Path
    extraction_path: Path
    extraction_partial_path: Path
    chunks_path: Path
    chunks_partial_path: Path
    rule_detections_path: Path
    rule_detections_partial_path: Path
    zero_shot_detections_path: Path
    zero_shot_detections_partial_path: Path
    hybrid_detections_path: Path
    hybrid_detections_partial_path: Path
    human_reviews_path: Path
    human_reviews_partial_path: Path
    canonical_artifacts_path: Path
    canonical_artifacts_partial_path: Path
    semantic_artifacts_path: Path
    semantic_artifacts_partial_path: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ImplementationUploadStorage:
    def __init__(self, root: Path, clock=utc_now) -> None:
        self._root = Path(root)
        self._clock = clock

    async def store(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        source_type: ImplementationInputSourceType,
        artifact_type: ImplementationArtifactType,
        label: str | None,
        upload: UploadFile,
    ) -> UploadedFileMetadata:
        extension, original_filename = self._validate_name(
            upload.filename, source_type
        )
        upload_id = f"A3UP-{uuid4().hex}"
        project_directory = self._project_directory(agent_project_id)
        stored_path = self._contained(
            project_directory, f"{upload_id}{extension}"
        )
        partial_path = self._contained(
            project_directory, f"{upload_id}{extension}.part"
        )
        metadata_path = self._contained(
            project_directory, f"{upload_id}.metadata.json"
        )
        metadata_partial_path = self._contained(
            project_directory, f"{upload_id}.metadata.json.part"
        )
        size_limit = (
            DOCUMENT_MAX_SIZE
            if source_type is ImplementationInputSourceType.DOCUMENT
            else IMAGE_MAX_SIZE
        )
        digest = hashlib.sha256()
        size_bytes = 0

        try:
            project_directory.mkdir(parents=True, exist_ok=True)
            with partial_path.open("xb") as destination:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > size_limit:
                        raise UploadValidationError(
                            f"{source_type.value} files must not exceed "
                            f"{size_limit // (1024 * 1024)} MB"
                        )
                    digest.update(chunk)
                    destination.write(chunk)
            if size_bytes == 0:
                raise UploadValidationError("Uploaded file must not be empty")
            self._validate_content(partial_path, extension)
            partial_path.replace(stored_path)
            metadata = UploadedFileMetadata(
                upload_id=upload_id,
                source_type=source_type,
                artifact_type=artifact_type,
                label=label,
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
            return metadata
        except UploadValidationError:
            self._cleanup(
                partial_path,
                stored_path,
                metadata_partial_path,
                metadata_path,
            )
            raise
        except OSError as exc:
            self._cleanup(
                partial_path,
                stored_path,
                metadata_partial_path,
                metadata_path,
            )
            raise UploadStorageError(
                "Staged upload could not be stored"
            ) from exc

    def delete(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        upload_id: str,
    ) -> None:
        if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
            raise UploadNotFoundError(upload_id)
        project_directory = self._project_directory(agent_project_id)
        metadata_path = self._contained(
            project_directory, f"{upload_id}.metadata.json"
        )
        metadata = self._load_metadata(
            metadata_path, agent_project_id, owner_user_id, upload_id
        )
        if metadata.extension not in DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS:
            raise UploadStorageError("Staged upload metadata is invalid")
        stored_path = self._contained(
            project_directory, f"{upload_id}{metadata.extension}"
        )
        extraction_path = self._contained(
            project_directory, f"{upload_id}.extracted.json"
        )
        extraction_partial_path = self._contained(
            project_directory, f"{upload_id}.extracted.json.part"
        )
        chunks_path = self._contained(project_directory, f"{upload_id}.chunks.json")
        chunks_partial_path = self._contained(
            project_directory, f"{upload_id}.chunks.json.part"
        )
        rule_detections_path = self._contained(
            project_directory, f"{upload_id}.rule-detections.json"
        )
        rule_detections_partial_path = self._contained(
            project_directory, f"{upload_id}.rule-detections.json.part"
        )
        zero_shot_detections_path = self._contained(
            project_directory, f"{upload_id}.zero-shot-detections.json"
        )
        zero_shot_detections_partial_path = self._contained(
            project_directory, f"{upload_id}.zero-shot-detections.json.part"
        )
        hybrid_detections_path = self._contained(
            project_directory, f"{upload_id}.hybrid-detections.json"
        )
        hybrid_detections_partial_path = self._contained(
            project_directory, f"{upload_id}.hybrid-detections.json.part"
        )
        human_reviews_path = self._contained(
            project_directory, f"{upload_id}.human-reviews.json"
        )
        human_reviews_partial_path = self._contained(
            project_directory, f"{upload_id}.human-reviews.json.part"
        )
        canonical_artifacts_path = self._contained(
            project_directory, f"{upload_id}.canonical-artifacts.json"
        )
        canonical_artifacts_partial_path = self._contained(
            project_directory, f"{upload_id}.canonical-artifacts.json.part"
        )
        semantic_artifacts_path = self._contained(
            project_directory, f"{upload_id}.semantic-artifacts.json"
        )
        semantic_artifacts_partial_path = self._contained(
            project_directory, f"{upload_id}.semantic-artifacts.json.part"
        )
        try:
            stored_path.unlink(missing_ok=True)
            extraction_path.unlink(missing_ok=True)
            extraction_partial_path.unlink(missing_ok=True)
            chunks_path.unlink(missing_ok=True)
            chunks_partial_path.unlink(missing_ok=True)
            rule_detections_path.unlink(missing_ok=True)
            rule_detections_partial_path.unlink(missing_ok=True)
            zero_shot_detections_path.unlink(missing_ok=True)
            zero_shot_detections_partial_path.unlink(missing_ok=True)
            hybrid_detections_path.unlink(missing_ok=True)
            hybrid_detections_partial_path.unlink(missing_ok=True)
            human_reviews_path.unlink(missing_ok=True)
            human_reviews_partial_path.unlink(missing_ok=True)
            canonical_artifacts_path.unlink(missing_ok=True)
            canonical_artifacts_partial_path.unlink(missing_ok=True)
            semantic_artifacts_path.unlink(missing_ok=True)
            semantic_artifacts_partial_path.unlink(missing_ok=True)
            metadata_path.unlink()
        except FileNotFoundError as exc:
            raise UploadNotFoundError(upload_id) from exc
        except OSError as exc:
            raise UploadStorageError(
                "Staged upload could not be deleted"
            ) from exc

    def locate(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
        upload_id: str,
    ) -> StagedUpload:
        if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
            raise UploadNotFoundError(upload_id)
        project_directory = self._project_directory(agent_project_id)
        metadata_path = self._contained(
            project_directory, f"{upload_id}.metadata.json"
        )
        metadata = self._load_metadata(
            metadata_path, agent_project_id, owner_user_id, upload_id
        )
        if metadata.extension not in DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS:
            raise UploadStorageError("Staged upload metadata is invalid")
        stored_path = self._contained(
            project_directory, f"{upload_id}{metadata.extension}"
        )
        extraction_path = self._contained(
            project_directory, f"{upload_id}.extracted.json"
        )
        extraction_partial_path = self._contained(
            project_directory, f"{upload_id}.extracted.json.part"
        )
        chunks_path = self._contained(project_directory, f"{upload_id}.chunks.json")
        chunks_partial_path = self._contained(
            project_directory, f"{upload_id}.chunks.json.part"
        )
        rule_detections_path = self._contained(
            project_directory, f"{upload_id}.rule-detections.json"
        )
        rule_detections_partial_path = self._contained(
            project_directory, f"{upload_id}.rule-detections.json.part"
        )
        zero_shot_detections_path = self._contained(
            project_directory, f"{upload_id}.zero-shot-detections.json"
        )
        zero_shot_detections_partial_path = self._contained(
            project_directory, f"{upload_id}.zero-shot-detections.json.part"
        )
        hybrid_detections_path = self._contained(
            project_directory, f"{upload_id}.hybrid-detections.json"
        )
        hybrid_detections_partial_path = self._contained(
            project_directory, f"{upload_id}.hybrid-detections.json.part"
        )
        human_reviews_path = self._contained(
            project_directory, f"{upload_id}.human-reviews.json"
        )
        human_reviews_partial_path = self._contained(
            project_directory, f"{upload_id}.human-reviews.json.part"
        )
        canonical_artifacts_path = self._contained(
            project_directory, f"{upload_id}.canonical-artifacts.json"
        )
        canonical_artifacts_partial_path = self._contained(
            project_directory, f"{upload_id}.canonical-artifacts.json.part"
        )
        semantic_artifacts_path = self._contained(
            project_directory, f"{upload_id}.semantic-artifacts.json"
        )
        semantic_artifacts_partial_path = self._contained(
            project_directory, f"{upload_id}.semantic-artifacts.json.part"
        )
        try:
            if not stored_path.is_file():
                raise UploadNotFoundError(upload_id)
            digest = hashlib.sha256()
            with stored_path.open("rb") as source:
                while chunk := source.read(UPLOAD_CHUNK_SIZE):
                    digest.update(chunk)
        except UploadNotFoundError:
            raise
        except OSError as exc:
            raise UploadStorageError("Staged upload is unavailable") from exc
        if digest.hexdigest() != metadata.sha256:
            raise UploadStorageError("Staged upload failed integrity validation")
        return StagedUpload(
            metadata=metadata,
            file_path=stored_path,
            extraction_path=extraction_path,
            extraction_partial_path=extraction_partial_path,
            chunks_path=chunks_path,
            chunks_partial_path=chunks_partial_path,
            rule_detections_path=rule_detections_path,
            rule_detections_partial_path=rule_detections_partial_path,
            zero_shot_detections_path=zero_shot_detections_path,
            zero_shot_detections_partial_path=zero_shot_detections_partial_path,
            hybrid_detections_path=hybrid_detections_path,
            hybrid_detections_partial_path=hybrid_detections_partial_path,
            human_reviews_path=human_reviews_path,
            human_reviews_partial_path=human_reviews_partial_path,
            canonical_artifacts_path=canonical_artifacts_path,
            canonical_artifacts_partial_path=canonical_artifacts_partial_path,
            semantic_artifacts_path=semantic_artifacts_path,
            semantic_artifacts_partial_path=semantic_artifacts_partial_path,
        )

    def list_for_project(
        self,
        *,
        agent_project_id: str,
        owner_user_id: str,
    ) -> list[UploadedFileMetadata]:
        """Discover current trusted uploads without exposing storage paths."""
        project_directory = self._project_directory(agent_project_id)
        if not project_directory.exists():
            return []
        uploads: list[UploadedFileMetadata] = []
        try:
            metadata_paths = sorted(
                project_directory.glob("A3UP-*.metadata.json")
            )
            for metadata_path in metadata_paths:
                upload_id = metadata_path.name.removesuffix(".metadata.json")
                if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
                    continue
                metadata = self._load_metadata(
                    metadata_path,
                    agent_project_id,
                    owner_user_id,
                    upload_id,
                )
                stored_path = self._contained(
                    project_directory,
                    f"{upload_id}{metadata.extension}",
                )
                if not stored_path.is_file():
                    raise UploadStorageError(
                        "Staged upload metadata references a missing file"
                    )
                uploads.append(metadata)
        except UploadStorageError:
            raise
        except OSError as exc:
            raise UploadStorageError(
                "Staged uploads could not be discovered"
            ) from exc
        return sorted(uploads, key=lambda item: (item.created_at, item.upload_id))

    @staticmethod
    def _load_metadata(
        metadata_path: Path,
        agent_project_id: str,
        owner_user_id: str,
        upload_id: str,
    ) -> UploadedFileMetadata:
        try:
            sidecar = json.loads(metadata_path.read_text(encoding="utf-8"))
            public_metadata = {
                field: sidecar[field]
                for field in UploadedFileMetadata.model_fields
                if field in sidecar
            }
            metadata = UploadedFileMetadata.model_validate(public_metadata)
        except FileNotFoundError as exc:
            raise UploadNotFoundError(upload_id) from exc
        except (OSError, json.JSONDecodeError, ValidationError, KeyError) as exc:
            raise UploadStorageError(
                "Staged upload metadata is unavailable"
            ) from exc
        if (
            sidecar.get("agent_project_id") != agent_project_id
            or sidecar.get("owner_user_id") != owner_user_id
            or metadata.upload_id != upload_id
        ):
            raise UploadNotFoundError(upload_id)
        return metadata

    def _project_directory(self, agent_project_id: str) -> Path:
        root = self._root.resolve()
        project_directory = (root / agent_project_id / "inputs").resolve()
        try:
            project_directory.relative_to(root)
        except ValueError as exc:
            raise UploadStorageError("Unsafe upload storage path") from exc
        return project_directory

    @staticmethod
    def _contained(directory: Path, filename: str) -> Path:
        candidate = (directory / filename).resolve()
        try:
            candidate.relative_to(directory)
        except ValueError as exc:
            raise UploadStorageError("Unsafe upload storage path") from exc
        return candidate

    @staticmethod
    def _validate_name(
        filename: str | None,
        source_type: ImplementationInputSourceType,
    ) -> tuple[str, str]:
        normalized = (filename or "").replace("\\", "/").split("/")[-1]
        normalized = "".join(
            character for character in normalized if character.isprintable()
        ).strip()
        if not normalized or len(normalized) > 255:
            raise UploadValidationError("A valid filename is required")
        extension = Path(normalized).suffix.lower()
        allowed = (
            DOCUMENT_EXTENSIONS
            if source_type is ImplementationInputSourceType.DOCUMENT
            else IMAGE_EXTENSIONS
        )
        if extension not in allowed:
            raise UploadValidationError(
                f"{extension or 'unknown'} file type is not supported for "
                f"{source_type.value}"
            )
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
                if b"\x00" in content:
                    valid = False
                else:
                    decoded = content.decode("utf-8")
                    if extension == ".json":
                        json.loads(decoded)
                    valid = True
            except (UnicodeDecodeError, json.JSONDecodeError):
                valid = False
        if not valid:
            raise UploadValidationError(
                f"File content does not match the declared {extension} type"
            )

    @staticmethod
    def _cleanup(*paths: Path) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
