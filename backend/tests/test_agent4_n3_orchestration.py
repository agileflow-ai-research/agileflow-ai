import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from pydantic import ValidationError

from app.modules.agents.testing_validation.intelligence.effective.service import (
    Agent4EffectiveClassificationService,
)
from app.modules.agents.testing_validation.intelligence.effective.storage import (
    Agent4EffectiveStorage,
)
from app.modules.agents.testing_validation.intelligence.hybrid.storage import Agent4HybridStorage
from app.modules.agents.testing_validation.intelligence.rules.storage import Agent4RuleStorage
from app.modules.agents.testing_validation.intelligence.semantic.storage import Agent4SemanticStorage
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TESTING_INTELLIGENCE_TAXONOMY,
)
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import Agent4ZeroShotStorage
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
from app.modules.agents.testing_validation.workflow.orchestration.n3_service import (
    Agent4N3ReviewError,
    Agent4N3OrchestrationService,
)
from app.modules.agents.testing_validation.workflow.orchestration.n3_progression import (
    derive_n3_execution_status,
    get_next_n3_substage,
    new_n3_sub_stages,
)
from app.modules.agents.testing_validation.workflow.orchestration.executor import (
    AGENT4_N3_MAX_WORKERS,
)
from app.main import app
from app.modules.agents.testing_validation.router import (
    get_agent4_n3_orchestration_service,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N3ReviewSubmission,
    Agent4N3ReviewResolutionRequest,
    Agent4N3ExecutionStatus,
    Agent4N3SourceStatus,
    Agent4N3SubStageName,
    Agent4N3SubStageStatus,
)
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from test_agent4_hybrid_classification import hybrid_service
from test_agent4_n2_orchestration import (
    ControlledExecutor,
    add_text,
    confirm,
    create_project,
    load,
    n2_context,
    upload,
)
from test_agent4_rule_classification import service_for as rule_service
from test_agent4_semantic_facts import FakeSemanticRuntime, behavior_output, semantic_service
from test_agent4_zero_shot_classification import FakeRuntime, service_for as zero_service
from test_standalone_foundation import user


def n3_service(context, scores=None, *, n4_handoff=None):
    root = context[3]
    executor = ControlledExecutor()
    service = Agent4N3OrchestrationService(
        context[1]._workflow_service,
        Agent4WorkflowStorage(root),
        Agent4ChunkStorage(root),
        rule_service(context),
        zero_service(context, FakeRuntime(scores=scores or [0.1] * 15)),
        hybrid_service(context),
        semantic_service(context, FakeSemanticRuntime([behavior_output()] * 4)),
        Agent4EffectiveClassificationService(Agent4EffectiveStorage(root)),
        Agent4HybridStorage(root),
        Agent4RuleStorage(root),
        Agent4ZeroShotStorage(root),
        executor=executor,
        n4_handoff=n4_handoff,
    )
    return service, executor


def prepare_n3(context, *contents):
    client, _, n2_executor, *_ = context
    project_id = create_project(client)
    sources = [add_text(client, project_id, content) for content in contents]
    confirm(client, project_id)
    n2_executor.drain()
    service, executor = n3_service(context)
    return project_id, sources, service, executor


def waiting_n3(context):
    project_id, sources, service, executor = prepare_n3(
        context, "The system shall create a booking."
    )
    service.start(project_id, user())
    executor.drain()
    return project_id, sources[0], service, executor


