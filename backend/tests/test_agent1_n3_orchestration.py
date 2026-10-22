from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.candidate_detection import RequirementCandidateDetector
from app.modules.agents.requirements.discovery.classification.protocol import (
    ClassifierConfiguration, ProviderClassification, RequirementClassifierError,
)
from app.modules.agents.requirements.discovery.classification.service import RequirementClassificationService
from app.modules.agents.requirements.discovery.classification.transformer import HYPOTHESIS_TEMPLATE, LABEL_DESCRIPTIONS
from app.modules.agents.requirements.discovery.contracts import (
    ClassificationScore, DiscoveryInputReference, RequirementClassificationLabel,
    ValidatedDiscoveryChunk, ValidatedDiscoveryInput,
)
from app.modules.agents.requirements.discovery.storage import DiscoveryStorage
from app.modules.agents.requirements.discovery.storage import DiscoveryStorageError
from app.modules.agents.requirements.infrastructure.artifact_paths import RequirementArtifactKind, RequirementArtifactPaths
from app.modules.agents.requirements.discovery.structuring import RequirementStructuringService
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore
from app.modules.agents.requirements.processing.preparation.schemas import EvidenceChunk, NormalizedProvenanceSpan
from app.modules.agents.requirements.workflow.contracts.n1 import RequirementN1Confirmation, RequirementOutputCode
from app.modules.agents.requirements.workflow.contracts.n2 import RequirementN2Status
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Status
from app.modules.agents.requirements.workflow.contracts.record import RequirementWorkflowRecord
from app.modules.agents.requirements.workflow.orchestration.n3_service import RequirementN3OrchestrationService
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


class InputLoader:
    def __init__(self, value): self.value = value
    def load(self, **_kwargs): return self.value


class FakeProvider:
    def __init__(self, label=RequirementClassificationLabel.FUNCTIONAL):
        self.label = label; self.fail = False
        self.configuration = ClassifierConfiguration(
            provider_type="FAKE", provider_version="1", model_id="fake/model",
            requested_revision="r1", resolved_revision="r1", task="zero-shot-classification",
            label_descriptions=dict(LABEL_DESCRIPTIONS), hypothesis_template=HYPOTHESIS_TEMPLATE,
            device="cpu", batch_size=4, local_files_only=True,
        )
    def classify(self, candidates):
        if self.fail: raise RequirementClassifierError("hidden")
        output = []
        for item in candidates:
            scores = tuple(ClassificationScore(label=label, score=0.8 if label is self.label else 0.1) for label in RequirementClassificationLabel)
            output.append(ProviderClassification(candidate_id=item.candidate_id, winner=self.label, scores=scores))
        return tuple(output)


class ImmediateExecutor:
    def submit(self, function, *args): function(*args); return SimpleNamespace()


class DeferredExecutor:
    def __init__(self): self.job = None
    def submit(self, function, *args): self.job = (function, args); return SimpleNamespace()
    def run(self): self.job[0](*self.job[1])


def discovery_input(text="The system must create accounts.", *, digest="d" * 64):
    chunks = ()
    if text:
        provenance = NormalizedProvenanceSpan(normalized_start_offset=0, normalized_end_offset=len(text), page_numbers=[1])
        chunk = EvidenceChunk(chunk_id="CHK-0123456789ABCDEF", content=text, normalized_start_offset=0, normalized_end_offset=len(text), provenance=[provenance])
        chunks = (ValidatedDiscoveryChunk(
            source_id="DOC-001", source_type=RequirementSourceType.DOCUMENT,
            source_sha256="a" * 64, parent_result_fingerprint="b" * 64,
            normalizer_version="1", chunker_fingerprint="c" * 64, chunk=chunk,
        ),)
    # S1 requires at least one chunk; use filler for the zero-candidate case.
    if not chunks:
        return discovery_input("Hello, thanks for meeting with us.", digest=digest)
    return ValidatedDiscoveryInput(
        contract_version="1", agent_project_id="AGP-020",
        reference=DiscoveryInputReference(
            n2_execution_id="N2-AAAAAAAAAAAAAAAA-001", n2_attempt=1,
            chunk_set_digest=digest, confirmed_source_set_digest="e" * 64,
        ), chunks=chunks, input_identity=("f" * 64 if digest == "d" * 64 else "1" * 64),
    )


def workflow_record():
    return RequirementWorkflowRecord(
        schema_version="3", workflow_version="W3", agent_project_id="AGP-020",
        owner_user_id="USR-001", selected_outputs=[RequirementOutputCode.SRS],
        selection_revision=1, selection_digest="a" * 64, source_set_digest="e" * 64,
        n1_confirmation=RequirementN1Confirmation(source_set_digest="e" * 64, selection_digest="a" * 64, confirmed_at=NOW),
        n2_executions=[], current_n2_execution_id=None, created_at=NOW, updated_at=NOW,
    )


