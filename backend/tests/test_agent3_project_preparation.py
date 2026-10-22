from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.main import app

from app.common.status import AgentProjectStatus, AgentType
from app.modules.agents.implementation.contracts.enums import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
)
from app.modules.agents.implementation.contracts.schemas import (
    UploadedFileMetadata,
)
from app.modules.agents.implementation.inputs.extraction.schemas import (
    ExtractionStatus,
)
from app.modules.agents.implementation.inputs.upload.service import (
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.preparation.orchestration import (
    service as orchestration_service,
)
from app.modules.agents.implementation.preparation.classification.zero_shot.schemas import (
    ZeroShotStatus,
)
from app.modules.agents.implementation.preparation.orchestration.constants import (
    PreparationStage,
    ProjectPreparationStatus,
    SourcePreparationStatus,
)
from app.modules.agents.implementation.preparation.orchestration.schemas import (
    PersistedPreparationSource,
    PreparationTextInput,
    ProjectPreparationStartRequest,
    ProjectPreparationStatusResponse,
)
from app.modules.agents.implementation.preparation.orchestration.status import (
    derive_project_status,
)
from app.modules.agents.implementation.api.dependencies import (
    get_project_preparation_service,
)
from app.modules.agents.implementation.preparation.orchestration.service import (
    ProjectPreparationService,
)
from app.modules.agents.implementation.preparation.orchestration.storage import (
    ProjectPreparationStorage,
)
from app.modules.agents.implementation.preparation.schemas import ChunkingStatus
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.schemas import AgentProject
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
)


NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


class InlineExecutor:
    def submit(self, fn, *args):
        fn(*args)
        return SimpleNamespace()


class HoldingExecutor:
    def __init__(self):
        self.calls = []

    def submit(self, fn, *args):
        self.calls.append((fn, args))
        return SimpleNamespace()


class StandaloneStub:
    def __init__(self):
        self.project = AgentProject(
            agent_project_id="AGP-003",
            owner_user_id="USR-001",
            agent_type=AgentType.IMPLEMENTATION,
            name="Implementation",
            domain="Research",
            status=AgentProjectStatus.ACTIVE,
            created_at=NOW,
            updated_at=NOW,
        )

    def require_active_project(self, owner_user_id, agent_project_id):
        assert owner_user_id == self.project.owner_user_id
        assert agent_project_id == self.project.agent_project_id
        return self.project


class UploadStorageStub:
    def __init__(self, uploads):
        self.uploads = uploads

    def list_for_project(self, *, agent_project_id, owner_user_id):
        assert agent_project_id == "AGP-003"
        assert owner_user_id == "USR-001"
        return list(self.uploads)


class StageStub:
    def __init__(self, status=None, fail_ids=()):
        self.status = status
        self.fail_ids = set(fail_ids)
        self.calls = []

    def build(self, agent_project_id, source_id, current_user):
        self.calls.append(source_id)
        if source_id in self.fail_ids:
            raise RuntimeError("unsafe internal detail")
        return SimpleNamespace(status=self.status)

    extract = build


class CachingStageStub(StageStub):
    def __init__(self, status=None):
        super().__init__(status)
        self.computed = set()
        self.computation_count = 0

    def build(self, agent_project_id, source_id, current_user):
        self.calls.append(source_id)
        if source_id not in self.computed:
            self.computed.add(source_id)
            self.computation_count += 1
        return SimpleNamespace(status=self.status)

    def extract(self, agent_project_id, source_id, current_user):
        return self.build(agent_project_id, source_id, current_user)


class ReviewStub:
    def __init__(self, complete_ids=()):
        self.complete_ids = set(complete_ids)

    def get_state(self, agent_project_id, source_id, current_user):
        value = "COMPLETE" if source_id in self.complete_ids else "IN_PROGRESS"
        return SimpleNamespace(review=SimpleNamespace(review_status=SimpleNamespace(value=value)))


def upload(index, source_type=ImplementationInputSourceType.DOCUMENT):
    return UploadedFileMetadata(
        upload_id=f"A3UP-{index:032x}",
        source_type=source_type,
        artifact_type=ImplementationArtifactType.FUNCTIONAL_REQUIREMENTS,
        label=None,
        original_filename=f"source-{index}.{'png' if source_type is ImplementationInputSourceType.IMAGE else 'pdf'}",
        mime_type="image/png" if source_type is ImplementationInputSourceType.IMAGE else "application/pdf",
        extension=".png" if source_type is ImplementationInputSourceType.IMAGE else ".pdf",
        size_bytes=100,
        sha256=f"{index:064x}",
        created_at=NOW,
    )


