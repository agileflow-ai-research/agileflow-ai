import json

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
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N3ReviewSubmission,
    Agent4N3ReviewResolutionRequest,
    Agent4N3ExecutionStatus,
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
    assert next(item for item in waiting.n3_execution.sources if item.source_id == sibling["source_id"]).status == "COMPLETE"
    assert service._semantic._runtime.prompts == []
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
    executor.drain()
    completed = load(client, project_id)
    assert completed["nodes"][2]["status"] == "COMPLETED"
    assert completed["current_node_id"] == "CONTEXT_TESTABILITY"
    assert completed["nodes"][3]["status"] == "NOT_STARTED"
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
    assert service._semantic._runtime.prompts
    assert "NON_TESTABLE_CONTEXT" not in service._semantic._runtime.prompts[-1]
    assert review.items[0].label in service._semantic._runtime.prompts[-1]
    for stage_name in ("rules", "zero", "hybrid"):
        assert calls[stage_name].count(source["source_id"]) == 1
        assert calls[stage_name].count(sibling["source_id"]) == 1
    assert calls["semantic"].count(source["source_id"]) == 2
    assert calls["semantic"].count(sibling["source_id"]) == 1
    assert runs.documents == {}


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


@pytest.mark.parametrize("status", ["QUEUED", "RUNNING"])
def test_orphaned_active_n3_is_interrupted_retryable_and_never_completed(n2_context, status):
    project_id, _, service, _ = prepare_n3(n2_context, "A neutral source statement.")
    queued = service.start(project_id, user())
    record = service._workflow.load(agent_project_id=project_id, owner_user_id=user().user_id)
    record.n3_executions[-1].status = Agent4N3ExecutionStatus(status)
    service._workflow.save(record)
    Agent4N3OrchestrationService._active_execution_ids.clear()

    recovered = service.get(project_id, user())
    assert queued.n3_execution.execution_id == recovered.n3_execution.execution_id
    assert recovered.n3_execution.status == "INTERRUPTED"
    assert recovered.n3_execution.retryable is True
    assert recovered.n3_execution.completed_at is None
    assert recovered.nodes[2].status == "FAILED"


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
            ).n3_executions[-1]
            assert current.status == "RUNNING"
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
        "COMPLETED", "COMPLETED", "COMPLETED", "NOT_STARTED", "LOCKED", "LOCKED",
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


def test_new_successful_n3_completion_invokes_n4_handoff_once_after_durable_completion(n2_context):
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

    assert len(calls) == 1
    assert calls[0][0] == project_id
    assert calls[0][1] == user().user_id
    assert service.start(project_id, user()).n3_execution_count == 1
    assert len(calls) == 1


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
    assert progress[sources[0]["source_id"]].error.code == "N3_SOURCE_FAILED"
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