def test_n3_waits_for_atomic_review_then_resumes_without_mutating_h1(n2_context):
    client, _, n2_executor, root, _, runs, *_ = n2_context
    project_id = create_project(client)
    source = add_text(client, project_id, "The system shall create a booking.")
    sibling = add_text(client, project_id, "A neutral source statement.")
    confirm(client, project_id)
    n2_executor.drain()
    service, executor = n3_service(n2_context, [0.1, 0.9] + [0.1] * 12 + [0.99])
    original_infer = service._zero._classifier._runtime.infer

    def source_specific_scores(texts, **kwargs):
        runtime = service._zero._classifier._runtime
        configured = runtime.scores
        if any("neutral" in text.lower() for text in texts):
            runtime.scores = [0.1] * 15
        try:
            return original_infer(texts, **kwargs)
        finally:
            runtime.scores = configured

    service._zero._classifier._runtime.infer = source_specific_scores
    calls = {name: [] for name in ("rules", "zero", "hybrid", "semantic")}
    for name, stage in (
        ("rules", service._rules), ("zero", service._zero),
        ("hybrid", service._hybrid), ("semantic", service._semantic),
    ):
        original = stage.build

        def recording(*args, _name=name, _original=original, **kwargs):
            calls[_name].append(args[1])
            return _original(*args, **kwargs)

        setattr(stage, "build", recording)

    queued = service.start(project_id, user())
    assert queued.n3_execution.status == "QUEUED"
    assert queued.n3_execution.trigger == "LEGACY_START"
    executor.drain()
    waiting = service.get(project_id, user())
    assert waiting.n3_execution.status == "WAITING_FOR_HUMAN"
    assert waiting.pipeline_status == "WAITING_FOR_HUMAN"
    assert next(item for item in waiting.n3_execution.sources if item.source_id == sibling["source_id"]).status == "QUEUED"
    assert service._semantic._runtime.prompts == []
    semantic_path = root / project_id / "intelligence" / f"{source['source_id']}.semantic-facts.json"
    assert not semantic_path.exists()
    review = service.review_projection(project_id, user())
    assert review.items
    hybrid_path = root / project_id / "intelligence" / f"{source['source_id']}.hybrid.json"
    before_hybrid = hybrid_path.read_bytes()
    immutable_paths = [
        root / project_id / "inputs" / f"{source['source_id']}.source.json",
        root / project_id / "preparation" / f"{source['source_id']}.normalized.json",
        root / project_id / "preparation" / f"{source['source_id']}.chunks.json",
        root / project_id / "intelligence" / f"{source['source_id']}.rules.json",
        root / project_id / "intelligence" / f"{source['source_id']}.zero-shot.json",
        hybrid_path,
    ]
    immutable_before = {path: path.read_bytes() for path in immutable_paths}
    n1_before = load(client, project_id)["n1_confirmation"]

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
    assert resumed.n3_execution.execution_id != waiting.n3_execution.execution_id
    assert resumed.n3_execution.attempt_number == 2
    assert len(executor.tasks) == 1
    assert executor.tasks[0][1][1] == resumed.n3_execution.execution_id
    executor.drain()
    completed = load(client, project_id)
    assert completed["nodes"][2]["status"] == "COMPLETED"
    assert completed["nodes"][3]["status"] == "COMPLETED"
    assert completed["current_node_id"] == "CONTEXT_TESTABILITY"
    assert completed["nodes"][4]["status"] == "NOT_STARTED"
    assert hybrid_path.read_bytes() == before_hybrid
    assert all(path.read_bytes() == content for path, content in immutable_before.items())
    assert load(client, project_id)["n1_confirmation"] == n1_before
    assert (root / project_id / "intelligence" / f"{source['source_id']}.effective-classification.json").is_file()
    effective = json.loads(
        (root / project_id / "intelligence" / f"{source['source_id']}.effective-classification.json").read_text(encoding="utf-8")
    )
    result = effective["results"][0]
    assert len(result["decisions"]) == 15
    assert len(result["accepted_labels"] + result["rejected_labels"]) == 15
    assert [item["label"] for item in result["decisions"]] == [
        item.value for item in TESTING_INTELLIGENCE_TAXONOMY
    ]
    assert "REVIEW_REQUIRED" not in {item["status"] for item in result["decisions"]}
    assert {item["origin"] for item in result["decisions"]} >= {
        "H1_AUTO_ACCEPTED", "H1_AUTO_REJECTED", "HUMAN_ACCEPTED",
    }
    assert result["hybrid_result_id"]
    assert result["review_id"]
    resumed_semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    assert resumed_semantic["effective_manifest_fingerprint"]
    assert resumed_semantic["waiting_review_chunk_ids"] == []
    immutable_hybrid = json.loads(hybrid_path.read_text(encoding="utf-8"))
    assert any(
        decision["status"] == "REVIEW_REQUIRED"
        for hybrid_result in immutable_hybrid["results"]
        for decision in hybrid_result["decisions"]
    )
    assert service._semantic._runtime.prompts
    assert "NON_TESTABLE_CONTEXT" not in service._semantic._runtime.prompts[-1]
    assert review.items[0].label in service._semantic._runtime.prompts[-1]
    for stage_name in ("rules", "zero", "hybrid"):
        assert calls[stage_name].count(source["source_id"]) == 1
        assert calls[stage_name].count(sibling["source_id"]) == 1
    assert calls["semantic"].count(source["source_id"]) == 1
    assert calls["semantic"].count(sibling["source_id"]) == 1
    assert runs.documents == {}


def test_waiting_attempt_is_not_active_and_cannot_block_review_resume(n2_context):
    project_id, _, service, executor = prepare_n3(
        n2_context, "The system shall create a booking."
    )
    queued = service.start(project_id, user())
    first_id = queued.n3_execution.execution_id
    assert first_id in Agent4N3OrchestrationService._active_execution_ids

    executor.drain()
    waiting = service.get(project_id, user())
    assert waiting.n3_execution.status == "WAITING_FOR_HUMAN"
    assert first_id not in Agent4N3OrchestrationService._active_execution_ids

    review = service.review_projection(project_id, user())
    resumed = service.submit_review(
        project_id,
        Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=review.review_snapshot_fingerprint,
            resolutions=[
                {"chunk_id": item.chunk_id, "label": item.label, "decision": "REJECT"}
                for item in review.items
            ],
        ),
        user(),
    )
    second_id = resumed.n3_execution.execution_id
    assert second_id != first_id
    assert resumed.n3_execution.trigger == "HUMAN_REVIEW_RESUME"
    assert second_id in Agent4N3OrchestrationService._active_execution_ids
    assert len(executor.tasks) == 1
    assert executor.tasks[0][1][1] == second_id

    executor.drain()
    assert service.get(project_id, user()).n3_execution.status == "COMPLETED"
    assert second_id not in Agent4N3OrchestrationService._active_execution_ids


