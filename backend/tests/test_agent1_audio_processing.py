import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.main import app
from app.modules.agents.requirements.api.dependencies import (
    get_requirement_source_storage,
    get_speech_to_text_provider,
)
from app.modules.agents.requirements.infrastructure.storage import (
    RequirementSourceStorage,
)
from app.modules.agents.requirements.processing.audio.providers.base import (
    AudioTranscriptionError,
    AudioUnreadableError,
    SpeechToTextConfiguration,
    SpeechToTextProviderNotConfiguredError,
    SpeechToTextResult,
    SpeechToTextSegment,
)
from app.modules.agents.requirements.processing.audio.providers.faster_whisper import (
    FasterWhisperProvider,
)
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


class FakeSpeechToTextProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.outcomes = [
            SpeechToTextResult(
                transcript=" Welcome to the interview.",
                segments=(
                    SpeechToTextSegment(0.0, 1.25, " Welcome"),
                    SpeechToTextSegment(1.25, 2.5, " to the interview."),
                ),
                detected_language="en",
                language_probability=0.97,
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
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def audio_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    storage = RequirementSourceStorage(tmp_path)
    provider = FakeSpeechToTextProvider()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_requirement_source_storage] = lambda: storage
    app.dependency_overrides[get_speech_to_text_provider] = lambda: provider
    try:
        yield authentication_context, projects, runs, tmp_path, provider
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_requirement_source_storage, None)
        app.dependency_overrides.pop(get_speech_to_text_provider, None)


def create_project(client, agent_type="REQUIREMENTS"):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": agent_type, "name": "Audio Discovery", "domain": "Health"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def audio_bytes(extension):
    return {
        ".mp3": b"ID3\x04\x00\x00interview",
        ".wav": b"RIFF\x24\x00\x00\x00WAVEfmt audio",
        ".m4a": b"\x00\x00\x00\x18ftypM4A audio",
    }[extension]


