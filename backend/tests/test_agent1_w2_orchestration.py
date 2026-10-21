from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep

import pytest

from app.main import app
from app.modules.agents.requirements.api.dependencies import (
    get_agent1_n2_executor,
    get_evidence_preparation_service,
    get_requirement_processing_service,
    get_requirement_source_storage,
    get_requirement_workflow_storage,
    get_speech_to_text_provider,
    get_video_audio_extractor,
)
from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.processing.audio.providers.base import (
    AudioTranscriptionError,
)
from app.modules.agents.requirements.processing.video.providers.base import (
    VideoAudioExtractionError,
)
from app.modules.agents.requirements.workflow.orchestration import (
    RequirementN2OrchestrationService,
    n2_chunk_set_digest,
    n2_execution_key,
)
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_agent1_video_processing import (
    FakeSpeechToTextProvider,
    FakeVideoAudioExtractor,
)
from test_agent1_workflow import assert_workflow_response_contract
from test_standalone_foundation import FakeAgentProjectRepository, FakeAgentRunRepository


class HoldingExecutor:
    def __init__(self):
        self.tasks = []

    def submit(self, function, *args):
        self.tasks.append((function, args))
        return SimpleNamespace()

    def run_next(self):
        function, args = self.tasks.pop(0)
        function(*args)


@pytest.fixture
def w2_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    source_storage = RequirementSourceStorage(tmp_path)
    workflow_storage = RequirementWorkflowStorage(tmp_path)
    transcription = FakeSpeechToTextProvider()
    extractor = FakeVideoAudioExtractor()
    executor = HoldingExecutor()
    RequirementN2OrchestrationService._active_execution_ids.clear()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_requirement_source_storage] = lambda: source_storage
    app.dependency_overrides[get_requirement_workflow_storage] = lambda: workflow_storage
    app.dependency_overrides[get_speech_to_text_provider] = lambda: transcription
    app.dependency_overrides[get_video_audio_extractor] = lambda: extractor
    app.dependency_overrides[get_agent1_n2_executor] = lambda: executor
    try:
        yield authentication_context, runs, transcription, extractor, executor, tmp_path
    finally:
        RequirementN2OrchestrationService._active_execution_ids.clear()
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_requirement_source_storage, None)
        app.dependency_overrides.pop(get_requirement_workflow_storage, None)
        app.dependency_overrides.pop(get_speech_to_text_provider, None)
        app.dependency_overrides.pop(get_video_audio_extractor, None)
        app.dependency_overrides.pop(get_agent1_n2_executor, None)
        app.dependency_overrides.pop(get_requirement_processing_service, None)
        app.dependency_overrides.pop(get_evidence_preparation_service, None)


def create_project(client):
    response = client.post(
        "/api/v1/agent-projects",
        json={"agent_type": "REQUIREMENTS", "name": "W2", "domain": "Health"},
    )
    assert response.status_code == 201
    return response.json()["data"]["agent_project_id"]


def upload(client, project_id, source_type, filename, content, mime):
    response = client.post(
        f"/api/v1/agents/requirements/{project_id}/sources",
        data={"source_type": source_type},
        files={"file": (filename, content, mime)},
    )
    assert response.status_code == 201
    return response.json()["data"]


def select_outputs(client, project_id, outputs=("SRS",)):
    response = client.put(
        f"/api/v1/agents/requirements/{project_id}/workflow/outputs",
        json={"selected_outputs": list(outputs)},
    )
    assert response.status_code == 200
    return response.json()["data"]


def continue_n1(client, project_id):
    return client.post(
        f"/api/v1/agents/requirements/{project_id}/workflow/n1/continue"
    )


def workflow(client, project_id):
    response = client.get(f"/api/v1/agents/requirements/{project_id}/workflow")
    assert response.status_code == 200
    return response.json()["data"]


class FakeProcessingService:
    def __init__(self, *, status="COMPLETED", started=None, release=None):
        self.status = status
        self.started = started
        self.release = release
        self.calls = []

    def process(self, project_id, source_id, current_user, *, force=False):
        self.calls.append((project_id, source_id, force))
        if self.started:
            self.started.set()
        if self.release:
            self.release.wait(timeout=5)
        return SimpleNamespace(status=SimpleNamespace(value=self.status))