def test_review_post_returns_queued_and_workflow_get_does_not_wait_for_semantic_runtime(
    n2_context, monkeypatch,
):
    client = n2_context[0]
    project_id, _, service, executor = waiting_n3(n2_context)
    review = service.review_projection(project_id, user())
    semantic_entered = Event()
    release_semantic = Event()
    original_generate = service._semantic._runtime.generate

    def blocking_generate(prompt):
        semantic_entered.set()
        release_semantic.wait(timeout=5)
        return original_generate(prompt)

    monkeypatch.setattr(service._semantic._runtime, "generate", blocking_generate)
    app.dependency_overrides[get_agent4_n3_orchestration_service] = lambda: service
    try:
        review_response = client.post(
            f"/api/v1/agents/testing-validation/{project_id}/test-generation/workflow/n3/review",
            json={
                "review_snapshot_fingerprint": review.review_snapshot_fingerprint,
                "resolutions": [
                    {"chunk_id": item.chunk_id, "label": item.label, "decision": "ACCEPT"}
                    for item in review.items
                ],
            },
        )
        assert review_response.status_code == 200
        assert review_response.json()["data"]["n3_execution"]["status"] == "QUEUED"
        assert len(executor.tasks) == 1
        worker_function, worker_args = executor.tasks.pop(0)

        with ThreadPoolExecutor(max_workers=2) as pool:
            worker = pool.submit(worker_function, *worker_args)
            worker.result(timeout=2)
            assert len(executor.tasks) == 1
            queued_fact = service.get(project_id, user())
            assert queued_fact.current_node_id == "TESTING_FACT_EXTRACTION"
            assert queued_fact.nodes[2].status == "COMPLETED"
            assert queued_fact.nodes[3].status == "QUEUED"
            semantic_function, semantic_args = executor.tasks.pop(0)
            semantic_worker = pool.submit(semantic_function, *semantic_args)
            assert semantic_entered.wait(timeout=2)
            started = time.monotonic()
            workflow_request = pool.submit(
                client.get,
                f"/api/v1/agents/testing-validation/{project_id}/test-generation/workflow",
            )
            workflow_response = workflow_request.result(timeout=2)
            assert time.monotonic() - started < 2
            assert workflow_response.status_code == 200
            payload = workflow_response.json()["data"]
            assert payload["n3_execution"]["status"] == "RUNNING"
            assert payload["n3_execution"]["sources"][0]["status"] == "SEMANTIC_EXTRACTION"
            release_semantic.set()
            semantic_worker.result(timeout=5)
    finally:
        release_semantic.set()
        app.dependency_overrides.pop(get_agent4_n3_orchestration_service, None)


def test_review_resume_submission_failure_is_durable_and_retryable(n2_context):
    class RejectingExecutor:
        def submit(self, *_args, **_kwargs):
            raise RuntimeError("private executor detail")

    project_id, source, service, _ = waiting_n3(n2_context)
    review = service.review_projection(project_id, user())
    service._executor = RejectingExecutor()

    result = service.submit_review(
        project_id,
        Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=review.review_snapshot_fingerprint,
            resolutions=[
                {"chunk_id": item.chunk_id, "label": item.label, "decision": "REJECT"}
                for item in review.items
            ],
        ),
        user(),
    )

    assert result.n3_execution.trigger == "HUMAN_REVIEW_RESUME"
    assert result.n3_execution.status == "FAILED"
    assert result.n3_execution.retryable is True
    assert result.n3_execution.error.code == "N3_EXECUTOR_UNAVAILABLE"
    assert "private" not in result.n3_execution.error.message
    record = service._workflow.load(
        agent_project_id=project_id, owner_user_id=user().user_id,
    )
    assert len(record.n3_review_history) == 1
    assert record.n3_executions[0].status == "WAITING_FOR_HUMAN"
    assert record.n3_executions[1].status == "FAILED"
    assert service._effective._storage.load(
        agent_project_id=project_id,
        owner_user_id=user().user_id,
        source_id=source["source_id"],
    ) is not None
    effective_stage = next(
        item for item in record.n3_executions[1].sources[0].sub_stages
        if item.stage == "TI_EFFECTIVE_CLASSIFICATION"
    )
    assert effective_stage.status == "COMPLETED"
    assert effective_stage.retryable is False


def test_semantic_failure_after_review_retries_without_repeating_human_review(
    n2_context, monkeypatch,
):
    project_id, source, service, executor = waiting_n3(n2_context)
    review = service.review_projection(project_id, user())
    root = n2_context[3]
    immutable_paths = [
        root / project_id / "intelligence" / f"{source['source_id']}.rules.json",
        root / project_id / "intelligence" / f"{source['source_id']}.zero-shot.json",
        root / project_id / "intelligence" / f"{source['source_id']}.hybrid.json",
    ]
    immutable_before = {path: path.read_bytes() for path in immutable_paths}
    original_semantic = service._semantic.build
    fail = {"enabled": True}

    def semantic(*args, **kwargs):
        if fail["enabled"]:
            raise RuntimeError("temporary semantic failure")
        return original_semantic(*args, **kwargs)

    monkeypatch.setattr(service._semantic, "build", semantic)
    service.submit_review(
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
    executor.drain()
    failed = service.get(project_id, user())
    assert failed.n3_execution.status == "FAILED"
    assert failed.n3_execution.sources[0].failed_stage == "TI_FACT_EXTRACTION"

    fail["enabled"] = False
    retried = service.retry_source(project_id, source["source_id"], user())
    assert retried.n3_execution.trigger == "SOURCE_RETRY"
    assert retried.n3_execution.review_id == failed.n3_execution.review_id
    executor.drain()

    completed = service.get(project_id, user())
    assert completed.n3_execution.status == "COMPLETED"
    record = service._workflow.load(
        agent_project_id=project_id, owner_user_id=user().user_id,
    )
    assert len(record.n3_review_history) == 1
    assert all(path.read_bytes() == immutable_before[path] for path in immutable_paths)


@pytest.mark.parametrize("changed_evidence", ["chunks", "hybrid"])
def test_review_snapshot_is_deterministic_trusted_and_stale_evidence_is_rejected(
    n2_context, changed_evidence
):
    project_id, source, service, _ = waiting_n3(n2_context)
    first = service.review_projection(project_id, user())
    second = service.review_projection(project_id, user())

    assert first == second
    assert first.items
    assert all(item.chunk_context == "The system shall create a booking." for item in first.items)
    assert all(item.relationship and item.model_score is not None for item in first.items)
    assert all(item.hybrid_result_id and item.hybrid_manifest_fingerprint for item in first.items)
    assert all(item.label not in item.auto_accepted_labels for item in first.items)
    assert first.pending_review_count == len(first.items)
    assert first.auto_accepted_count + first.auto_rejected_count + first.pending_review_count == 15
    assert sum(first.review_relationship_counts.values()) == first.pending_review_count
    assert sum(first.auto_accepted_label_counts.values()) == first.auto_accepted_count
    serialized = first.model_dump_json().casefold()
    assert "reviewer_user_id" not in serialized and "storage" not in serialized
    assert "logits" not in serialized and "vector" not in serialized

    root = n2_context[3]
    if changed_evidence == "chunks":
        evidence_path = root / project_id / "preparation" / f"{source['source_id']}.chunks.json"
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
        document["chunk_set_fingerprint"] = "f" * 64
    else:
        evidence_path = root / project_id / "intelligence" / f"{source['source_id']}.hybrid.json"
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
        document["results"][0]["decisions"][0]["explanation"] = "Changed after snapshot."
    evidence_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(Agent4N3ReviewError, match="stale"):
        service.submit_review(project_id, Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=first.review_snapshot_fingerprint,
            resolutions=[
                {"chunk_id": item.chunk_id, "label": item.label, "decision": "ACCEPT"}
                for item in first.items
            ],
        ), user())