def upload(client, project_id, extension=".mp3"):
    return client.post(
        f"/api/v1/agents/requirements/{project_id}/sources",
        data={"source_type": "AUDIO"},
        files={"file": (f"interview{extension}", audio_bytes(extension), "application/octet-stream")},
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


@pytest.mark.parametrize("extension", [".mp3", ".wav", ".m4a"])
def test_audio_formats_transcribe_with_segments_and_language(audio_context, extension):
    authentication, _, runs, root, provider = audio_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source = upload(client, project_id, extension).json()["data"]

    assert status(client, project_id, source["source_id"]).json()["data"]["status"] == "READY"
    assert process(client, project_id, source["source_id"]).json()["data"]["status"] == "COMPLETED"
    payload = result(client, project_id, source["source_id"]).json()["data"]

    assert payload["source_id"] == "AUD-001"
    assert payload["transcript"] == " Welcome to the interview."
    assert payload["segments"] == [
        {"start_seconds": 0.0, "end_seconds": 1.25, "text": " Welcome"},
        {"start_seconds": 1.25, "end_seconds": 2.5, "text": " to the interview."},
    ]
    assert payload["detected_language"] == "en"
    assert payload["language_probability"] == 0.97
    assert payload["transcription"]["model_name"] == "fake-small"
    processing_sidecar = json.loads(
        (root / project_id / "inputs" / "AUD-001.audio-processing.json").read_text(
            encoding="utf-8"
        )
    )
    result_sidecar = json.loads(
        (root / project_id / "inputs" / "AUD-001.audio-result.json").read_text(
            encoding="utf-8"
        )
    )
    assert processing_sidecar["status"] == "COMPLETED"
    assert processing_sidecar["source_id"] == source["source_id"]
    assert processing_sidecar["agent_project_id"] == project_id
    assert processing_sidecar["source_sha256"] == source["sha256"]
    assert result_sidecar["source_id"] == source["source_id"]
    assert result_sidecar["agent_project_id"] == project_id
    assert result_sidecar["source_sha256"] == source["sha256"]
    assert result_sidecar["processor_version"] == "1"
    assert result_sidecar["transcription"]["fingerprint"] == "a" * 64
    assert provider.calls == 1
    assert runs.documents == {}


@pytest.mark.parametrize(
    "exception,code",
    [
        (SpeechToTextProviderNotConfiguredError("missing"), "TRANSCRIPTION_PROVIDER_NOT_CONFIGURED"),
        (AudioUnreadableError("decoder path C:/secret"), "AUDIO_UNREADABLE"),
        (AudioTranscriptionError("raw model stack"), "AUDIO_TRANSCRIPTION_FAILED"),
    ],
)
def test_provider_failures_use_safe_codes(audio_context, exception, code):
    authentication, _, _, _, provider = audio_context
    provider.outcomes = [exception]
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_id = upload(client, project_id).json()["data"]["source_id"]

    record = process(client, project_id, source_id).json()["data"]

    assert record["status"] == "FAILED"
    assert record["error"]["code"] == code
    assert "secret" not in json.dumps(record).lower()
    assert "stack" not in json.dumps(record).lower()
    assert result(client, project_id, source_id).status_code == 404


def test_empty_transcript_is_retryable(audio_context):
    authentication, _, _, _, provider = audio_context
    provider.outcomes = [
        SpeechToTextResult("   ", (), "en", 0.5),
        SpeechToTextResult(" Retry succeeded", (SpeechToTextSegment(0, 1, " Retry succeeded"),)),
    ]
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_id = upload(client, project_id).json()["data"]["source_id"]

    failed = process(client, project_id, source_id).json()["data"]
    retried = process(client, project_id, source_id).json()["data"]

    assert failed["error"]["code"] == "NO_USABLE_TRANSCRIPT"
    assert retried["status"] == "COMPLETED"
    assert provider.calls == 2


def test_completed_result_reuse_and_force_reprocessing(audio_context):
    authentication, _, _, _, provider = audio_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source_id = upload(client, project_id).json()["data"]["source_id"]

    process(client, project_id, source_id)
    process(client, project_id, source_id)
    assert provider.calls == 1
    process(client, project_id, source_id, force=True)
    assert provider.calls == 2


def test_checksum_version_and_configuration_bind_results(audio_context):
    authentication, _, _, root, provider = audio_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source = upload(client, project_id).json()["data"]
    process(client, project_id, source["source_id"])
    directory = root / project_id / "inputs"
    processing_path = directory / "AUD-001.audio-processing.json"
    result_path = directory / "AUD-001.audio-result.json"

    result_path.write_text(
        result_path.read_text(encoding="utf-8").replace(source["sha256"], "0" * 64),
        encoding="utf-8",
    )
    assert result(client, project_id, source["source_id"]).status_code == 404
    process(client, project_id, source["source_id"])

    processing_path.write_text(
        processing_path.read_text(encoding="utf-8").replace(
            '"processor_version":"1"', '"processor_version":"999"'
        ),
        encoding="utf-8",
    )
    assert status(client, project_id, source["source_id"]).json()["data"]["status"] == "READY"

    provider.configuration = replace(provider.configuration, fingerprint="b" * 64)
    assert result(client, project_id, source["source_id"]).status_code == 404


def test_checksum_failure_preserves_source_metadata_and_creates_no_run(audio_context):
    authentication, _, runs, root, _ = audio_context
    client = authentication.client()
    project_id = create_project(client)["agent_project_id"]
    source = upload(client, project_id).json()["data"]
    directory = root / project_id / "inputs"
    metadata_path = directory / "AUD-001.metadata.json"
    before = metadata_path.read_bytes()
    (directory / "AUD-001.mp3").write_bytes(b"ID3\x04\x00\x00changed")

    record = process(client, project_id, source["source_id"]).json()["data"]

    assert record["error"]["code"] == "SOURCE_CHECKSUM_MISMATCH"
    assert metadata_path.read_bytes() == before
    assert runs.documents == {}


def test_audio_ownership_type_archive_guards_and_reload(audio_context):
    authentication, _, _, root, _ = audio_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project_id = create_project(owner)["agent_project_id"]
    source = upload(owner, project_id).json()["data"]

    assert process(foreign, project_id, source["source_id"]).status_code == 404
    document = owner.post(
        f"/api/v1/agents/requirements/{project_id}/sources",
        data={"source_type": "DOCUMENT"},
        files={"file": ("notes.txt", b"notes", "text/plain")},
    ).json()["data"]
    assert status(owner, project_id, document["source_id"]).status_code == 200
    wrong_id = create_project(owner, "IMPLEMENTATION")["agent_project_id"]
    assert status(owner, wrong_id, "AUD-001").status_code == 422

    before = owner.get(f"/api/v1/agents/requirements/{project_id}/sources").json()["data"]
    process(owner, project_id, source["source_id"])
    after = owner.get(f"/api/v1/agents/requirements/{project_id}/sources").json()["data"]
    assert after == before
    app.dependency_overrides[get_requirement_source_storage] = lambda: RequirementSourceStorage(root)
    assert status(owner, project_id, source["source_id"]).json()["data"]["status"] == "COMPLETED"

    owner.patch(f"/api/v1/agent-projects/{project_id}", json={"status": "ARCHIVED"})
    assert process(owner, project_id, source["source_id"]).status_code == 409
    assert status(owner, project_id, source["source_id"]).status_code == 409
    assert result(owner, project_id, source["source_id"]).status_code == 409


def test_faster_whisper_model_construction_is_lazy_and_cached(monkeypatch, tmp_path):
    constructions = []

    class FakeWhisperModel:
        def __init__(self, model_name, *, device, compute_type):
            constructions.append((model_name, device, compute_type))

        def transcribe(self, audio_path, *, language):
            assert audio_path == str(tmp_path / "sample.wav")
            assert language is None
            return (
                [SimpleNamespace(start=0, end=1, text=" Local transcript")],
                SimpleNamespace(language="en", language_probability=0.99),
            )

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    provider = FasterWhisperProvider(
        model_name="small", device="cpu", compute_type="int8"
    )

    assert constructions == []
    provider.transcribe(Path(tmp_path / "sample.wav"))
    provider.transcribe(Path(tmp_path / "sample.wav"))

    assert constructions == [("small", "cpu", "int8")]
