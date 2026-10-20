import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.main import app
from app.modules.agents.requirements.api.dependencies import (
    get_requirement_source_storage,
    get_speech_to_text_provider,
    get_video_audio_extractor,
)
from app.modules.agents.requirements.infrastructure.storage import (
    RequirementSourceStorage,
)
from app.modules.agents.requirements.processing.audio.providers.base import (
    AudioTranscriptionError,
    SpeechToTextConfiguration,
    SpeechToTextResult,
    SpeechToTextSegment,
)
from app.modules.agents.requirements.processing.facade import (
    RequirementProcessingService,
)
from app.modules.agents.requirements.processing.video.providers.base import (
    VideoAudioExtractionConfiguration,
    VideoAudioExtractionError,
    VideoNoAudioTrackError,
)
from app.modules.agents.requirements.processing.video.providers.ffmpeg import (
    FFmpegAudioExtractor,
)
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


VIDEO_BYTES = {
    ".mp4": b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00video",
    ".mov": b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00video",
    ".webm": b"\x1aE\xdf\xa3webm-video",
}


class FakeVideoAudioExtractor:
    def __init__(self) -> None:
        self.calls = 0
        self.outcomes = [None]
        self.output_paths = []
        self.before_extract = None
        self.configuration = VideoAudioExtractionConfiguration(
            provider="fake_ffmpeg",
            provider_version="test-1",
            executable="fake-ffmpeg",
            timeout_seconds=10,
            sample_rate_hz=16_000,
            channels=1,
            fingerprint="b" * 64,
        )

    def extract_audio(self, input_video_path, output_audio_path):
        assert input_video_path.is_file()
        self.calls += 1
        self.output_paths.append(output_audio_path)
        if self.before_extract:
            self.before_extract()
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            output_audio_path.write_bytes(b"partial")
            raise outcome
        output_audio_path.write_bytes(b"RIFFfake-wave")


class FakeSpeechToTextProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.input_paths = []
        self.outcomes = [
            SpeechToTextResult(
                transcript=" Video interview transcript.",
                segments=(
                    SpeechToTextSegment(0, 1.5, " Video interview"),
                    SpeechToTextSegment(1.5, 2.75, " transcript."),
                ),
                detected_language="en",
                language_probability=0.98,
            )
        ]
        self.configuration = SpeechToTextConfiguration(
            provider="fake",
            provider_version="test-1",
            model_name="fake-small",
            device="cpu",
            compute_type="int8",
            language=None,
            fingerprint="a" * 64,
        )

    def transcribe(self, audio_path):
        assert audio_path.is_file()
        self.calls += 1
        self.input_paths.append(audio_path)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def video_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    storage = RequirementSourceStorage(tmp_path)
    extractor = FakeVideoAudioExtractor()
    transcription = FakeSpeechToTextProvider()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_requirement_source_storage] = lambda: storage
    app.dependency_overrides[get_video_audio_extractor] = lambda: extractor
    app.dependency_overrides[get_speech_to_text_provider] = lambda: transcription
    try:
        yield authentication_context, projects, runs, tmp_path, extractor, transcription
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_requirement_source_storage, None)
        app.dependency_overrides.pop(get_video_audio_extractor, None)
        app.dependency_overrides.pop(get_speech_to_text_provider, None)


def create_project(client, agent_type="REQUIREMENTS"):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": agent_type, "name": "Video Discovery", "domain": "Health"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def upload(client, project_id, extension=".mp4", source_type="VIDEO"):
    content = VIDEO_BYTES.get(extension, b"unsupported-video")
    return client.post(
        f"/api/v1/agents/requirements/{project_id}/sources",
        data={"source_type": source_type},
        files={"file": (f"workflow{extension}", content, "application/octet-stream")},
    )


def process(client, project_id, source_id, *, force=False):
    suffix = "?force=true" if force else ""
    return client.post(
        f"/api/v1/agents/requirements/{project_id}/sources/{source_id}/processing{suffix}"
    )


def status(client, project_id, source_id):
    return client.get(
        f"/api/v1/agents/requirements/{project_id}/sources/{source_id}/processing/status"
    )


def result(client, project_id, source_id):
    return client.get(
        f"/api/v1/agents/requirements/{project_id}/sources/{source_id}/processing/result"
    )