def test_review_submission_is_atomic_strict_append_only_and_supports_reject(n2_context):
    project_id, _, service, executor = waiting_n3(n2_context)
    review = service.review_projection(project_id, user())
    item = review.items[0]

    with pytest.raises(Agent4N3ReviewError, match="Duplicate"):
        service.submit_review(project_id, Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=review.review_snapshot_fingerprint,
            resolutions=[
                {"chunk_id": item.chunk_id, "label": item.label, "decision": "ACCEPT"},
                {"chunk_id": item.chunk_id, "label": item.label, "decision": "REJECT"},
            ],
        ), user())
    with pytest.raises(Agent4N3ReviewError, match="Exactly one"):
        service.submit_review(project_id, Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=review.review_snapshot_fingerprint,
            resolutions=[
                {"chunk_id": item.chunk_id, "label": "UNKNOWN_LABEL", "decision": "ACCEPT"}
            ],
        ), user())
    with pytest.raises(Agent4N3ReviewError, match="Exactly one"):
        service.submit_review(project_id, Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=review.review_snapshot_fingerprint,
            resolutions=[{
                "chunk_id": item.chunk_id,
                "label": "INPUT_VALIDATION",
                "decision": "ACCEPT",
            }],
        ), user())
    with pytest.raises(Agent4N3ReviewError, match="stale"):
        service.submit_review(project_id, Agent4N3ReviewSubmission(
            review_snapshot_fingerprint="0" * 64,
            resolutions=[
                {"chunk_id": pending.chunk_id, "label": pending.label, "decision": "ACCEPT"}
                for pending in review.items
            ],
        ), user())
    with pytest.raises(ValidationError):
        Agent4N3ReviewResolutionRequest(
            chunk_id=item.chunk_id, label=item.label, decision="ACCEPT", note="x" * 1001
        )

    queued = service.submit_review(project_id, Agent4N3ReviewSubmission(
        review_snapshot_fingerprint=review.review_snapshot_fingerprint,
        resolutions=[
            {
                "chunk_id": pending.chunk_id,
                "label": pending.label,
                "decision": "REJECT",
                "note": "  reviewed by owner  ",
            }
            for pending in review.items
        ],
    ), user())
    assert queued.n3_execution.trigger == "HUMAN_REVIEW_RESUME"
    assert queued.n3_execution.attempt_number == 2
    record = service._workflow.load(agent_project_id=project_id, owner_user_id=user().user_id)
    assert len(record.n3_review_history) == 1
    assert record.n3_review_history[0].reviewer_user_id == user().user_id
    assert all(resolution.note == "reviewed by owner" for resolution in record.n3_review_history[0].resolutions)
    executor.drain()
    effective = service._effective._storage.load(
        agent_project_id=project_id, owner_user_id=user().user_id,
        source_id=review.items[0].source_id,
    )
    assert any(item.origin == "HUMAN_REJECTED" for item in effective.results[0].decisions)
    assert service._semantic._runtime.prompts == []
    record = service._workflow.load(agent_project_id=project_id, owner_user_id=user().user_id)
    assert len(record.n3_review_history) == 1
    assert record.n3_executions[-1].status == "COMPLETED"
    semantic = Agent4SemanticStorage(n2_context[3]).load(
        agent_project_id=project_id,
        owner_user_id=user().user_id,
        source_id=review.items[0].source_id,
    )
    assert semantic.waiting_review_chunk_ids == []
    assert semantic.not_applicable_chunk_ids == semantic.chunk_ids


