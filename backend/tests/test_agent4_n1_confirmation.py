import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import Future

import pytest

from app.main import app
from app.modules.agents.testing_validation.router import (
    get_agent4_n2_orchestration_service,
    get_agent4_source_storage,
    get_agent4_workflow_storage,
)
from app.modules.agents.testing_validation.preparation.chunking.service import Agent4ChunkingService
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
from app.modules.agents.testing_validation.preparation.extraction.service import Agent4DocumentExtractionService
from app.modules.agents.testing_validation.preparation.extraction.storage import Agent4ExtractionStorage
from app.modules.agents.testing_validation.preparation.normalization.service import Agent4NormalizationService
from app.modules.agents.testing_validation.preparation.normalization.storage import Agent4NormalizationStorage
from app.modules.agents.testing_validation.workflow.orchestration.service import Agent4N2OrchestrationService
from app.modules.agents.testing_validation.workflow.service import Agent4WorkflowService
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType as ArtifactType,
    TestGenerationInputOriginAgent as OriginAgent,
)
from app.modules.agents.testing_validation.schemas import (
    TestGenerationOutputCode as OutputCode,
)
from app.modules.agents.testing_validation.sources.schemas import (
    TestGenerationSourceRecord as SourceRecord,
)
from app.modules.agents.testing_validation.sources.storage import Agent4SourceStorage
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
    AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
)
from app.modules.agents.testing_validation.workflow.digests import (
    output_selection_digest,
    source_set_digest,
)
from app.modules.agents.testing_validation.workflow.storage import (
    Agent4WorkflowStorage,
    Agent4WorkflowStorageError,
)
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_agent4_source_collection import PDF, PNG
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)
from app.modules.standalone.service import StandaloneService


class DeferredN2Executor:
    def __init__(self):
        self.tasks = []

    def submit(self, function, *args):
        self.tasks.append((function, args))
        return Future()


@pytest.fixture
def confirmation_context(authentication_context, tmp_path):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    source_storage = Agent4SourceStorage(tmp_path)
    workflow_storage = Agent4WorkflowStorage(tmp_path)
    standalone = StandaloneService(projects, runs)
    workflow_service = Agent4WorkflowService(
        standalone, workflow_storage, source_storage
    )
    extraction = Agent4DocumentExtractionService(
        standalone,
        source_storage,
        workflow_storage,
        Agent4ExtractionStorage(tmp_path),
    )
    normalization = Agent4NormalizationService(
        extraction, Agent4NormalizationStorage(tmp_path)
    )
    orchestration = Agent4N2OrchestrationService(
        workflow_service,
        workflow_storage,
        source_storage,
        extraction,
        normalization,
        Agent4ChunkingService(normalization, Agent4ChunkStorage(tmp_path)),
        executor=DeferredN2Executor(),
    )
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent4_source_storage] = lambda: source_storage
    app.dependency_overrides[get_agent4_workflow_storage] = lambda: workflow_storage
    app.dependency_overrides[get_agent4_n2_orchestration_service] = (
        lambda: orchestration
    )
    try:
        yield (
            authentication_context,
            projects,
            runs,
            tmp_path,
            workflow_storage,
        )
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent4_source_storage, None)
        app.dependency_overrides.pop(get_agent4_workflow_storage, None)
        app.dependency_overrides.pop(get_agent4_n2_orchestration_service, None)
        Agent4N2OrchestrationService._active_execution_ids.clear()


def create_project(client, agent_type="TESTING_VALIDATION"):
    payload = {
        "agent_type": agent_type,
        "name": "N1 confirmation project",
        "domain": "Fintech",
    }
    if agent_type == "TESTING_VALIDATION":
        payload["agent_stage"] = "TEST_GENERATION"
    response = client.post("/api/v1/agent-projects", json=payload)
    assert response.status_code == 201
    return response.json()["data"]["agent_project_id"]


def workflow_url(project_id):
    return (
        f"/api/v1/agents/testing-validation/{project_id}"
        "/test-generation/workflow"
    )


def sources_url(project_id):
    return (
        f"/api/v1/agents/testing-validation/{project_id}"
        "/test-generation/sources"
    )