@pytest.mark.parametrize("extension", [".mp4", ".mov", ".webm"])
def test_video_formats_extract_transcribe_persist_and_cleanup(video_context, extension):
    authentication, _, runs, root, extractor, transcription = video_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source = upload(client, project_id, extension).json()["data"]
    directory = root / project_id / "inputs"

    extractor.before_extract = lambda: (
        json.loads((directory / "VID-001.video-processing.json").read_text())["status"]
        == "PROCESSING"
    ) or pytest.fail("PROCESSING was not persisted")
    assert status(client, project_id, source["source_id"]).json()["data"]["status"] == "READY"
    completed = process(client, project_id, source["source_id"])
    payload = result(client, project_id, source["source_id"]).json()["data"]

    assert completed.json()["data"]["status"] == "COMPLETED"
    assert extractor.calls == transcription.calls == 1
    assert transcription.input_paths == extractor.output_paths
    assert not extractor.output_paths[0].exists()
    assert payload["source_id"] == "VID-001"
    assert payload["agent_project_id"] == project_id
    assert payload["source_sha256"] == source["sha256"]
    assert payload["original_filename"] == f"workflow{extension}"
    assert payload["transcript"] == " Video interview transcript."
    assert payload["segments"][1] == {
        "start_seconds": 1.5,
        "end_seconds": 2.75,
        "text": " transcript.",
    }
    assert payload["detected_language"] == "en"
    assert payload["language_probability"] == 0.98
    assert json.loads((directory / "VID-001.video-processing.json").read_text())["status"] == "COMPLETED"
    persisted = json.loads((directory / "VID-001.video-result.json").read_text())
    assert persisted["source_id"] == source["source_id"]
    assert persisted["agent_project_id"] == project_id
    assert persisted["source_sha256"] == source["sha256"]
    assert persisted["extraction"]["fingerprint"] == "b" * 64
    assert persisted["transcription"]["fingerprint"] == "a" * 64
    assert runs.documents == {}


def test_completed_result_is_reused_and_force_reruns_both_providers(video_context):
    authentication, _, _, _, extractor, transcription = video_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_id = upload(client, project_id).json()["data"]["source_id"]

    process(client, project_id, source_id)
    process(client, project_id, source_id)
    assert extractor.calls == transcription.calls == 1
    process(client, project_id, source_id, force=True)
    assert extractor.calls == transcription.calls == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "deleted",
        "corrupt",
        "stale_source",
        "stale_checksum",
        "stale_processor",
        "stale_model",
        "stale_extraction",
    ],
)
def test_completed_video_status_reconciles_invalid_result_and_retries(
    video_context, mutation
):
    authentication, _, _, root, extractor, transcription = video_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source = upload(client, project_id).json()["data"]
    source_id = source["source_id"]
    process(client, project_id, source_id)
    result_path = root / project_id / "inputs" / "VID-001.video-result.json"

    if mutation == "deleted":
        result_path.unlink()
    elif mutation == "corrupt":
        result_path.write_text("{not-json", encoding="utf-8")
    else:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if mutation == "stale_source":
            payload["source_id"] = "VID-999"
        elif mutation == "stale_checksum":
            payload["source_sha256"] = "0" * 64
        elif mutation == "stale_processor":
            payload["processor_version"] = "999"
        elif mutation == "stale_model":
            payload["transcription"]["fingerprint"] = "c" * 64
        else:
            payload["extraction"]["fingerprint"] = "d" * 64
        result_path.write_text(json.dumps(payload), encoding="utf-8")

    reconciled = status(client, project_id, source_id).json()["data"]

    assert reconciled["status"] == "FAILED"
    assert reconciled["error"]["code"] == "PROCESSING_RESULT_INVALID"
    assert "not-json" not in json.dumps(reconciled)
    persisted = json.loads(
        (root / project_id / "inputs" / "VID-001.video-processing.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["status"] == "FAILED"
    assert result(client, project_id, source_id).status_code == 404
    assert process(client, project_id, source_id).json()["data"]["status"] == "COMPLETED"
    assert extractor.calls == transcription.calls == 2


@pytest.mark.parametrize(
    "exception,code",
    [
        (VideoAudioExtractionError("raw ffmpeg stderr C:/secret"), "VIDEO_AUDIO_EXTRACTION_FAILED"),
        (VideoNoAudioTrackError("no stream"), "VIDEO_NO_AUDIO_TRACK"),
    ],
)
def test_extraction_failures_are_safe_retryable_and_cleaned(video_context, exception, code):
    authentication, _, _, _, extractor, transcription = video_context
    extractor.outcomes = [exception, None]
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_id = upload(client, project_id).json()["data"]["source_id"]

    failed = process(client, project_id, source_id).json()["data"]
    assert failed["status"] == "FAILED"
    assert failed["error"]["code"] == code
    assert "secret" not in json.dumps(failed).lower()
    assert not extractor.output_paths[0].exists()
    assert transcription.calls == 0

    retried = process(client, project_id, source_id).json()["data"]
    assert retried["status"] == "COMPLETED"
    assert extractor.calls == 2


def test_transcription_failure_is_safe_and_temp_audio_is_cleaned(video_context):
    authentication, _, _, _, extractor, transcription = video_context
    transcription.outcomes = [AudioTranscriptionError("raw stack"), transcription.outcomes[0]]
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_id = upload(client, project_id).json()["data"]["source_id"]

    failed = process(client, project_id, source_id).json()["data"]

    assert failed["error"]["code"] == "VIDEO_TRANSCRIPTION_FAILED"
    assert not extractor.output_paths[0].exists()
    assert result(client, project_id, source_id).status_code == 404
    assert process(client, project_id, source_id).json()["data"]["status"] == "COMPLETED"


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing", "VIDEO_FILE_MISSING"),
        ("empty", "VIDEO_EMPTY"),
        ("changed", "VIDEO_CHECKSUM_MISMATCH"),
        ("unsupported", "VIDEO_UNSUPPORTED_FORMAT"),
    ],
)
def test_stored_video_validation_failures(video_context, mutation, code):
    authentication, _, _, root, extractor, _ = video_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source = upload(client, project_id).json()["data"]
    directory = root / project_id / "inputs"
    video_path = directory / "VID-001.mp4"
    if mutation == "missing":
        video_path.unlink()
    elif mutation == "empty":
        video_path.write_bytes(b"")
    elif mutation == "changed":
        video_path.write_bytes(VIDEO_BYTES[".mp4"] + b"changed")
    else:
        metadata_path = directory / "VID-001.metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata.update(extension=".avi", mime_type="video/x-msvideo")
        metadata_path.write_text(json.dumps(metadata))
        video_path.rename(directory / "VID-001.avi")

    response = process(client, project_id, source["source_id"])

    assert response.status_code == 200
    assert response.json()["data"]["error"]["code"] == code
    assert extractor.calls == 0