@pytest.mark.parametrize("status", ["QUEUED", "RUNNING"])
def test_orphaned_active_n3_is_recovered_without_fabricated_completion(n2_context, status):
    project_id, _, service, _ = prepare_n3(n2_context, "A neutral source statement.")
    queued = service.start(project_id, user())
    record = service._workflow.load(agent_project_id=project_id, owner_user_id=user().user_id)
    record.n3_executions[-1].status = Agent4N3ExecutionStatus(status)
    service._workflow.save(record)
    Agent4N3OrchestrationService._active_execution_ids.clear()

    recovered = service.get(project_id, user())
    assert queued.n3_execution.execution_id != recovered.n3_execution.execution_id
    assert recovered.n3_execution.trigger == "RESTART_RECOVERY"
    assert recovered.n3_execution.status == "QUEUED"
    assert recovered.n3_execution.completed_at is None
    assert recovered.nodes[2].status == "QUEUED"
    persisted = service._workflow.load(
        agent_project_id=project_id, owner_user_id=user().user_id,
    )
    assert persisted.n3_executions[0].status == "INTERRUPTED"
    assert persisted.n3_executions[0].completed_at is None


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


def test_semantic_queue_cannot_starve_testing_intelligence_orchestration():
    # A project waiting behind Qwen must not occupy a general N3 lane and
    # prevent another project's N2 -> Testing Intelligence handoff.
    first_started = Event()
    release_first = Event()
    second_started = Event()

    def occupy_first_lane():
        first_started.set()
        release_first.wait(timeout=5)

    with (
        ThreadPoolExecutor(max_workers=1) as semantic_executor,
        ThreadPoolExecutor(max_workers=AGENT4_N3_MAX_WORKERS) as executor,
    ):
        first = semantic_executor.submit(occupy_first_lane)
        assert first_started.wait(timeout=1)
        second = executor.submit(second_started.set)
        try:
            assert second_started.wait(timeout=1)
            second.result(timeout=1)
        finally:
            release_first.set()
            first.result(timeout=1)


def test_n2_completion_background_runner_enters_running_without_frontend_request(
    n2_context, monkeypatch,
):
    client, n2, n2_executor, *_ = n2_context
    service, _ = n3_service(n2_context)
    entered_rules = Event()
    release_rules = Event()
    original_rules = service._rules.build

    def blocking_rules(*args, **kwargs):
        entered_rules.set()
        assert release_rules.wait(timeout=5)
        return original_rules(*args, **kwargs)

    monkeypatch.setattr(service._rules, "build", blocking_rules)
    with ThreadPoolExecutor(max_workers=1) as runner:
        service._executor = runner
        n2._n3_handoff = service.start_after_n2
        project_id = create_project(client)
        add_text(client, project_id, "A neutral source statement.")
        confirm(client, project_id)

        n2_executor.drain()
        assert entered_rules.wait(timeout=2)
        persisted = service._workflow.load(
            agent_project_id=project_id, owner_user_id=user().user_id,
        )
        assert persisted.n2_executions[-1].status == "COMPLETED"
        assert persisted.n3_executions[-1].trigger == "N2_COMPLETION"
        assert persisted.n3_executions[-1].status == "RUNNING"
        assert persisted.nodes[2].status == "RUNNING"
        release_rules.set()


def test_n3_reserves_execution_before_publishing_queued_state(
    n2_context, monkeypatch,
):
    project_id, _, service, executor = prepare_n3(
        n2_context, "A neutral source statement."
    )
    original_save = service._workflow.save
    queued_saves = []

    def checked_save(record):
        current = (
            record.n3_executions[-1] if record.n3_executions else None
        )
        if current is not None and current.status == "QUEUED":
            queued_saves.append(current.execution_id)
            assert (
                current.execution_id
                in Agent4N3OrchestrationService._active_execution_ids
            )
        result = original_save(record)
        if current is not None and current.status == "QUEUED":
            concurrent_projection = service.get(project_id, user())
            assert concurrent_projection.n3_execution.status == "QUEUED"
        return result

    monkeypatch.setattr(service._workflow, "save", checked_save)
    queued = service.start(project_id, user())

    assert queued_saves == [queued.n3_execution.execution_id]
    assert len(executor.tasks) == 1
    executor.drain()


def test_initial_n3_workflow_get_remains_observable_during_zero_shot_inference(
    n2_context, monkeypatch,
):
    client = n2_context[0]
    project_id, _, service, executor = prepare_n3(
        n2_context, "A neutral source statement."
    )
    inference_entered = Event()
    release_inference = Event()
    original_infer = service._zero._classifier._runtime.infer

    def blocking_infer(*args, **kwargs):
        inference_entered.set()
        assert release_inference.wait(timeout=5)
        return original_infer(*args, **kwargs)

    monkeypatch.setattr(
        service._zero._classifier._runtime, "infer", blocking_infer
    )
    app.dependency_overrides[get_agent4_n3_orchestration_service] = lambda: service
    try:
        service.start(project_id, user())
        worker_function, worker_args = executor.tasks.pop(0)
        with ThreadPoolExecutor(max_workers=2) as pool:
            worker = pool.submit(worker_function, *worker_args)
            assert inference_entered.wait(timeout=2)
            workflow_request = pool.submit(
                client.get,
                f"/api/v1/agents/testing-validation/{project_id}/test-generation/workflow",
            )
            response = workflow_request.result(timeout=2)
            assert response.status_code == 200
            payload = response.json()["data"]
            assert payload["n3_execution"]["status"] == "RUNNING"
            assert (
                payload["n3_execution"]["sources"][0]["status"]
                == "ZERO_SHOT_CLASSIFICATION"
            )
            release_inference.set()
            worker.result(timeout=5)
    finally:
        release_inference.set()
        app.dependency_overrides.pop(get_agent4_n3_orchestration_service, None)