def confirm_url(project_id):
    return f"{workflow_url(project_id)}/n1/confirm"


def add_text(
    client,
    project_id,
    *,
    artifact_type="FUNCTIONAL_REQUIREMENTS",
    origin="AGENT_1",
    content="Customers can transfer funds.",
):
    return client.post(
        f"{sources_url(project_id)}/text",
        json={
            "artifact_type": artifact_type,
            "normally_supplied_by": origin,
            "content": content,
        },
    )


def upload(
    client,
    project_id,
    *,
    source_type="DOCUMENT",
    artifact_type="FUNCTIONAL_REQUIREMENTS",
    origin="AGENT_1",
    filename="requirements.pdf",
    content=PDF,
    content_type="application/pdf",
):
    return client.post(
        f"{sources_url(project_id)}/files",
        data={
            "artifact_type": artifact_type,
            "source_type": source_type,
            "normally_supplied_by": origin,
        },
        files={"file": (filename, content, content_type)},
    )


def select_outputs(client, project_id, outputs=None, **extra):
    return client.put(
        f"{workflow_url(project_id)}/outputs",
        json={
            "selected_outputs": outputs or ["UNIT_TEST_CASES"],
            **extra,
        },
    )


def prepare_valid(client, project_id):
    source = add_text(client, project_id).json()["data"]
    selection = select_outputs(client, project_id).json()["data"]
    return source, selection


def test_valid_confirmation_snapshots_exact_setup_and_transitions_workflow(
    confirmation_context,
):
    authentication, _, runs, root, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    source, selection = prepare_valid(client, project_id)
    sidecar = root / project_id / "inputs" / f"{source['source_id']}.source.json"
    sidecar_before = sidecar.read_bytes()

    response = client.post(confirm_url(project_id))

    assert response.status_code == 200
    workflow = response.json()["data"]
    confirmation = workflow["n1_confirmation"]
    assert confirmation["confirmation_id"].startswith("A4N1C-")
    assert len(confirmation["confirmation_id"]) == len("A4N1C-") + 32
    assert confirmation["confirmed_at"]
    assert confirmation["source_ids"] == [source["source_id"]]
    assert confirmation["selected_outputs"] == ["UNIT_TEST_CASES"]
    assert confirmation["source_count"] == 1
    assert confirmation["selected_output_count"] == 1
    assert confirmation["selection_revision"] == selection["selection_revision"]
    assert len(confirmation["source_set_digest"]) == 64
    assert len(confirmation["selection_digest"]) == 64
    assert "confirmed_by" not in json.dumps(confirmation)
    assert "path" not in json.dumps(workflow).lower()
    assert workflow["pipeline_status"] == "RUNNING"
    assert workflow["current_node_id"] == "INPUT_PREPARATION"
    assert [node["status"] for node in workflow["nodes"]] == [
        "COMPLETED",
        "QUEUED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
        "LOCKED",
    ]
    assert sidecar.read_bytes() == sidecar_before
    assert runs.documents == {}


def test_document_primary_and_pending_image_can_be_confirmed(
    confirmation_context,
):
    authentication, _, _, root, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    document = upload(client, project_id).json()["data"]
    image = upload(
        client,
        project_id,
        source_type="IMAGE",
        artifact_type="WIREFRAMES",
        origin="AGENT_2",
        filename="wireframe.png",
        content=PNG,
        content_type="image/png",
    ).json()["data"]
    assert image["collection_status"] == "PENDING_ANALYSIS"
    select_outputs(client, project_id, ["E2E_TEST_CASES"])
    raw_path = root / project_id / "inputs" / f"{document['source_id']}.pdf"
    raw_before = raw_path.read_bytes()

    response = client.post(confirm_url(project_id))

    assert response.status_code == 200
    confirmation = response.json()["data"]["n1_confirmation"]
    assert confirmation["source_count"] == 2
    assert confirmation["source_ids"] == sorted(
        [document["source_id"], image["source_id"]]
    )
    assert raw_path.read_bytes() == raw_before
    assert {path.name for path in (root / project_id / "inputs").iterdir()} == {
        f"{document['source_id']}.pdf",
        f"{document['source_id']}.source.json",
        f"{image['source_id']}.png",
        f"{image['source_id']}.source.json",
    }


