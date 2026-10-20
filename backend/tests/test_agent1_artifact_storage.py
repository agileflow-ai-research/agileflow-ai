import json

import pytest
from pydantic import BaseModel, ConfigDict

from app.modules.agents.requirements.infrastructure.artifact_paths import (
    ArtifactPathError,
    RequirementArtifactKind,
    RequirementArtifactPaths,
)
from app.modules.agents.requirements.infrastructure.artifact_store import (
    JsonArtifactStore,
    JsonArtifactStoreError,
)
from app.modules.agents.requirements.infrastructure.storage import (
    RequirementSourceStorage,
    SourceNotFoundError,
    SourceStorageError,
)


class ExampleArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    count: int


SOURCE_FILENAMES = {
    RequirementArtifactKind.SOURCE_METADATA: "DOC-001.metadata.json",
    RequirementArtifactKind.DOCUMENT_PROCESSING: "DOC-001.document-processing.json",
    RequirementArtifactKind.DOCUMENT_RESULT: "DOC-001.document-result.json",
    RequirementArtifactKind.AUDIO_PROCESSING: "DOC-001.audio-processing.json",
    RequirementArtifactKind.AUDIO_RESULT: "DOC-001.audio-result.json",
    RequirementArtifactKind.VIDEO_PROCESSING: "DOC-001.video-processing.json",
    RequirementArtifactKind.VIDEO_RESULT: "DOC-001.video-result.json",
    RequirementArtifactKind.EVIDENCE_PREPARATION: "DOC-001.evidence-preparation.json",
    RequirementArtifactKind.NORMALIZED_RESULT: "DOC-001.normalized-result.json",
    RequirementArtifactKind.CHUNK_RESULT: "DOC-001.chunk-result.json",
}


def metadata_payload(source_id: str, extension: str, source_type: str):
    return {
        "source_id": source_id,
        "source_type": source_type,
        "original_filename": f"source{extension}",
        "mime_type": "text/plain",
        "extension": extension,
        "size_bytes": 7,
        "sha256": "a" * 64,
        "status": "READY",
        "created_at": "2026-10-20T12:30:00Z",
        "agent_project_id": "AGP-020",
        "owner_user_id": "USR-001",
    }


def test_artifact_paths_preserve_every_existing_filename(tmp_path):
    paths = RequirementArtifactPaths(tmp_path)
    inputs = tmp_path.resolve() / "AGP-020" / "inputs"

    assert paths.project_directory("AGP-020") == tmp_path.resolve() / "AGP-020"
    assert paths.inputs_directory("AGP-020") == inputs
    assert paths.for_project(
        "AGP-020", RequirementArtifactKind.WORKFLOW
    ) == tmp_path.resolve() / "AGP-020" / "workflow.json"
    for kind, filename in SOURCE_FILENAMES.items():
        assert paths.for_source("AGP-020", "DOC-001", kind) == inputs / filename
        assert paths.for_source(
            "AGP-020", "DOC-001", kind, partial=True
        ) == inputs / f"{filename}.part"


@pytest.mark.parametrize(
    ("source_id", "extension", "filename"),
    [
        ("DOC-001", ".txt", "DOC-001.txt"),
        ("AUD-002", ".mp3", "AUD-002.mp3"),
        ("VID-003", ".mp4", "VID-003.mp4"),
    ],
)
def test_uploaded_doc_audio_video_paths_are_exact(
    tmp_path, source_id, extension, filename
):
    paths = RequirementArtifactPaths(tmp_path)
    expected = tmp_path.resolve() / "AGP-020" / "inputs" / filename

    assert paths.for_source(
        "AGP-020",
        source_id,
        RequirementArtifactKind.UPLOADED_SOURCE,
        extension=extension,
    ) == expected
    assert paths.for_source(
        "AGP-020",
        source_id,
        RequirementArtifactKind.UPLOADED_SOURCE,
        extension=extension,
        partial=True,
    ) == expected.with_suffix(expected.suffix + ".part")


