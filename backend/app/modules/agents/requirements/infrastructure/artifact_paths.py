"""Filesystem layout for backend-controlled Agent 1 artifacts."""

import re
from enum import StrEnum
from pathlib import Path

from app.common.id_generator import validate_id


SOURCE_ID_PATTERN = re.compile(r"^(DOC|AUD|VID)-(\d{3,})$")
SOURCE_EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9]+$")


class ArtifactPathError(ValueError):
    pass


class RequirementArtifactKind(StrEnum):
    UPLOADED_SOURCE = "UPLOADED_SOURCE"
    SOURCE_METADATA = "SOURCE_METADATA"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    DOCUMENT_RESULT = "DOCUMENT_RESULT"
    AUDIO_PROCESSING = "AUDIO_PROCESSING"
    AUDIO_RESULT = "AUDIO_RESULT"
    VIDEO_PROCESSING = "VIDEO_PROCESSING"
    VIDEO_RESULT = "VIDEO_RESULT"
    EVIDENCE_PREPARATION = "EVIDENCE_PREPARATION"
    NORMALIZED_RESULT = "NORMALIZED_RESULT"
    CHUNK_RESULT = "CHUNK_RESULT"
    WORKFLOW = "WORKFLOW"


SOURCE_ARTIFACT_SUFFIXES = {
    RequirementArtifactKind.SOURCE_METADATA: ".metadata.json",
    RequirementArtifactKind.DOCUMENT_PROCESSING: ".document-processing.json",
    RequirementArtifactKind.DOCUMENT_RESULT: ".document-result.json",
    RequirementArtifactKind.AUDIO_PROCESSING: ".audio-processing.json",
    RequirementArtifactKind.AUDIO_RESULT: ".audio-result.json",
    RequirementArtifactKind.VIDEO_PROCESSING: ".video-processing.json",
    RequirementArtifactKind.VIDEO_RESULT: ".video-result.json",
    RequirementArtifactKind.EVIDENCE_PREPARATION: ".evidence-preparation.json",
    RequirementArtifactKind.NORMALIZED_RESULT: ".normalized-result.json",
    RequirementArtifactKind.CHUNK_RESULT: ".chunk-result.json",
}
PROJECT_ARTIFACT_FILENAMES = {
    RequirementArtifactKind.WORKFLOW: "workflow.json",
}
SOURCE_CLEANUP_SIDECARS = tuple(
    kind
    for kind in SOURCE_ARTIFACT_SUFFIXES
    if kind is not RequirementArtifactKind.SOURCE_METADATA
)


class RequirementArtifactPaths:
    """Resolve typed artifact identities without exposing filename conventions."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def project_directory(self, agent_project_id: str) -> Path:
        self._validate_project_id(agent_project_id)
        return self._contained(self._root, agent_project_id)

    def inputs_directory(self, agent_project_id: str) -> Path:
        return self._contained(self.project_directory(agent_project_id), "inputs")

    def for_project(
        self,
        agent_project_id: str,
        kind: RequirementArtifactKind,
        *,
        partial: bool = False,
    ) -> Path:
        self._require_kind(kind)
        filename = PROJECT_ARTIFACT_FILENAMES.get(kind)
        if filename is None:
            raise ArtifactPathError("Artifact kind is not project-scoped")
        path = self._contained(self.project_directory(agent_project_id), filename)
        return self.partial_path(path) if partial else path

    def for_source(
        self,
        agent_project_id: str,
        source_id: str,
        kind: RequirementArtifactKind,
        *,
        extension: str | None = None,
        partial: bool = False,
    ) -> Path:
        self._validate_source_id(source_id)
        self._require_kind(kind)
        if kind is RequirementArtifactKind.UPLOADED_SOURCE:
            if extension is None or not SOURCE_EXTENSION_PATTERN.fullmatch(extension):
                raise ArtifactPathError("A safe source extension is required")
            filename = f"{source_id}{extension}"
        else:
            suffix = SOURCE_ARTIFACT_SUFFIXES.get(kind)
            if suffix is None:
                raise ArtifactPathError("Artifact kind is not source-scoped")
            filename = f"{source_id}{suffix}"
        path = self._contained(self.inputs_directory(agent_project_id), filename)
        return self.partial_path(path) if partial else path

    def source_cleanup_paths(
        self,
        agent_project_id: str,
        source_id: str,
        extension: str,
    ) -> tuple[Path, ...]:
        paths = [
            self.for_source(
                agent_project_id,
                source_id,
                RequirementArtifactKind.UPLOADED_SOURCE,
                extension=extension,
            )
        ]
        for kind in SOURCE_CLEANUP_SIDECARS:
            paths.append(self.for_source(agent_project_id, source_id, kind))
            paths.append(
                self.for_source(agent_project_id, source_id, kind, partial=True)
            )
        paths.append(
            self.for_source(
                agent_project_id,
                source_id,
                RequirementArtifactKind.SOURCE_METADATA,
            )
        )
        return tuple(paths)

    @staticmethod
    def partial_path(path: Path) -> Path:
        return path.with_suffix(path.suffix + ".part")

    @staticmethod
    def _require_kind(kind: RequirementArtifactKind) -> None:
        if not isinstance(kind, RequirementArtifactKind):
            raise ArtifactPathError("Artifact kind must be typed")

    @staticmethod
    def _validate_project_id(agent_project_id: str) -> None:
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise ArtifactPathError("Invalid Agent 1 project identity") from exc

    @staticmethod
    def _validate_source_id(source_id: str) -> None:
        if not isinstance(source_id, str) or not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise ArtifactPathError("Invalid requirement source identity")

    @staticmethod
    def _contained(directory: Path, filename: str) -> Path:
        directory = directory.resolve()
        candidate = (directory / filename).resolve()
        try:
            candidate.relative_to(directory)
        except ValueError as exc:
            raise ArtifactPathError("Artifact path escapes its storage boundary") from exc
        return candidate
