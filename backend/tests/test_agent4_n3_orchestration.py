import json

from app.modules.agents.testing_validation.intelligence.effective.service import (
    Agent4EffectiveClassificationService,
)
from app.modules.agents.testing_validation.intelligence.effective.storage import (
    Agent4EffectiveStorage,
)
from app.modules.agents.testing_validation.intelligence.hybrid.storage import Agent4HybridStorage
from app.modules.agents.testing_validation.intelligence.rules.storage import Agent4RuleStorage
from app.modules.agents.testing_validation.intelligence.semantic.storage import Agent4SemanticStorage
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import Agent4ZeroShotStorage
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
from app.modules.agents.testing_validation.workflow.orchestration.n3_service import (
    Agent4N3OrchestrationService,
)
from app.modules.agents.testing_validation.workflow.schemas import Agent4N3ReviewSubmission
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from test_agent4_hybrid_classification import hybrid_service
from test_agent4_n2_orchestration import (
    ControlledExecutor,
    add_text,
    confirm,
    create_project,
    load,
    n2_context,
)
from test_agent4_rule_classification import service_for as rule_service
from test_agent4_semantic_facts import FakeSemanticRuntime, behavior_output, semantic_service
from test_agent4_zero_shot_classification import FakeRuntime, service_for as zero_service
from test_standalone_foundation import user


def n3_service(context):
    root = context[3]
    executor = ControlledExecutor()
    service = Agent4N3OrchestrationService(
        context[1]._workflow_service,
        Agent4WorkflowStorage(root),
        Agent4ChunkStorage(root),
        rule_service(context),
        zero_service(context, FakeRuntime(scores=[0.1] * 15)),
        hybrid_service(context),
        semantic_service(context, FakeSemanticRuntime([behavior_output()] * 4)),
        Agent4EffectiveClassificationService(Agent4EffectiveStorage(root)),
        Agent4HybridStorage(root),
        Agent4RuleStorage(root),
        Agent4ZeroShotStorage(root),
        executor=executor,
    )
    return service, executor


def test_n3_waits_for_atomic_review_then_resumes_without_mutating_h1(n2_context):
    client, _, n2_executor, root, _, runs, *_ = n2_context
    project_id = create_project(client)
    source = add_text(client, project_id, "The system shall create a booking.")
    confirm(client, project_id)
    n2_executor.drain()
    service, executor = n3_service(n2_context)

    queued = service.start(project_id, user())
    assert queued.n3_execution.status == "QUEUED"
    assert queued.n3_execution.trigger == "LEGACY_START"
    executor.drain()
    waiting = service.get(project_id, user())
    assert waiting.n3_execution.status == "WAITING_FOR_HUMAN"
    assert waiting.pipeline_status == "WAITING_FOR_HUMAN"
    assert service._semantic._runtime.prompts == []
    review = service.review_projection(project_id, user())
    assert review.items
    hybrid_path = root / project_id / "intelligence" / f"{source['source_id']}.hybrid.json"
    before_hybrid = hybrid_path.read_bytes()

    resumed = service.submit_review(
        project_id,
        Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=review.review_snapshot_fingerprint,
            resolutions=[
                {"chunk_id": item.chunk_id, "label": item.label, "decision": "ACCEPT"}
                for item in review.items
            ],
        ),
        user(),
    )
    assert resumed.n3_execution.status == "QUEUED"
    assert resumed.n3_execution.trigger == "HUMAN_REVIEW_RESUME"
    executor.drain()
    completed = load(client, project_id)
    assert completed["nodes"][2]["status"] == "COMPLETED"
    assert completed["current_node_id"] == "CONTEXT_TESTABILITY"
    assert completed["nodes"][3]["status"] == "NOT_STARTED"
    assert hybrid_path.read_bytes() == before_hybrid
    assert (root / project_id / "intelligence" / f"{source['source_id']}.effective-classification.json").is_file()
    effective = json.loads(
        (root / project_id / "intelligence" / f"{source['source_id']}.effective-classification.json").read_text(encoding="utf-8")
    )
    result = effective["results"][0]
    assert len(result["decisions"]) == 15
    assert len(result["accepted_labels"] + result["rejected_labels"]) == 15
    assert any(item["origin"] == "HUMAN_ACCEPTED" for item in result["decisions"])
    assert service._semantic._runtime.prompts
    assert "NON_TESTABLE_CONTEXT" not in service._semantic._runtime.prompts[-1]
    assert runs.documents == {}


def test_new_n2_completion_queues_exactly_one_n3_execution(n2_context):
    client, n2, n2_executor, _, _, runs, *_ = n2_context
    service, n3_executor = n3_service(n2_context)
    n2._n3_handoff = service.start_after_n2
    project_id = create_project(client)
    add_text(client, project_id, "The system shall create a booking.")
    confirm(client, project_id)

    n2_executor.drain()
    workflow = load(client, project_id)
    assert workflow["n2_execution"]["status"] == "COMPLETED"
    assert workflow["n3_execution"]["status"] == "QUEUED"
    assert workflow["n3_execution"]["trigger"] == "N2_COMPLETION"
    assert workflow["n3_execution_count"] == 1
    assert len(n3_executor.tasks) == 1
    assert runs.documents == {}