class FakePreparationService:
    def __init__(self, *, status="COMPLETED", chunks=True):
        self.status = status
        self.include_chunks = chunks
        self.calls = []

    def prepare(self, project_id, source_id, current_user, *, force=False):
        self.calls.append(("prepare", source_id, force))
        return SimpleNamespace(status=SimpleNamespace(value=self.status))

    def get_chunks(self, project_id, source_id, current_user):
        self.calls.append(("chunks", source_id))
        chunks = [SimpleNamespace(chunk_id="CHK-0000000000000001")] if self.include_chunks else []
        return SimpleNamespace(
            chunks=chunks,
            parent_result_fingerprint="a" * 64,
            normalizer_version="1",
            chunker=SimpleNamespace(fingerprint="b" * 64),
        )


def test_mixed_sources_queue_once_run_sequentially_and_complete(w2_context):
    authentication, runs, transcription, extractor, executor, _ = w2_context
    client = authentication.client()
    project_id = create_project(client)
    uploaded = [
        upload(client, project_id, "DOCUMENT", "requirements.txt", b"Secure booking is required.", "text/plain"),
        upload(client, project_id, "AUDIO", "interview.mp3", b"ID3\x04\x00\x00interview", "audio/mpeg"),
        upload(client, project_id, "VIDEO", "walkthrough.mp4", b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00video", "video/mp4"),
    ]
    select_outputs(client, project_id, ("SRS", "FUNCTIONAL_REQUIREMENTS"))

    first = continue_n1(client, project_id)
    replay = continue_n1(client, project_id)
    assert first.status_code == replay.status_code == 200
    queued = replay.json()["data"]
    assert queued["n1_state"] == "COMPLETE"
    assert queued["n2_execution"]["status"] == "QUEUED"
    assert queued["n2_execution_count"] == 1
    assert [item["source_id"] for item in queued["n2_execution"]["input_sources"]] == [
        item["source_id"] for item in sorted(uploaded, key=lambda item: item["source_id"])
    ]
    assert len(executor.tasks) == 1

    executor.run_next()
    completed = workflow(client, project_id)
    execution = completed["n2_execution"]
    assert execution["status"] == "COMPLETE"
    assert execution["result_summary"]["completed_source_count"] == 3
    assert execution["result_summary"]["chunk_count"] >= 3
    assert len(execution["chunk_set_digest"]) == 64
    assert all(item["preparation_status"] == "COMPLETE" for item in execution["source_progress"])
    assert transcription.calls == 2
    assert extractor.calls == 1
    assert runs.documents == {}
    for source in uploaded:
        source_id = source["source_id"]
        base = f"/api/v1/agents/requirements/{project_id}/sources/{source_id}"
        processing_status = client.get(f"{base}/processing/status")
        processing_result = client.get(f"{base}/processing/result")
        preparation_status = client.get(f"{base}/preparation/status")
        normalized_result = client.get(f"{base}/preparation/normalized")
        chunks_result = client.get(f"{base}/preparation/chunks")
        assert processing_status.status_code == 200
        assert processing_status.json()["data"]["status"] == "COMPLETED"
        assert processing_result.status_code == 200
        result_data = processing_result.json()["data"]
        assert result_data.get("text") or result_data.get("transcript")
        assert preparation_status.status_code == 200
        assert preparation_status.json()["data"]["status"] == "COMPLETED"
        assert normalized_result.status_code == 200
        assert normalized_result.json()["data"]["normalized_text"]
        assert chunks_result.status_code == 200
        assert chunks_result.json()["data"]["chunks"]
    completed_replay = continue_n1(client, project_id).json()["data"]
    assert completed_replay["n2_execution"]["execution_id"] == execution["execution_id"]
    assert completed_replay["n2_execution"]["chunk_set_digest"] == execution["chunk_set_digest"]
    assert completed_replay["n2_execution_count"] == 1
    assert completed_replay["n3_execution"] is None
    assert completed_replay["n3_execution_count"] == 0


def test_processing_failure_stops_and_retry_reuses_same_logical_key(w2_context):
    authentication, _, transcription, _, executor, _ = w2_context
    transcription.outcomes = [
        AudioTranscriptionError("provider details must not escape"),
        transcription.outcomes[0],
    ]
    client = authentication.client()
    project_id = create_project(client)
    upload(client, project_id, "AUDIO", "interview.mp3", b"ID3\x04\x00\x00interview", "audio/mpeg")
    select_outputs(client, project_id)
    continue_n1(client, project_id)
    executor.run_next()

    failed = workflow(client, project_id)["n2_execution"]
    assert failed["status"] == "FAILED"
    assert failed["error"]["code"] == "SOURCE_PROCESSING_FAILED"
    assert "provider details" not in failed["error"]["message"]
    retry = client.post(f"/api/v1/agents/requirements/{project_id}/workflow/n2/retry")
    assert retry.status_code == 200
    assert_workflow_response_contract(retry)
    retried = retry.json()["data"]["n2_execution"]
    assert retried["execution_key"] == failed["execution_key"]
    assert retried["attempt_number"] == 2
    executor.run_next()
    assert workflow(client, project_id)["n2_execution"]["status"] == "COMPLETE"


def test_preparation_failure_and_empty_chunk_result_prevent_completion(w2_context):
    authentication, _, _, _, executor, _ = w2_context
    client = authentication.client()
    project_id = create_project(client)
    upload(client, project_id, "DOCUMENT", "one.txt", b"First requirement.", "text/plain")
    select_outputs(client, project_id)
    processing = FakeProcessingService()
    preparation = FakePreparationService(status="FAILED")
    app.dependency_overrides[get_requirement_processing_service] = lambda: processing
    app.dependency_overrides[get_evidence_preparation_service] = lambda: preparation

    continue_n1(client, project_id)
    executor.run_next()
    failed = workflow(client, project_id)["n2_execution"]
    assert failed["status"] == "FAILED"
    assert failed["error"]["code"] == "EVIDENCE_PREPARATION_FAILED"
    assert processing.calls == [(project_id, "DOC-001", False)]
    assert preparation.calls == [("prepare", "DOC-001", False)]

    preparation.status = "COMPLETED"
    preparation.include_chunks = False
    retry = client.post(f"/api/v1/agents/requirements/{project_id}/workflow/n2/retry")
    assert retry.status_code == 200
    executor.run_next()
    invalid = workflow(client, project_id)["n2_execution"]
    assert invalid["status"] == "FAILED"
    assert invalid["error"]["code"] == "N2_RESULT_INVALID"


def test_running_replay_and_retry_return_existing_execution(w2_context):
    authentication, _, _, _, _, _ = w2_context
    started = Event()
    release = Event()
    processing = FakeProcessingService(started=started, release=release)
    preparation = FakePreparationService()
    pool = ThreadPoolExecutor(max_workers=1)
    app.dependency_overrides[get_requirement_processing_service] = lambda: processing
    app.dependency_overrides[get_evidence_preparation_service] = lambda: preparation
    app.dependency_overrides[get_agent1_n2_executor] = lambda: pool
    client = authentication.client()
    project_id = create_project(client)
    upload(client, project_id, "DOCUMENT", "one.txt", b"First requirement.", "text/plain")
    select_outputs(client, project_id)

    initial = continue_n1(client, project_id).json()["data"]["n2_execution"]
    assert started.wait(timeout=2)
    running = workflow(client, project_id)
    assert running["n2_execution"]["status"] == "RUNNING"
    replay = continue_n1(client, project_id).json()["data"]
    retry = client.post(f"/api/v1/agents/requirements/{project_id}/workflow/n2/retry").json()["data"]
    assert replay["n2_execution"]["execution_id"] == initial["execution_id"]
    assert retry["n2_execution"]["execution_id"] == initial["execution_id"]
    assert replay["n2_execution_count"] == retry["n2_execution_count"] == 1

    release.set()
    for _ in range(50):
        if workflow(client, project_id)["n2_execution"]["status"] == "COMPLETE":
            break
        sleep(0.02)
    assert workflow(client, project_id)["n2_execution"]["status"] == "COMPLETE"
    pool.shutdown(wait=True)


def test_concurrent_same_input_continue_creates_one_execution(w2_context):
    authentication, _, _, _, executor, _ = w2_context
    owner = authentication.client()
    project_id = create_project(owner)
    upload(owner, project_id, "DOCUMENT", "one.txt", b"First requirement.", "text/plain")
    select_outputs(owner, project_id)

    def start():
        return continue_n1(authentication.client(), project_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: start(), range(2)))
    assert all(response.status_code == 200 for response in responses)
    execution_ids = {
        response.json()["data"]["n2_execution"]["execution_id"]
        for response in responses
    }
    assert len(execution_ids) == 1
    assert workflow(owner, project_id)["n2_execution_count"] == 1
    assert len(executor.tasks) == 1