def test_n3_runs_stages_in_order_once_and_hands_off_to_unstarted_n4(n2_context, monkeypatch):
    project_id, _, service, executor = prepare_n3(n2_context, "A neutral source statement.")
    calls = []
    for name, stage in (
        ("rules", service._rules), ("zero", service._zero),
        ("hybrid", service._hybrid), ("semantic", service._semantic),
    ):
        original = stage.build

        def recording(*args, _name=name, _original=original, **kwargs):
            current = service._workflow.load(
                agent_project_id=project_id, owner_user_id=user().user_id
            )
            execution = current.n3_executions[-1]
            if _name == "semantic":
                assert current.current_node_id == "TESTING_FACT_EXTRACTION"
                assert current.nodes[2].status == "COMPLETED"
                assert current.nodes[3].status == "QUEUED"
            assert execution.status == "RUNNING"
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(stage, "build", recording)

    first = service.start(project_id, user())
    duplicate = service.start(project_id, user())
    assert first.n3_execution.execution_id == duplicate.n3_execution.execution_id
    assert first.n3_execution.status == "QUEUED"
    assert len(executor.tasks) == 1
    executor.drain()

    completed = service.get(project_id, user())
    assert calls == ["rules", "zero", "hybrid", "semantic"]
    assert completed.n3_execution.status == "COMPLETED"
    assert completed.n3_execution_count == 1
    assert [node.status.value for node in completed.nodes] == [
        "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED",
        "NOT_STARTED", "LOCKED", "LOCKED",
    ]
    assert completed.current_node_id == "CONTEXT_TESTABILITY"
    assert completed.pipeline_status == "RUNNING"
    assert service.start(project_id, user()).n3_execution_count == 1
    names = [path.name.lower() for path in (n2_context[3] / project_id).rglob("*") if path.is_file()]
    assert not any(
        marker in name
        for name in names
        for marker in ("traceability", "readiness", "testability-result", "feasibility")
    )


def test_new_successful_n3_completion_leaves_n4_not_started(n2_context):
    calls = []

    def handoff(project_id, owner_id, execution_id, current_user):
        persisted = Agent4WorkflowStorage(n2_context[3]).load(
            agent_project_id=project_id, owner_user_id=owner_id,
        )
        assert persisted.n3_executions[-1].status is Agent4N3ExecutionStatus.COMPLETED
        calls.append((project_id, owner_id, execution_id, current_user.user_id))

    client, _, n2_executor, *_ = n2_context
    project_id = create_project(client)
    add_text(client, project_id, "A neutral source statement.")
    confirm(client, project_id)
    n2_executor.drain()
    service, executor = n3_service(n2_context, n4_handoff=handoff)
    service.start(project_id, user())
    executor.drain()

    result = service.get(project_id, user())
    assert calls == []
    assert result.current_node_id == "CONTEXT_TESTABILITY"
    assert result.n4_execution is None
    assert next(
        node for node in result.nodes if node.node_id == "CONTEXT_TESTABILITY"
    ).status == "NOT_STARTED"


def test_n3_executor_submission_failure_preserves_completed_n2_and_is_retryable(n2_context):
    class RejectingExecutor:
        def submit(self, *_args, **_kwargs):
            raise RuntimeError("executor internals must not escape")

    project_id, _, service, _ = prepare_n3(n2_context, "A neutral source statement.")
    service._executor = RejectingExecutor()
    result = service.start(project_id, user())

    assert result.n2_execution.status == "COMPLETED"
    assert result.n3_execution.status == "FAILED"
    assert result.n3_execution.retryable is True
    assert result.n3_execution.error.code == "N3_EXECUTOR_UNAVAILABLE"
    assert "internals" not in result.n3_execution.error.message


@pytest.mark.parametrize("stage_name", ["_rules", "_zero", "_hybrid", "_semantic"])
def test_each_n3_stage_failure_is_source_isolated_and_safely_reported(
    n2_context, monkeypatch, stage_name
):
    project_id, sources, service, executor = prepare_n3(
        n2_context, "Neutral source one.", "Neutral source two."
    )
    stage = getattr(service, stage_name)
    original = stage.build

    def fail_one(_project_id, source_id, *args, **kwargs):
        if source_id == sources[0]["source_id"]:
            raise RuntimeError("private traceback material")
        return original(_project_id, source_id, *args, **kwargs)

    monkeypatch.setattr(stage, "build", fail_one)
    service.start(project_id, user())
    executor.drain()
    result = service.get(project_id, user())
    progress = {item.source_id: item for item in result.n3_execution.sources}

    assert result.n3_execution.status == "FAILED"
    assert progress[sources[0]["source_id"]].status == "FAILED"
    assert progress[sources[1]["source_id"]].status == "COMPLETE"
    expected_code = {
        "_rules": "TI_RULE_ANALYSIS_FAILED",
        "_zero": "TI_AI_CLASSIFICATION_FAILED",
        "_hybrid": "TI_HYBRID_DECISION_FAILED",
        "_semantic": "TI_FACT_EXTRACTION_FAILED",
    }[stage_name]
    assert progress[sources[0]["source_id"]].error.code == expected_code
    assert "traceback" not in progress[sources[0]["source_id"]].error.message
    assert (n2_context[3] / project_id / "intelligence").is_dir()