@pytest.mark.parametrize(
    "project_id",
    ["../../escape", "AGP-020/../../escape", "AGP-000", "not-a-project"],
)
def test_artifact_paths_reject_unsafe_project_id(tmp_path, project_id):
    paths = RequirementArtifactPaths(tmp_path)
    with pytest.raises(ArtifactPathError):
        paths.for_project(project_id, RequirementArtifactKind.WORKFLOW)


@pytest.mark.parametrize("source_id", ["../../escape", "DOC-001/../x", "DOC-x"])
def test_artifact_paths_reject_unsafe_source_id(tmp_path, source_id):
    paths = RequirementArtifactPaths(tmp_path)
    with pytest.raises(ArtifactPathError):
        paths.for_source(
            "AGP-020", source_id, RequirementArtifactKind.DOCUMENT_RESULT
        )


def test_artifact_paths_reject_filename_and_scope_injection(tmp_path):
    paths = RequirementArtifactPaths(tmp_path)
    with pytest.raises(ArtifactPathError, match="typed"):
        paths.for_source("AGP-020", "DOC-001", "../../evil.json")
    with pytest.raises(ArtifactPathError, match="extension"):
        paths.for_source(
            "AGP-020",
            "DOC-001",
            RequirementArtifactKind.UPLOADED_SOURCE,
            extension="../../evil",
        )
    with pytest.raises(ArtifactPathError, match="source-scoped"):
        paths.for_source("AGP-020", "DOC-001", RequirementArtifactKind.WORKFLOW)
    with pytest.raises(ArtifactPathError, match="project-scoped"):
        paths.for_project("AGP-020", RequirementArtifactKind.CHUNK_RESULT)


def test_source_cleanup_registration_matches_existing_family(tmp_path):
    paths = RequirementArtifactPaths(tmp_path)
    cleanup = paths.source_cleanup_paths("AGP-020", "DOC-001", ".txt")

    assert len(cleanup) == 20
    assert cleanup[0].name == "DOC-001.txt"
    assert cleanup[-1].name == "DOC-001.metadata.json"
    assert all(path.is_relative_to(tmp_path.resolve()) for path in cleanup)
    assert "DOC-001.metadata.json.part" not in {path.name for path in cleanup}
    assert "DOC-001.txt.part" not in {path.name for path in cleanup}


def test_json_artifact_store_typed_round_trip_and_remove(tmp_path):
    store = JsonArtifactStore(tmp_path)
    value = ExampleArtifact(name="candidate-boundary", count=2)

    assert store.load(
        agent_project_id="AGP-020",
        source_id="DOC-001",
        kind=RequirementArtifactKind.DOCUMENT_RESULT,
        model=ExampleArtifact,
    ) is None
    store.save(
        agent_project_id="AGP-020",
        source_id="DOC-001",
        kind=RequirementArtifactKind.DOCUMENT_RESULT,
        value=value,
    )
    final_path = (
        tmp_path.resolve()
        / "AGP-020"
        / "inputs"
        / "DOC-001.document-result.json"
    )
    assert final_path.read_text(encoding="utf-8") == value.model_dump_json()
    assert not final_path.with_suffix(final_path.suffix + ".part").exists()
    assert store.load(
        agent_project_id="AGP-020",
        source_id="DOC-001",
        kind=RequirementArtifactKind.DOCUMENT_RESULT,
        model=ExampleArtifact,
    ) == value

    final_path.with_suffix(final_path.suffix + ".part").write_text(
        "partial", encoding="utf-8"
    )
    store.remove(
        agent_project_id="AGP-020",
        source_id="DOC-001",
        kind=RequirementArtifactKind.DOCUMENT_RESULT,
    )
    assert not final_path.exists()
    assert not final_path.with_suffix(final_path.suffix + ".part").exists()


@pytest.mark.parametrize("payload", ["not-json", '{"name":"missing-count"}'])
def test_json_artifact_store_wraps_malformed_and_invalid_artifacts(tmp_path, payload):
    paths = RequirementArtifactPaths(tmp_path)
    path = paths.for_source(
        "AGP-020", "DOC-001", RequirementArtifactKind.DOCUMENT_RESULT
    )
    path.parent.mkdir(parents=True)
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(JsonArtifactStoreError, match="could not be loaded"):
        JsonArtifactStore(tmp_path).load(
            agent_project_id="AGP-020",
            source_id="DOC-001",
            kind=RequirementArtifactKind.DOCUMENT_RESULT,
            model=ExampleArtifact,
        )