def test_retry_reuses_compatible_completed_modality_results(w2_context):
    authentication, _, transcription, extractor, executor, _ = w2_context
    extractor.outcomes = [VideoAudioExtractionError("first failure"), None]
    client = authentication.client()
    project_id = create_project(client)
    upload(client, project_id, "AUDIO", "interview.mp3", b"ID3\x04\x00\x00interview", "audio/mpeg")
    upload(client, project_id, "VIDEO", "walkthrough.mp4", b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00video", "video/mp4")
    select_outputs(client, project_id)
    continue_n1(client, project_id)
    executor.run_next()
    assert workflow(client, project_id)["n2_execution"]["status"] == "FAILED"
    assert transcription.calls == 1

    client.post(f"/api/v1/agents/requirements/{project_id}/workflow/n2/retry")
    executor.run_next()
    assert workflow(client, project_id)["n2_execution"]["status"] == "COMPLETE"
    # Audio is reused; only the recovered video adds a second transcription.
    assert transcription.calls == 2


def test_stale_source_snapshot_blocks_old_execution_and_new_confirmation_gets_new_key(w2_context):
    authentication, _, _, _, executor, _ = w2_context
    client = authentication.client()
    project_id = create_project(client)
    upload(client, project_id, "DOCUMENT", "one.txt", b"First requirement.", "text/plain")
    select_outputs(client, project_id)
    queued = continue_n1(client, project_id).json()["data"]["n2_execution"]

    upload(client, project_id, "DOCUMENT", "two.txt", b"Second requirement.", "text/plain")
    executor.run_next()
    stale = workflow(client, project_id)
    assert stale["n1_state"] == "WAITING_FOR_HUMAN"
    assert stale["n2_is_current"] is False
    assert stale["n2_execution"]["status"] == "BLOCKED"
    assert stale["n2_execution"]["error"]["code"] == "N2_INPUT_STALE"

    refreshed = continue_n1(client, project_id).json()["data"]
    assert refreshed["n2_execution"]["execution_key"] != queued["execution_key"]
    assert refreshed["n2_execution_count"] == 2


def test_output_change_requires_reconfirmation_and_creates_new_input_identity(w2_context):
    authentication, _, _, _, executor, _ = w2_context
    client = authentication.client()
    project_id = create_project(client)
    upload(client, project_id, "DOCUMENT", "one.txt", b"First requirement.", "text/plain")
    select_outputs(client, project_id, ("SRS",))
    continue_n1(client, project_id)
    executor.run_next()
    first = workflow(client, project_id)["n2_execution"]

    changed = select_outputs(client, project_id, ("FUNCTIONAL_REQUIREMENTS",))
    assert changed["n1_state"] == "WAITING_FOR_HUMAN"
    assert changed["n2_is_current"] is False
    stale_retry = client.post(f"/api/v1/agents/requirements/{project_id}/workflow/n2/retry")
    assert stale_retry.status_code == 409
    second = continue_n1(client, project_id).json()["data"]["n2_execution"]
    assert second["execution_key"] != first["execution_key"]


def test_interrupted_active_state_reconciles_to_retryable_failure(w2_context):
    authentication, _, _, _, _, _ = w2_context
    client = authentication.client()
    project_id = create_project(client)
    upload(client, project_id, "DOCUMENT", "one.txt", b"First requirement.", "text/plain")
    select_outputs(client, project_id)
    queued = continue_n1(client, project_id).json()["data"]["n2_execution"]
    RequirementN2OrchestrationService._active_execution_ids.discard(queued["execution_id"])

    reconciled = workflow(client, project_id)["n2_execution"]
    assert reconciled["status"] == "FAILED"
    assert reconciled["retryable"] is True
    assert reconciled["error"]["code"] == "N2_EXECUTION_INTERRUPTED"


def test_execution_and_chunk_fingerprints_are_deterministic():
    key = n2_execution_key("AGP-001", "a" * 64, "b" * 64)
    assert key == n2_execution_key("AGP-001", "a" * 64, "b" * 64)
    assert key != n2_execution_key("AGP-001", "c" * 64, "b" * 64)
    sources = [
        {"source_id": "DOC-002", "chunk_ids": ["CHK-B"]},
        {"source_id": "DOC-001", "chunk_ids": ["CHK-A"]},
    ]
    assert n2_chunk_set_digest("a" * 64, sources) == n2_chunk_set_digest(
        "a" * 64, list(reversed(sources))
    )
