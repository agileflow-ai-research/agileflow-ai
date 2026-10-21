from concurrent.futures import Future

import pytest

from app.main import app
from app.modules.agents.testing_validation.preparation.chunking.service import (
    Agent4ChunkingService,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
)
from app.modules.agents.testing_validation.preparation.extraction.service import (
    Agent4DocumentExtractionService,
)
from app.modules.agents.testing_validation.preparation.extraction.storage import (
    Agent4ExtractionStorage,
)
from app.modules.agents.testing_validation.preparation.normalization.service import (
    Agent4NormalizationService,
)
from app.modules.agents.testing_validation.preparation.normalization.storage import (
    Agent4NormalizationStorage,
)
from app.modules.agents.testing_validation.router import (
    get_agent4_n2_orchestration_service,
    get_agent4_source_storage,
    get_agent4_workflow_storage,
)
from app.modules.agents.testing_validation.sources.storage import Agent4SourceStorage
from app.modules.agents.testing_validation.workflow.orchestration.service import (
    Agent4N2OrchestrationService,
)
from app.modules.agents.testing_validation.workflow.service import Agent4WorkflowService
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from app.modules.standalone.service import StandaloneService
from test_agent4_document_extraction import pdf_bytes
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
    user,
)


class ControlledExecutor:
    def __init__(self):
        self.tasks = []

    def submit(self, function, *args):
        self.tasks.append((function, args))
        return Future()

    def drain(self):
        while self.tasks:
            function, args = self.tasks.pop(0)
            function(*args)


@pytest.fixture
def n2_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    sources = Agent4SourceStorage(tmp_path)
    workflows = Agent4WorkflowStorage(tmp_path)
    standalone = StandaloneService(projects, runs)
    workflow_service = Agent4WorkflowService(standalone, workflows, sources)
    extraction = Agent4DocumentExtractionService(
        standalone, sources, workflows, Agent4ExtractionStorage(tmp_path)
    )
    normalization = Agent4NormalizationService(
        extraction, Agent4NormalizationStorage(tmp_path)
    )
    chunking = Agent4ChunkingService(
        normalization, Agent4ChunkStorage(tmp_path)
    )
    executor = ControlledExecutor()
    orchestration = Agent4N2OrchestrationService(
        workflow_service,
        workflows,
        sources,
        extraction,
        normalization,
        chunking,
        executor=executor,
    )
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent4_source_storage] = lambda: sources
    app.dependency_overrides[get_agent4_workflow_storage] = lambda: workflows
    app.dependency_overrides[get_agent4_n2_orchestration_service] = (
        lambda: orchestration
    )
    try:
        yield (
            authentication_context.client(),
            orchestration,
            executor,
            tmp_path,
            projects,
            runs,
            extraction,
            normalization,
            chunking,
        )
    finally:
        Agent4N2OrchestrationService._active_execution_ids.clear()
        for dependency in (
            get_agent_project_repository,
            get_agent_run_repository,
            get_agent4_source_storage,
            get_agent4_workflow_storage,
            get_agent4_n2_orchestration_service,
        ):
            app.dependency_overrides.pop(dependency, None)