@pytest.mark.parametrize(
    ("prepare", "message"),
    [
        (lambda client, project: select_outputs(client, project), "at least one source"),
        (lambda client, project: add_text(client, project), "at least one desired output"),
        (
            lambda client, project: (
                add_text(
                    client,
                    project,
                    artifact_type="API_SPECIFICATION",
                    origin="AGENT_2",
                ),
                select_outputs(client, project),
            ),
            "primary functional source",
        ),
    ],
)
def test_confirmation_gates(confirmation_context, prepare, message):
    authentication, _, runs, _, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    prepare(client, project_id)

    response = client.post(confirm_url(project_id))

    assert response.status_code == 409
    assert message in response.text
    workflow = client.get(workflow_url(project_id)).json()["data"]
    assert workflow["n1_confirmation"] is None
    assert workflow["current_node_id"] == "INPUT_OUTPUT_SETUP"
    assert runs.documents == {}


def test_backend_confirms_only_persisted_selection_and_ignores_client_snapshot(
    confirmation_context,
):
    authentication, _, _, _, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    source, selection = prepare_valid(client, project_id)

    response = client.post(
        confirm_url(project_id),
        json={
            "source_ids": ["A4SRC-" + "f" * 32],
            "selected_outputs": ["SECURITY_TEST_CASES"],
            "selection_revision": 999,
            "source_set_digest": "0" * 64,
        },
    )

    assert response.status_code == 200
    confirmation = response.json()["data"]["n1_confirmation"]
    assert confirmation["source_ids"] == [source["source_id"]]
    assert confirmation["selected_outputs"] == ["UNIT_TEST_CASES"]
    assert confirmation["selection_revision"] == selection["selection_revision"]
    assert confirmation["source_set_digest"] != "0" * 64


def test_digest_contracts_are_deterministic_and_bind_relevant_state(
    confirmation_context,
):
    authentication, _, _, _, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    first = SourceRecord.model_validate(
        add_text(client, project_id, content="Exact  text\ncontent").json()["data"]
    )
    second = SourceRecord.model_validate(
        upload(client, project_id).json()["data"]
    )

    assert source_set_digest([first, second]) == source_set_digest([second, first])
    assert source_set_digest([first]) != source_set_digest(
        [first.model_copy(update={"text_content": "Exact text\ncontent"})]
    )
    assert source_set_digest([first]) != source_set_digest(
        [first.model_copy(update={"artifact_type": ArtifactType.SRS})]
    )
    assert source_set_digest([first]) != source_set_digest(
        [first.model_copy(update={"normally_supplied_by": OriginAgent.AGENT_2})]
    )
    assert source_set_digest([second]) != source_set_digest(
        [second.model_copy(update={"sha256": "f" * 64})]
    )
    left = output_selection_digest(
        [OutputCode.API_TEST_CASES, OutputCode.UNIT_TEST_CASES]
    )
    right = output_selection_digest(
        [OutputCode.UNIT_TEST_CASES, OutputCode.API_TEST_CASES]
    )
    assert left == right
    assert left != output_selection_digest([OutputCode.API_TEST_CASES])


def test_repeat_confirmation_is_byte_idempotent(confirmation_context):
    authentication, _, _, root, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    prepare_valid(client, project_id)
    first = client.post(confirm_url(project_id)).json()["data"]
    path = root / project_id / "workflow.json"
    before = path.read_bytes()

    second = client.post(confirm_url(project_id)).json()["data"]

    assert second == first
    assert second["n1_confirmation"]["confirmation_id"] == first[
        "n1_confirmation"
    ]["confirmation_id"]
    assert second["n1_confirmation"]["confirmed_at"] == first[
        "n1_confirmation"
    ]["confirmed_at"]
    assert path.read_bytes() == before