@pytest.mark.parametrize(
    ("source_id", "extension", "source_type"),
    [
        ("DOC-001", ".txt", "DOCUMENT"),
        ("AUD-001", ".mp3", "AUDIO"),
        ("VID-001", ".mp4", "VIDEO"),
    ],
)
def test_pre_r4_source_layout_locates_without_migration(
    tmp_path, source_id, extension, source_type
):
    paths = RequirementArtifactPaths(tmp_path)
    inputs = paths.inputs_directory("AGP-020")
    inputs.mkdir(parents=True)
    metadata_path = paths.for_source(
        "AGP-020", source_id, RequirementArtifactKind.SOURCE_METADATA
    )
    metadata_path.write_text(
        json.dumps(metadata_payload(source_id, extension, source_type)),
        encoding="utf-8",
    )
    uploaded = paths.for_source(
        "AGP-020",
        source_id,
        RequirementArtifactKind.UPLOADED_SOURCE,
        extension=extension,
    )
    uploaded.write_bytes(b"content")

    stored = RequirementSourceStorage(tmp_path).locate(
        agent_project_id="AGP-020",
        owner_user_id="USR-001",
        source_id=source_id,
    )

    assert stored.file_path == uploaded
    assert stored.processing_path.name == f"{source_id}.document-processing.json"
    assert stored.audio_result_path.name == f"{source_id}.audio-result.json"
    assert stored.video_result_path.name == f"{source_id}.video-result.json"
    assert stored.preparation_path.name == f"{source_id}.evidence-preparation.json"
    assert stored.normalized_result_path.name == f"{source_id}.normalized-result.json"
    assert stored.chunk_result_path.name == f"{source_id}.chunk-result.json"


def test_source_deletion_removes_registered_family_only(tmp_path):
    paths = RequirementArtifactPaths(tmp_path)
    cleanup = paths.source_cleanup_paths("AGP-020", "DOC-001", ".txt")
    cleanup[0].parent.mkdir(parents=True)
    for path in cleanup:
        path.write_text("artifact", encoding="utf-8")
    cleanup[-1].write_text(
        json.dumps(metadata_payload("DOC-001", ".txt", "DOCUMENT")),
        encoding="utf-8",
    )
    unrelated_source = paths.for_source(
        "AGP-020", "DOC-002", RequirementArtifactKind.DOCUMENT_RESULT
    )
    unrelated_source.write_text("keep", encoding="utf-8")
    workflow = paths.for_project("AGP-020", RequirementArtifactKind.WORKFLOW)
    workflow.write_text("keep", encoding="utf-8")
    unrelated_file = paths.inputs_directory("AGP-020") / "unrelated.json"
    unrelated_file.write_text("keep", encoding="utf-8")

    RequirementSourceStorage(tmp_path).delete(
        agent_project_id="AGP-020",
        owner_user_id="USR-001",
        source_id="DOC-001",
    )

    assert all(not path.exists() for path in cleanup)
    assert unrelated_source.read_text(encoding="utf-8") == "keep"
    assert workflow.read_text(encoding="utf-8") == "keep"
    assert unrelated_file.read_text(encoding="utf-8") == "keep"


def test_source_deletion_cannot_escape_root(tmp_path):
    outside = tmp_path.parent / "outside-agent1-artifact.txt"
    outside.write_text("keep", encoding="utf-8")
    storage = RequirementSourceStorage(tmp_path)

    with pytest.raises(SourceNotFoundError):
        storage.delete(
            agent_project_id="AGP-020",
            owner_user_id="USR-001",
            source_id="../../outside-agent1-artifact",
        )
    with pytest.raises(SourceStorageError):
        storage.list_for_project(
            agent_project_id="../../escape", owner_user_id="USR-001"
        )

    assert outside.read_text(encoding="utf-8") == "keep"
    outside.unlink()