def create_project(client):
    response = client.post(
        "/api/v1/agent-projects",
        json={
            "agent_type": "TESTING_VALIDATION",
            "agent_stage": "TEST_GENERATION",
            "name": "N2 orchestration",
            "domain": "Fintech",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["agent_project_id"]


def base(project_id):
    return f"/api/v1/agents/testing-validation/{project_id}/test-generation"


def add_text(client, project_id, content="Customer can transfer funds."):
    response = client.post(
        f"{base(project_id)}/sources/text",
        json={
            "artifact_type": "FUNCTIONAL_REQUIREMENTS",
            "normally_supplied_by": "AGENT_1",
            "content": content,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def upload(client, project_id, filename, content, content_type, **fields):
    data = {
        "artifact_type": "FUNCTIONAL_REQUIREMENTS",
        "source_type": "DOCUMENT",
        "normally_supplied_by": "AGENT_1",
        **fields,
    }
    response = client.post(
        f"{base(project_id)}/sources/files",
        data=data,
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def confirm(client, project_id):
    selected = client.put(
        f"{base(project_id)}/workflow/outputs",
        json={"selected_outputs": ["UNIT_TEST_CASES"]},
    )
    assert selected.status_code == 200
    response = client.post(f"{base(project_id)}/workflow/n1/confirm")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def load(client, project_id):
    response = client.get(f"{base(project_id)}/workflow")
    assert response.status_code == 200
    return response.json()["data"]


def test_confirmation_queues_one_snapshot_bound_execution(n2_context):
    client, _, executor, _, _, runs, _, _, _ = n2_context
    project_id = create_project(client)
    source = add_text(client, project_id)

    first = confirm(client, project_id)
    second = client.post(f"{base(project_id)}/workflow/n1/confirm").json()["data"]

    assert first["nodes"][1]["status"] == "QUEUED"
    assert first["n2_execution"]["status"] == "QUEUED"
    assert first["n2_execution"]["confirmed_source_ids"] == [source["source_id"]]
    assert first["n2_execution"]["confirmation_id"] == first["n1_confirmation"]["confirmation_id"]
    assert second["n2_execution"]["execution_id"] == first["n2_execution"]["execution_id"]
    assert second["n2_execution_count"] == 1
    assert len(executor.tasks) == 1
    assert runs.documents == {}


def test_text_pipeline_completes_n2_and_unlocks_n3_without_extraction(
    n2_context, monkeypatch
):
    client, _, executor, root, _, runs, extraction, normalization, chunking = n2_context
    project_id = create_project(client)
    source = add_text(client, project_id, "First behavior.\n\nSecond behavior.")
    extract_calls = []
    normalize_calls = []
    chunk_calls = []
    original_extract = extraction.extract
    original_normalize = normalization.normalize
    original_chunk = chunking.build
    monkeypatch.setattr(extraction, "extract", lambda *args, **kwargs: extract_calls.append(args) or original_extract(*args, **kwargs))
    monkeypatch.setattr(normalization, "normalize", lambda *args, **kwargs: normalize_calls.append(args) or original_normalize(*args, **kwargs))
    monkeypatch.setattr(chunking, "build", lambda *args, **kwargs: chunk_calls.append(args) or original_chunk(*args, **kwargs))

    confirm(client, project_id)
    executor.drain()
    workflow = load(client, project_id)

    assert extract_calls == []
    assert [call[1] for call in normalize_calls] == [source["source_id"]]
    assert [call[1] for call in chunk_calls] == [source["source_id"]]
    assert workflow["n2_execution"]["status"] == "COMPLETED"
    assert workflow["n2_execution"]["sources"][0]["status"] == "COMPLETE"
    assert workflow["n2_execution"]["total_chunks"] >= 1
    assert workflow["current_node_id"] == "TESTING_INTELLIGENCE"
    assert [node["status"] for node in workflow["nodes"]] == [
        "COMPLETED", "COMPLETED", "NOT_STARTED", "LOCKED", "LOCKED", "LOCKED"
    ]
    assert workflow["pipeline_status"] == "RUNNING"
    assert runs.documents == {}
    assert not list((root / project_id).rglob("*classification*"))


def test_document_and_image_pipelines_are_truthful_and_image_is_nonblocking(
    n2_context, monkeypatch
):
    client, _, executor, root, _, _, extraction, _, chunking = n2_context
    project_id = create_project(client)
    document = upload(
        client,
        project_id,
        "requirements.pdf",
        pdf_bytes("Approved behavior"),
        "application/pdf",
    )
    image = upload(
        client,
        project_id,
        "wireframe.png",
        b"\x89PNG\r\n\x1a\nminimal",
        "image/png",
        artifact_type="WIREFRAMES",
        source_type="IMAGE",
        normally_supplied_by="AGENT_2",
    )
    immutable_paths = [
        root / project_id / "inputs" / f"{document['source_id']}.pdf",
        root / project_id / "inputs" / f"{document['source_id']}.source.json",
        root / project_id / "inputs" / f"{image['source_id']}.png",
        root / project_id / "inputs" / f"{image['source_id']}.source.json",
    ]
    immutable_before = {path: path.read_bytes() for path in immutable_paths}
    extracted = []
    chunked = []
    original_extract = extraction.extract
    original_chunk = chunking.build
    monkeypatch.setattr(extraction, "extract", lambda *args, **kwargs: extracted.append(args[1]) or original_extract(*args, **kwargs))
    monkeypatch.setattr(chunking, "build", lambda *args, **kwargs: chunked.append(args[1]) or original_chunk(*args, **kwargs))

    confirm(client, project_id)
    executor.drain()
    workflow = load(client, project_id)
    sources = {item["source_id"]: item for item in workflow["n2_execution"]["sources"]}

    assert extracted == [document["source_id"]]
    assert chunked == [document["source_id"]]
    assert sources[document["source_id"]]["status"] == "COMPLETE"
    assert sources[image["source_id"]]["status"] == "PENDING_ANALYSIS"
    assert sources[image["source_id"]]["normalization_status"] == "PENDING_ANALYSIS"
    assert sources[image["source_id"]]["chunk_count"] == 0
    assert workflow["n2_execution"]["status"] == "COMPLETED"
    assert workflow["n2_execution"]["warnings"][0]["code"] == "IMAGE_ANALYSIS_NOT_IMPLEMENTED"
    assert all(path.read_bytes() == content for path, content in immutable_before.items())


def test_partial_document_remains_usable_with_warnings(n2_context):
    client, _, executor, _, _, _, _, _, _ = n2_context
    project_id = create_project(client)
    source = upload(
        client,
        project_id,
        "requirements.pdf",
        pdf_bytes("Usable requirement", ""),
        "application/pdf",
    )
    confirm(client, project_id)
    executor.drain()
    workflow = load(client, project_id)
    progress = workflow["n2_execution"]["sources"][0]
    assert progress["source_id"] == source["source_id"]
    assert progress["extraction_status"] == "PARTIAL"
    assert progress["normalization_status"] == "READY_WITH_WARNINGS"
    assert progress["status"] == "COMPLETE"
    assert progress["chunk_count"] >= 1
    assert {warning["code"] for warning in progress["warnings"]} >= {
        "NO_TEXT_ON_PAGE"
    }


def test_source_failure_isolated_and_targeted_retry_reuses_success(
    n2_context, monkeypatch
):
    client, _, executor, _, _, _, extraction, normalization, _ = n2_context
    project_id = create_project(client)
    text = add_text(client, project_id)
    document = upload(
        client,
        project_id,
        "requirements.pdf",
        pdf_bytes("Retryable document"),
        "application/pdf",
    )
    original_normalize = normalization.normalize
    failed_once = {document["source_id"]: False}
    calls = []

    def transient_failure(project, source_id, current_user, **kwargs):
        calls.append(source_id)
        if source_id == document["source_id"] and not failed_once[source_id]:
            failed_once[source_id] = True
            raise RuntimeError("internal detail must not escape")
        return original_normalize(project, source_id, current_user, **kwargs)

    monkeypatch.setattr(normalization, "normalize", transient_failure)
    confirm(client, project_id)
    executor.drain()
    failed = load(client, project_id)
    confirmation_id = failed["n1_confirmation"]["confirmation_id"]
    states = {item["source_id"]: item for item in failed["n2_execution"]["sources"]}
    assert states[text["source_id"]]["status"] == "COMPLETE"
    assert states[document["source_id"]]["status"] == "FAILED"
    assert failed["pipeline_status"] == "FAILED"
    assert failed["current_node_id"] == "INPUT_PREPARATION"
    assert "internal detail" not in str(failed)

    response = client.post(
        f"{base(project_id)}/workflow/n2/sources/{document['source_id']}/retry"
    )
    assert response.status_code == 200
    assert response.json()["data"]["n2_execution_count"] == 2
    assert response.json()["data"]["n2_execution"]["attempt_number"] == 2
    executor.drain()
    completed = load(client, project_id)
    assert completed["n2_execution"]["status"] == "COMPLETED"
    assert completed["current_node_id"] == "TESTING_INTELLIGENCE"
    assert completed["n1_confirmation"]["confirmation_id"] == confirmation_id
    assert calls.count(text["source_id"]) == 1
    assert calls.count(document["source_id"]) == 2
    assert extraction.extract(project_id, document["source_id"], user()).source_id == document["source_id"]


def test_legacy_not_started_start_is_idempotent(n2_context):
    client, orchestration, executor, _, _, _, _, _, _ = n2_context
    project_id = create_project(client)
    add_text(client, project_id)
    client.put(
        f"{base(project_id)}/workflow/outputs",
        json={"selected_outputs": ["UNIT_TEST_CASES"]},
    )
    orchestration._workflow_service.confirm_n1(project_id, user())

    first = client.post(f"{base(project_id)}/workflow/n2/start")
    second = client.post(f"{base(project_id)}/workflow/n2/start")

    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["n2_execution"]["execution_id"] == second.json()["data"]["n2_execution"]["execution_id"]
    assert len(executor.tasks) == 1


def test_interrupted_execution_becomes_retryable_without_claiming_completion(
    n2_context,
):
    client, orchestration, _, _, _, _, _, _, _ = n2_context
    project_id = create_project(client)
    source = add_text(client, project_id)
    queued = confirm(client, project_id)
    execution_id = queued["n2_execution"]["execution_id"]
    Agent4N2OrchestrationService._active_execution_ids.discard(execution_id)

    interrupted = orchestration.get(project_id, user()).model_dump(mode="json")

    assert interrupted["n2_execution"]["status"] == "INTERRUPTED"
    assert interrupted["n2_execution"]["retryable"] is True
    assert interrupted["n2_execution"]["completed_at"] is None
    assert interrupted["n2_execution"]["sources"][0]["source_id"] == source["source_id"]
    assert interrupted["n2_execution"]["sources"][0]["status"] == "FAILED"
    assert interrupted["pipeline_status"] == "FAILED"


def test_start_requires_confirmation_and_never_creates_agent_run(n2_context):
    client, _, _, _, _, runs, _, _, _ = n2_context
    project_id = create_project(client)
    add_text(client, project_id)
    response = client.post(f"{base(project_id)}/workflow/n2/start")
    assert response.status_code == 409
    assert runs.documents == {}


def test_executor_submission_failure_is_persisted_as_retryable(n2_context):
    client, orchestration, _, _, _, _, _, _, _ = n2_context

    class UnavailableExecutor:
        def submit(self, *_args):
            raise RuntimeError("executor stopped")

    orchestration._executor = UnavailableExecutor()
    project_id = create_project(client)
    add_text(client, project_id)
    workflow = confirm(client, project_id)
    assert workflow["n2_execution"]["status"] == "FAILED"
    assert workflow["n2_execution"]["retryable"] is True
    assert workflow["n2_execution"]["error"]["code"] == "N2_EXECUTOR_UNAVAILABLE"
    assert workflow["nodes"][0]["status"] == "COMPLETED"
    assert workflow["nodes"][1]["status"] == "FAILED"