def test_confirmed_setup_is_frozen_but_remains_readable(confirmation_context):
    authentication, _, runs, root, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    source, _ = prepare_valid(client, project_id)
    assert client.post(confirm_url(project_id)).status_code == 200

    assert add_text(client, project_id, content="New evidence").status_code == 409
    assert upload(client, project_id).status_code == 409
    assert upload(
        client,
        project_id,
        source_type="IMAGE",
        artifact_type="UI_FLOW",
        origin="AGENT_2",
        filename="flow.png",
        content=PNG,
        content_type="image/png",
    ).status_code == 409
    assert client.delete(
        f"{sources_url(project_id)}/{source['source_id']}"
    ).status_code == 409
    assert select_outputs(client, project_id, ["SECURITY_TEST_CASES"]).status_code == 409
    assert client.get(sources_url(project_id)).status_code == 200
    workflow = client.get(workflow_url(project_id))
    assert workflow.status_code == 200
    assert workflow.json()["data"]["selected_outputs"] == ["UNIT_TEST_CASES"]
    input_names = {path.name for path in (root / project_id / "inputs").iterdir()}
    assert input_names == {f"{source['source_id']}.source.json"}
    assert runs.documents == {}


def test_failed_atomic_save_leaves_unconfirmed_workflow(
    confirmation_context, monkeypatch
):
    authentication, _, _, root, storage = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    prepare_valid(client, project_id)
    path = root / project_id / "workflow.json"
    before = path.read_bytes()
    original_save = storage.save

    def fail_confirmation(record):
        if record.n1_confirmation is not None:
            raise Agent4WorkflowStorageError("injected failure")
        original_save(record)

    monkeypatch.setattr(storage, "save", fail_confirmation)
    response = client.post(confirm_url(project_id))

    assert response.status_code == 503
    assert path.read_bytes() == before
    persisted = storage.load(
        agent_project_id=project_id, owner_user_id="USR-001"
    )
    assert persisted.n1_confirmation is None
    assert persisted.current_node_id.value == "INPUT_OUTPUT_SETUP"


def test_existing_workflow_without_confirmation_remains_unconfirmed(
    confirmation_context,
):
    authentication, _, _, root, _ = confirmation_context
    client = authentication.client()
    project_id = create_project(client)
    workflow = client.get(workflow_url(project_id)).json()["data"]
    path = root / project_id / "workflow.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("n1_confirmation")
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    before = path.read_bytes()

    response = client.get(workflow_url(project_id))

    assert response.status_code == 200
    projected = response.json()["data"]
    assert projected["n1_confirmation"] is None
    assert projected["pipeline_status"] == "WAITING_FOR_HUMAN"
    assert projected["schema_version"] == AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION
    assert projected["workflow_version"] == AGENT4_TEST_GENERATION_WORKFLOW_VERSION
    assert path.read_bytes() == before
    assert workflow["n1_confirmation"] is None


def test_concurrent_confirmation_returns_one_identity(confirmation_context):
    authentication, _, _, _, _ = confirmation_context
    owner = authentication.client()
    project_id = create_project(owner)
    prepare_valid(owner, project_id)

    def confirm():
        return authentication.client().post(confirm_url(project_id))

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: confirm(), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    identities = {
        response.json()["data"]["n1_confirmation"]["confirmation_id"]
        for response in responses
    }
    assert len(identities) == 1


def test_confirmation_security_boundaries(confirmation_context):
    authentication, projects, runs, root, _ = confirmation_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project_id = create_project(owner)
    prepare_valid(owner, project_id)

    assert foreign.post(confirm_url(project_id)).status_code == 404
    assert owner.post(confirm_url("AGP-999")).status_code == 404
    assert owner.post(confirm_url("invalid")).status_code == 422
    for agent_type in ("REQUIREMENTS", "DESIGN_PLANNING", "IMPLEMENTATION"):
        assert owner.post(confirm_url(create_project(owner, agent_type))).status_code == 422

    projects.documents[project_id]["agent_stage"] = None
    assert owner.post(confirm_url(project_id)).status_code == 409
    projects.documents[project_id]["agent_stage"] = "VALIDATION"
    assert owner.post(confirm_url(project_id)).status_code == 409
    projects.documents[project_id]["agent_stage"] = "TEST_GENERATION"
    projects.documents[project_id]["status"] = "ARCHIVED"
    assert owner.post(confirm_url(project_id)).status_code == 409
    assert runs.documents == {}
    assert json.loads((root / project_id / "workflow.json").read_text())["n1_confirmation"] is None