def test_binding_guards_metadata_immutability_and_no_agent_run(video_context):
    authentication, _, runs, root, _, _ = video_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project_id = create_project(owner)["agent_project_id"]
    source = upload(owner, project_id).json()["data"]
    directory = root / project_id / "inputs"
    metadata_path = directory / "VID-001.metadata.json"
    before = metadata_path.read_bytes()

    assert process(foreign, project_id, source["source_id"]).status_code == 404
    wrong_id = create_project(owner, "IMPLEMENTATION")["agent_project_id"]
    assert status(owner, wrong_id, "VID-001").status_code == 422
    process(owner, project_id, source["source_id"])
    result_path = directory / "VID-001.video-result.json"
    result_path.write_text(
        result_path.read_text().replace(project_id, "AGP-999"), encoding="utf-8"
    )
    assert result(owner, project_id, source["source_id"]).status_code == 404
    assert metadata_path.read_bytes() == before
    assert runs.documents == {}

    owner.patch(f"/api/v1/agent-projects/{project_id}", json={"status": "ARCHIVED"})
    assert process(owner, project_id, source["source_id"]).status_code == 409
    assert status(owner, project_id, source["source_id"]).status_code == 409
    assert result(owner, project_id, source["source_id"]).status_code == 409


def test_vid_dispatch_rejects_tampered_non_video_source_type(video_context):
    authentication, _, _, root, extractor, _ = video_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_id = upload(client, project_id).json()["data"]["source_id"]
    metadata_path = root / project_id / "inputs" / "VID-001.metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["source_type"] = "AUDIO"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    response = process(client, project_id, source_id)

    assert response.status_code == 422
    assert extractor.calls == 0


def test_dispatcher_routes_all_three_source_id_families():
    documents, audio, video = object(), object(), object()
    dispatcher = RequirementProcessingService(documents, audio, video)

    assert dispatcher._service("DOC-001") is documents
    assert dispatcher._service("AUD-001") is audio
    assert dispatcher._service("VID-001") is video


def test_ffmpeg_extractor_uses_safe_fixed_command(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **options):
        calls.append((command, options))
        Path(command[-1]).write_bytes(b"RIFFfake")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)
    extractor = FFmpegAudioExtractor(
        executable="C:/tools/ffmpeg.exe", timeout_seconds=12
    )
    input_path = tmp_path / "source.mp4"
    output_path = tmp_path / "audio.wav"
    input_path.write_bytes(VIDEO_BYTES[".mp4"])

    extractor.extract_audio(input_path, output_path)

    command, options = calls[0]
    assert command[0] == "C:/tools/ffmpeg.exe"
    assert command[1:] == [
        "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(input_path),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-f", "wav",
        "-n", str(output_path),
    ]
    assert options["shell"] is False
    assert options["timeout"] == 12
    assert extractor.configuration.executable == "ffmpeg.exe"
    assert "tools" not in str(extractor.configuration)