@pytest.fixture(autouse=True)
def clear_running_projects():
    ProjectPreparationService._running_projects.clear()
    yield
    ProjectPreparationService._running_projects.clear()


@pytest.fixture
def user():
    return UserPublicResponse(
        user_id="USR-001",
        name="User",
        email="user@example.com",
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


def service(tmp_path, uploads, *, failed=(), complete=(), executor=None):
    extraction = StageStub(ExtractionStatus.SUCCESS, failed)
    chunks = StageStub(ChunkingStatus.SUCCESS)
    rules = StageStub()
    model = StageStub(ZeroShotStatus.SUCCESS)
    hybrid = StageStub()
    instance = ProjectPreparationService(
        StandaloneStub(),
        UploadStorageStub(uploads),
        ProjectPreparationStorage(tmp_path),
        extraction,
        chunks,
        rules,
        model,
        hybrid,
        ReviewStub(complete),
        executor=executor or InlineExecutor(),
        clock=lambda: NOW,
    )
    return instance, (extraction, chunks, rules, model, hybrid)


def test_multiple_documents_run_through_hybrid_and_wait_for_human(tmp_path, user):
    uploads = [upload(1), upload(2)]
    controller, stages = service(tmp_path, uploads)

    result = controller.start("AGP-003", ProjectPreparationStartRequest(), user)

    assert result.status is ProjectPreparationStatus.WAITING_FOR_HUMAN
    assert result.completed_source_count == 2
    assert result.human_review_source_count == 2
    assert all(stage.calls == [item.upload_id for item in uploads] for stage in stages)


def test_one_document_runs_through_hybrid_to_ready(tmp_path, user):
    item = upload(1)
    controller, stages = service(tmp_path, [item], complete={item.upload_id})

    result = controller.start("AGP-003", ProjectPreparationStartRequest(), user)

    assert result.status is ProjectPreparationStatus.ANALYSIS_READY
    assert result.sources[0].status is SourcePreparationStatus.READY
    assert all(stage.calls == [item.upload_id] for stage in stages)


def test_failure_is_isolated_and_safe(tmp_path, user):
    uploads = [upload(1), upload(2)]
    controller, _ = service(tmp_path, uploads, failed={uploads[1].upload_id})

    result = controller.start("AGP-003", ProjectPreparationStartRequest(), user)

    assert result.status is ProjectPreparationStatus.PARTIAL_FAILURE
    assert result.failed_source_count == 1
    failed = next(source for source in result.sources if source.status is SourcePreparationStatus.FAILED)
    assert failed.error.error_code == "SOURCE_PREPARATION_FAILED"
    assert "unsafe internal detail" not in failed.error.message


def test_all_failures_produce_failed(tmp_path, user):
    uploads = [upload(1), upload(2)]
    controller, _ = service(
        tmp_path, uploads, failed={item.upload_id for item in uploads}
    )
    assert controller.start(
        "AGP-003", ProjectPreparationStartRequest(), user
    ).status is ProjectPreparationStatus.FAILED


def test_text_and_image_states_are_honest(tmp_path, user):
    controller, _ = service(tmp_path, [upload(3, ImplementationInputSourceType.IMAGE)])
    request = ProjectPreparationStartRequest(
        text_inputs=[PreparationTextInput(
            input_id="LOCAL-1",
            artifact_type=ImplementationArtifactType.TECHNICAL_CONSTRAINTS,
            content="Use the supported stack.",
        )]
    )

    result = controller.start("AGP-003", request, user)

    assert result.status is ProjectPreparationStatus.ANALYSIS_READY
    assert result.eligible_source_count == 1
    assert result.processed_source_count == 1
    image = next(source for source in result.sources if source.source_kind is ImplementationInputSourceType.IMAGE)
    assert image.status is SourcePreparationStatus.SKIPPED
    assert image.error.error_code == "IMAGE_ANALYSIS_NOT_IMPLEMENTED"


def test_persisted_status_reconciles_deleted_sources_and_completed_review(tmp_path, user):
    uploads = [upload(1), upload(2)]
    controller, _ = service(tmp_path, uploads)
    controller.start("AGP-003", ProjectPreparationStartRequest(), user)

    controller._uploads.uploads = [uploads[0]]
    controller._human_review.complete_ids.add(uploads[0].upload_id)
    recovered, _ = service(tmp_path, controller._uploads.uploads, complete={uploads[0].upload_id})
    result = recovered.get_status("AGP-003", user)

    assert result.status is ProjectPreparationStatus.ANALYSIS_READY
    assert [source.source_id for source in result.sources] == [uploads[0].upload_id]


def test_cached_stages_are_reused_and_only_new_source_computes(tmp_path, user):
    uploads = [upload(1), upload(2), upload(3)]
    storage = UploadStorageStub(uploads)
    stages = [
        CachingStageStub(ExtractionStatus.SUCCESS),
        CachingStageStub(ChunkingStatus.SUCCESS),
        CachingStageStub(),
        CachingStageStub(ZeroShotStatus.SUCCESS),
        CachingStageStub(),
    ]
    controller = ProjectPreparationService(
        StandaloneStub(), storage, ProjectPreparationStorage(tmp_path),
        *stages, ReviewStub(), executor=InlineExecutor(), clock=lambda: NOW,
    )

    controller.start("AGP-003", ProjectPreparationStartRequest(), user)
    controller.start("AGP-003", ProjectPreparationStartRequest(), user)
    storage.uploads.append(upload(4))
    controller.start("AGP-003", ProjectPreparationStartRequest(), user)

    assert all(stage.computation_count == 4 for stage in stages)
    assert all(stage.calls.count(uploads[0].upload_id) == 3 for stage in stages)
    assert all(stage.calls.count(storage.uploads[-1].upload_id) == 1 for stage in stages)


def test_text_snapshot_and_identity_survive_reload_and_empty_resume(tmp_path, user):
    controller, _ = service(tmp_path, [])
    request = ProjectPreparationStartRequest(text_inputs=[PreparationTextInput(
        input_id="LOCAL-stable-7",
        artifact_type=ImplementationArtifactType.SRS,
        label="Requirements notes",
        content="Persisted only in the private preparation sidecar.",
    )])
    controller.start("AGP-003", request, user)

    recovered, _ = service(tmp_path, [])
    refreshed = recovered.get_status("AGP-003", user)
    resumed = recovered.start(
        "AGP-003", ProjectPreparationStartRequest(), user
    )

    assert [source.source_id for source in refreshed.sources] == ["LOCAL-stable-7"]
    assert [source.source_id for source in resumed.sources] == ["LOCAL-stable-7"]
    assert "Persisted only" not in refreshed.model_dump_json()


def test_stale_running_state_becomes_failed_and_can_resume(tmp_path, user):
    held = HoldingExecutor()
    uploads = [upload(1), upload(2)]
    controller, _ = service(tmp_path, uploads, executor=held)
    controller.start("AGP-003", ProjectPreparationStartRequest(), user)

    ProjectPreparationService._running_projects.clear()
    recovered, _ = service(
        tmp_path, uploads, complete={item.upload_id for item in uploads}
    )
    interrupted = recovered.get_status("AGP-003", user)
    resumed = recovered.start(
        "AGP-003", ProjectPreparationStartRequest(), user
    )

    assert interrupted.status is ProjectPreparationStatus.FAILED
    assert all(
        source.error.error_code == "PREPARATION_INTERRUPTED"
        for source in interrupted.sources
    )
    assert resumed.status is ProjectPreparationStatus.ANALYSIS_READY


def test_project_status_precedence_is_explicit():
    def source(status):
        return PersistedPreparationSource(
            source_id=f"LOCAL-{status}",
            source_kind=ImplementationInputSourceType.TEXT,
            artifact_type=ImplementationArtifactType.SRS,
            status=status,
            current_stage=PreparationStage.TEXT_NORMALIZATION,
            text_content="source",
        )

    assert derive_project_status([]) is ProjectPreparationStatus.NOT_STARTED
    assert derive_project_status([source(SourcePreparationStatus.EXTRACTING)]) is ProjectPreparationStatus.RUNNING
    assert derive_project_status([source(SourcePreparationStatus.WAITING_FOR_HUMAN)]) is ProjectPreparationStatus.WAITING_FOR_HUMAN
    assert derive_project_status([source(SourcePreparationStatus.READY)]) is ProjectPreparationStatus.ANALYSIS_READY
    assert derive_project_status([source(SourcePreparationStatus.READY), source(SourcePreparationStatus.FAILED)]) is ProjectPreparationStatus.PARTIAL_FAILURE
    assert derive_project_status([source(SourcePreparationStatus.FAILED)]) is ProjectPreparationStatus.FAILED


def test_duplicate_start_does_not_schedule_a_second_job(tmp_path, user):
    held = HoldingExecutor()
    controller, _ = service(tmp_path, [upload(1)], executor=held)

    first = controller.start("AGP-003", ProjectPreparationStartRequest(), user)
    second = controller.start("AGP-003", ProjectPreparationStartRequest(), user)

    assert first.status is ProjectPreparationStatus.RUNNING
    assert second.status is ProjectPreparationStatus.RUNNING
    assert len(held.calls) == 1


def test_global_worker_pool_is_bounded_to_one():
    assert orchestration_service._PREPARATION_EXECUTOR._max_workers == 1


def test_public_status_never_exposes_paths_or_text_content(tmp_path, user):
    controller, _ = service(tmp_path, [])
    result = controller.start(
        "AGP-003",
        ProjectPreparationStartRequest(text_inputs=[PreparationTextInput(
            input_id="LOCAL-secret",
            artifact_type=ImplementationArtifactType.SRS,
            content="private source body",
        )]),
        user,
    )
    payload = result.model_dump_json()
    assert "private source body" not in payload
    assert str(tmp_path) not in payload


def test_preparation_sidecar_does_not_change_existing_upload_artifacts(tmp_path, user):
    project_directory = tmp_path / "AGP-003"
    project_directory.mkdir()
    existing_sidecar = project_directory / "existing.hybrid.json"
    existing_sidecar.write_text('{"fingerprint":"unchanged"}', encoding="utf-8")
    controller, _ = service(tmp_path, [])

    controller.start(
        "AGP-003",
        ProjectPreparationStartRequest(text_inputs=[PreparationTextInput(
            input_id="LOCAL-sidecar",
            artifact_type=ImplementationArtifactType.SRS,
            content="Text preparation state.",
        )]),
        user,
    )

    assert existing_sidecar.read_text(encoding="utf-8") == '{"fingerprint":"unchanged"}'
    assert (project_directory / "preparation.json").is_file()
    assert not (project_directory / "preparation.json.part").exists()


class ApiPreparationStub:
    def __init__(self):
        self.start_requests = []

    @staticmethod
    def response():
        return ProjectPreparationStatusResponse(
            agent_project_id="AGP-003",
            status=ProjectPreparationStatus.NOT_STARTED,
            source_count=0,
            eligible_source_count=0,
            processed_source_count=0,
            completed_source_count=0,
            active_source_count=0,
            failed_source_count=0,
            sources=[],
            requires_human_review=False,
            human_review_source_count=0,
        )

    def start(self, agent_project_id, request, current_user):
        self.start_requests.append(request)
        return self.response()

    def get_status(self, agent_project_id, current_user):
        return self.response()


class FailingApiPreparationStub(ApiPreparationStub):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def start(self, agent_project_id, request, current_user):
        raise self.error

    def get_status(self, agent_project_id, current_user):
        raise self.error


def test_preparation_api_contracts_and_authentication(authentication_context):
    service_stub = ApiPreparationStub()
    app.dependency_overrides[get_project_preparation_service] = lambda: service_stub
    try:
        anonymous = authentication_context.anonymous_client()
        assert anonymous.get(
            "/api/v1/agents/implementation/AGP-003/preparation/status"
        ).status_code == 401

        client = authentication_context.client()
        start_response = client.post(
            "/api/v1/agents/implementation/AGP-003/preparation/start",
            json={"text_inputs": []},
        )
        status_response = client.get(
            "/api/v1/agents/implementation/AGP-003/preparation/status"
        )

        assert start_response.status_code == 202
        assert status_response.status_code == 200
        assert start_response.json()["data"]["status"] == "NOT_STARTED"
        assert status_response.json()["data"]["sources"] == []
        assert service_stub.start_requests == [ProjectPreparationStartRequest()]
    finally:
        app.dependency_overrides.pop(get_project_preparation_service, None)


def test_openapi_contains_only_the_intended_preparation_operations():
    paths = app.openapi()["paths"]
    start_path = paths[
        "/api/v1/agents/implementation/{agent_project_id}/preparation/start"
    ]
    status_path = paths[
        "/api/v1/agents/implementation/{agent_project_id}/preparation/status"
    ]
    assert set(start_path) == {"post"}
    assert set(status_path) == {"get"}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (AgentProjectNotFoundError(), 404),
        (ArchivedAgentProjectError(), 409),
        (WrongAgentProjectTypeError("wrong type"), 422),
    ],
)
def test_preparation_api_maps_project_access_errors(
    authentication_context, error, expected_status
):
    app.dependency_overrides[get_project_preparation_service] = (
        lambda: FailingApiPreparationStub(error)
    )
    try:
        client = authentication_context.client()
        assert client.post(
            "/api/v1/agents/implementation/AGP-003/preparation/start",
            json={"text_inputs": []},
        ).status_code == expected_status
        assert client.get(
            "/api/v1/agents/implementation/AGP-003/preparation/status"
        ).status_code == expected_status
    finally:
        app.dependency_overrides.pop(get_project_preparation_service, None)