def test_targeted_retry_is_append_only_skips_successful_sibling_and_completes(
    n2_context, monkeypatch
):
    project_id, sources, service, executor = prepare_n3(
        n2_context, "Neutral source one.", "Neutral source two."
    )
    original = service._semantic.build
    calls = []
    fail = {"enabled": True}

    def semantic(_project_id, source_id, *args, **kwargs):
        calls.append(source_id)
        if fail["enabled"] and source_id == sources[0]["source_id"]:
            raise RuntimeError("temporary semantic failure")
        return original(_project_id, source_id, *args, **kwargs)

    monkeypatch.setattr(service._semantic, "build", semantic)
    service.start(project_id, user())
    executor.drain()
    assert service.get(project_id, user()).n3_execution.status == "FAILED"
    sibling_calls = calls.count(sources[1]["source_id"])

    fail["enabled"] = False
    queued = service.retry_source(project_id, sources[0]["source_id"], user())
    assert queued.n3_execution.attempt_number == 2
    assert queued.n3_execution.trigger == "SOURCE_RETRY"
    with pytest.raises(Exception, match="no retryable execution"):
        service.retry_source(project_id, sources[0]["source_id"], user())
    executor.drain()
    completed = service.get(project_id, user())
    assert completed.n3_execution.status == "COMPLETED"
    assert completed.n3_execution_count == 2
    assert calls.count(sources[1]["source_id"]) == sibling_calls
    assert completed.n3_execution.sources[1].status == "COMPLETE"


def test_image_stays_truthful_pending_and_invokes_no_intelligence_stage(n2_context, monkeypatch):
    client, _, n2_executor, *_ = n2_context
    project_id = create_project(client)
    add_text(client, project_id, "A neutral source statement.")
    image = upload(
        client, project_id, "wireframe.png", b"\x89PNG\r\n\x1a\nminimal", "image/png",
        artifact_type="WIREFRAMES", source_type="IMAGE", normally_supplied_by="AGENT_2",
    )
    confirm(client, project_id)
    n2_executor.drain()
    service, executor = n3_service(n2_context)
    stage_sources = []
    for stage in (service._rules, service._zero, service._hybrid, service._semantic):
        original = stage.build

        def record(*args, _original=original, **kwargs):
            stage_sources.append(args[1])
            return _original(*args, **kwargs)

        monkeypatch.setattr(stage, "build", record)
    service.start(project_id, user())
    executor.drain()
    result = service.get(project_id, user())
    progress = next(item for item in result.n3_execution.sources if item.source_id == image["source_id"])

    assert progress.status == "PENDING_ANALYSIS"
    assert not any((progress.rules_complete, progress.zero_shot_complete, progress.hybrid_complete, progress.semantic_complete))
    assert image["source_id"] not in stage_sources
    assert result.n3_execution.status == "COMPLETED"


def test_no_review_path_persists_all_sub_stage_checkpoints(n2_context):
    project_id, _, service, executor = prepare_n3(
        n2_context, "A neutral source statement."
    )
    service.start(project_id, user())
    executor.drain()

    result = service.get(project_id, user()).n3_execution
    stages = {item.stage: item for item in result.sub_stages}
    assert result.status == "COMPLETED"
    assert stages["TI_RULE_ANALYSIS"].status == "COMPLETED"
    assert stages["TI_AI_CLASSIFICATION"].status == "COMPLETED"
    assert stages["TI_HYBRID_DECISION"].status == "COMPLETED"
    assert stages["TI_HUMAN_REVIEW"].status == "NOT_APPLICABLE"
    assert stages["TI_EFFECTIVE_CLASSIFICATION"].status == "COMPLETED"
    assert stages["TI_FACT_EXTRACTION"].status == "NOT_APPLICABLE"
    assert service._semantic._runtime.prompts == []


def test_valid_semantic_empty_is_terminal_success(n2_context):
    project_id, _, service, executor = prepare_n3(
        n2_context, "The system shall create a booking."
    )
    service._zero._classifier._runtime.scores = [0.1] * 14 + [0.99]
    service._semantic._runtime.outputs = ['{"facts":[]}']
    service.start(project_id, user())
    executor.drain()

    result = service.get(project_id, user()).n3_execution
    source = result.sources[0]
    fact_stage = next(
        item for item in source.sub_stages
        if item.stage == "TI_FACT_EXTRACTION"
    )
    assert result.status == "COMPLETED"
    assert fact_stage.status == "COMPLETED"
    assert fact_stage.summary["empty_chunk_count"] == 1
    assert source.fact_extraction_chunks[0].status == "EMPTY"


def test_grounding_failure_is_typed_and_persists_no_fact(n2_context):
    project_id, source_record, service, executor = prepare_n3(
        n2_context, "The system shall create a booking."
    )
    service._zero._classifier._runtime.scores = [0.1] * 14 + [0.99]
    unsupported = json.dumps({"facts": [{
        "fact_type": "BEHAVIOR",
        "related_labels": ["FUNCTIONAL_BEHAVIOR"],
        "evidence_quote": "The system shall invent unsupported evidence.",
        "action": "invent",
        "target": "evidence",
    }]})
    service._semantic._runtime.outputs = [unsupported, unsupported]
    service.start(project_id, user())
    executor.drain()

    result = service.get(project_id, user()).n3_execution
    failed = result.sources[0]
    stage = next(
        item for item in failed.sub_stages
        if item.stage == "TI_FACT_EXTRACTION"
    )
    assert result.status == "FAILED"
    assert stage.status == "FAILED"
    assert stage.safe_error.code == "SEMANTIC_GROUNDING_FAILED"
    semantic = Agent4SemanticStorage(n2_context[3]).load(
        agent_project_id=project_id,
        owner_user_id=user().user_id,
        source_id=source_record[0]["source_id"],
    )
    assert semantic is None