def context(tmp_path, *, text="The system must create accounts.", label=RequirementClassificationLabel.FUNCTIONAL, executor=None):
    states = RequirementWorkflowStorage(tmp_path); states.save(workflow_record())
    loader = InputLoader(discovery_input(text)); provider = FakeProvider(label)
    classifier = RequirementClassificationService(provider, minimum_margin=None)
    storage = DiscoveryStorage(JsonArtifactStore(tmp_path)); executor = executor or ImmediateExecutor()
    service = RequirementN3OrchestrationService(
        states, loader, RequirementCandidateDetector(), classifier,
        RequirementStructuringService(), storage, executor=executor, clock=lambda: NOW,
    )
    return service, states, loader, provider, storage, executor


def current(states):
    record = states.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    return record, record.n3_executions[-1]


def test_full_pipeline_persists_all_artifacts_summary_and_replays_idempotently(tmp_path):
    service, states, _, _, storage, _ = context(tmp_path)
    service.start("AGP-020", "USR-001")
    record, execution = current(states)
    assert execution.status is RequirementN3Status.COMPLETE
    assert execution.result_summary.candidate_count == 1
    assert execution.result_summary.functional_requirement_count == 1
    assert storage.load_candidates("AGP-020", execution.execution_id).candidates
    assert storage.load_classifications("AGP-020", execution.execution_id).classifications
    assert storage.load_structured_requirements("AGP-020", execution.execution_id).functional_requirements
    assert len({execution.result_summary.candidate_artifact_digest, execution.result_summary.classification_artifact_digest, execution.result_summary.structured_artifact_digest}) == 3
    replay = service.start("AGP-020", "USR-001")
    assert replay.execution_id == execution.execution_id
    assert len(current(states)[0].n3_executions) == 1


def test_zero_candidates_and_all_other_complete(tmp_path):
    zero, zero_states, *_ = context(tmp_path / "zero", text="Hello, thanks for meeting with us.")
    zero.start("AGP-020", "USR-001")
    assert current(zero_states)[1].result_summary.candidate_count == 0
    other, other_states, *_ = context(tmp_path / "other", label=RequirementClassificationLabel.OTHER)
    other.start("AGP-020", "USR-001")
    summary = current(other_states)[1].result_summary
    assert summary.excluded_candidate_count == 1
    assert summary.functional_requirement_count == summary.non_functional_requirement_count == 0


def test_failed_classification_is_historical_and_explicit_retry_creates_attempt(tmp_path):
    service, states, _, provider, _, _ = context(tmp_path)
    provider.fail = True; service.start("AGP-020", "USR-001")
    assert current(states)[1].status is RequirementN3Status.FAILED
    provider.fail = False; retry = service.retry("AGP-020", "USR-001")
    record, completed = current(states)
    assert retry.attempt_number == 2
    assert completed.status is RequirementN3Status.COMPLETE
    assert len(record.n3_executions) == 2
    assert record.n3_executions[0].status is RequirementN3Status.FAILED


def test_stale_input_blocks_and_interrupted_execution_reconciles(tmp_path):
    deferred = DeferredExecutor()
    service, states, loader, _, _, _ = context(tmp_path / "stale", executor=deferred)
    service.start("AGP-020", "USR-001")
    loader.value = discovery_input(digest="9" * 64); deferred.run()
    assert current(states)[1].status is RequirementN3Status.BLOCKED
    deferred2 = DeferredExecutor()
    service2, states2, *_ = context(tmp_path / "interrupt", executor=deferred2)
    service2.start("AGP-020", "USR-001")
    service2._active_execution_ids.clear()
    service2.reconcile("AGP-020", "USR-001")
    execution = current(states2)[1]
    assert execution.status is RequirementN3Status.FAILED
    assert execution.error.code == "N3_EXECUTION_INTERRUPTED"


def test_execution_artifacts_are_isolated_immutable_and_fail_closed(tmp_path):
    service, states, _, _, storage, _ = context(tmp_path)
    service.start("AGP-020", "USR-001")
    execution = current(states)[1]
    candidates = storage.load_candidates("AGP-020", execution.execution_id)
    other_execution = "N3-BBBBBBBBBBBBBBBB-001"
    storage.save_candidates("AGP-020", other_execution, candidates)
    assert storage.load_candidates("AGP-020", other_execution) == candidates
    changed = candidates.model_copy(update={"contract_version": "changed"})
    try:
        storage.save_candidates("AGP-020", execution.execution_id, changed)
        assert False, "historical overwrite must fail"
    except DiscoveryStorageError:
        pass
    paths = RequirementArtifactPaths(tmp_path)
    malformed = paths.for_execution("AGP-020", "N3-CCCCCCCCCCCCCCCC-001", RequirementArtifactKind.DISCOVERY_CANDIDATES)
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_text("{malformed", encoding="utf-8")
    try:
        storage.load_candidates("AGP-020", "N3-CCCCCCCCCCCCCCCC-001")
        assert False, "malformed artifact must fail"
    except DiscoveryStorageError:
        pass
    try:
        storage.load_candidates("AGP-020", "../escape")
        assert False, "unsafe execution identity must fail"
    except DiscoveryStorageError:
        pass