def test_restart_during_fact_extraction_creates_one_append_only_recovery_attempt(
    n2_context,
):
    project_id, _, service, _ = prepare_n3(
        n2_context, "A neutral source statement."
    )
    queued = service.start(project_id, user())
    record = service._workflow.load(
        agent_project_id=project_id, owner_user_id=user().user_id,
    )
    execution = record.n3_executions[-1]
    source = execution.sources[0]
    for stage in source.sub_stages:
        stage.status = Agent4N3SubStageStatus.COMPLETED
    fact = next(
        item for item in source.sub_stages
        if item.stage is Agent4N3SubStageName.FACT_EXTRACTION
    )
    fact.status = Agent4N3SubStageStatus.RUNNING
    source.status = Agent4N3SourceStatus.SEMANTIC_EXTRACTION
    source.semantic_complete = False
    execution.status = Agent4N3ExecutionStatus.RUNNING
    service._refresh_execution_sub_stages(execution)
    service._workflow.save(record)
    Agent4N3OrchestrationService._active_execution_ids.clear()

    recovered = service.get(project_id, user()).n3_execution
    stages = {item.stage: item.status for item in recovered.sources[0].sub_stages}
    assert recovered.execution_id != queued.n3_execution.execution_id
    assert recovered.trigger == "RESTART_RECOVERY"
    assert recovered.status == "QUEUED"
    assert stages["TI_EFFECTIVE_CLASSIFICATION"] == "COMPLETED"
    assert stages["TI_FACT_EXTRACTION"] == "QUEUED"
    again = service.get(project_id, user())
    assert again.n3_execution.execution_id == recovered.execution_id
    assert again.n3_execution_count == 2
    persisted = service._workflow.load(
        agent_project_id=project_id, owner_user_id=user().user_id,
    )
    assert persisted.n3_executions[0].status == "INTERRUPTED"
    assert persisted.n3_executions[0].error.code == "N3_EXECUTION_INTERRUPTED"


def test_fresh_service_recovers_review_resume_once_without_repeating_prior_stages(
    n2_context, monkeypatch,
):
    project_id, _, original, _ = waiting_n3(n2_context)
    review = original.review_projection(project_id, user())
    resumed = original.submit_review(
        project_id,
        Agent4N3ReviewSubmission(
            review_snapshot_fingerprint=review.review_snapshot_fingerprint,
            resolutions=[
                {"chunk_id": item.chunk_id, "label": item.label, "decision": "REJECT"}
                for item in review.items
            ],
        ),
        user(),
    )
    assert resumed.n3_execution.trigger == "HUMAN_REVIEW_RESUME"
    Agent4N3OrchestrationService._active_execution_ids.clear()

    fresh, executor = n3_service(n2_context)
    calls = {name: 0 for name in ("rules", "zero", "hybrid", "semantic")}
    for name, stage in (
        ("rules", fresh._rules), ("zero", fresh._zero),
        ("hybrid", fresh._hybrid), ("semantic", fresh._semantic),
    ):
        original_build = stage.build

        def record(*args, _name=name, _build=original_build, **kwargs):
            calls[_name] += 1
            return _build(*args, **kwargs)

        monkeypatch.setattr(stage, "build", record)

    recovered = fresh.get(project_id, user())
    repeated_get = fresh.get(project_id, user())
    assert recovered.n3_execution.trigger == "RESTART_RECOVERY"
    assert repeated_get.n3_execution.execution_id == recovered.n3_execution.execution_id
    assert len(executor.tasks) == 1
    executor.drain()

    completed = fresh.get(project_id, user())
    assert completed.n3_execution.status == "COMPLETED"
    assert completed.n3_execution_count == 3
    assert calls == {"rules": 0, "zero": 0, "hybrid": 0, "semantic": 1}
    record = fresh._workflow.load(
        agent_project_id=project_id, owner_user_id=user().user_id,
    )
    assert len(record.n3_review_history) == 1
    assert [item.status.value for item in record.n3_executions] == [
        "WAITING_FOR_HUMAN", "INTERRUPTED", "COMPLETED",
    ]


def test_pure_n3_transition_and_status_derivation_cover_review_and_retry():
    stages = new_n3_sub_stages()
    assert get_next_n3_substage(stages) is Agent4N3SubStageName.RULE_ANALYSIS
    stages[0].status = Agent4N3SubStageStatus.COMPLETED
    stages[1].status = Agent4N3SubStageStatus.COMPLETED
    stages[2].status = Agent4N3SubStageStatus.COMPLETED
    stages[3].status = Agent4N3SubStageStatus.WAITING_FOR_HUMAN
    assert get_next_n3_substage(stages) is Agent4N3SubStageName.HUMAN_REVIEW
    assert derive_n3_execution_status(stages) is Agent4N3ExecutionStatus.WAITING_FOR_HUMAN
    stages[3].status = Agent4N3SubStageStatus.COMPLETED
    stages[4].status = Agent4N3SubStageStatus.COMPLETED
    stages[5].status = Agent4N3SubStageStatus.FAILED
    assert get_next_n3_substage(stages) is Agent4N3SubStageName.FACT_EXTRACTION
    assert derive_n3_execution_status(stages) is Agent4N3ExecutionStatus.FAILED
    stages[5].status = Agent4N3SubStageStatus.COMPLETED
    assert get_next_n3_substage(stages) is None
    assert derive_n3_execution_status(stages) is Agent4N3ExecutionStatus.COMPLETED
