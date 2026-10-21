from app.modules.agents.requirements.infrastructure.artifact_paths import RequirementArtifactKind
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore
from app.modules.agents.requirements.quality.clarity.service import RequirementClarityService
from app.modules.agents.requirements.quality.conflicts.service import RequirementConflictService
from app.modules.agents.requirements.quality.contracts import (
    ExactDuplicateResult, RequirementClarityResult, RequirementConflictResult,
    SemanticDuplicateResult, ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.exact_duplicates import ExactDuplicateDetector
from app.modules.agents.requirements.quality.findings.contracts import QualityConsolidationResult
from app.modules.agents.requirements.quality.findings.service import QualityFindingConsolidationService
from app.modules.agents.requirements.quality.n4_identity import n4_configuration_fingerprint
from app.modules.agents.requirements.quality.n4_service import RequirementN4OrchestrationService
from app.modules.agents.requirements.quality.semantic_duplicates.service import SemanticDuplicateService
from app.modules.agents.requirements.quality.storage import QualityStorage
from app.modules.agents.requirements.workflow.contracts.n4 import RequirementN4Status
from test_agent1_conflicts import FakeNliProvider
from test_agent1_n3_orchestration import ImmediateExecutor, InputLoader, context, current
from test_agent1_semantic_duplicates import FakeProvider
from test_agent1_exact_duplicates import quality_input, requirement


def build(tmp_path):
    # Complete the authoritative N3 stage first.
    n3, states, upstream, _, _, _ = context(tmp_path)
    n3.start("AGP-020", "USR-001")
    value = quality_input(requirement(1, "The system shall create accounts."))
    exact = ExactDuplicateDetector()
    semantic = SemanticDuplicateService(FakeProvider(((1.0, 0.0),)))
    conflicts = RequirementConflictService(FakeProvider(((1.0, 0.0),)), FakeNliProvider(()))
    clarity = RequirementClarityService()
    findings = QualityFindingConsolidationService()
    artifacts = QualityStorage(JsonArtifactStore(tmp_path))
    service = RequirementN4OrchestrationService(
        states, InputLoader(value), exact, semantic, conflicts, clarity, findings,
        artifacts, executor=ImmediateExecutor(),
        configuration_fingerprint=n4_configuration_fingerprint(
            exact=exact, semantic=semantic, conflicts=conflicts,
            clarity=clarity, findings=findings,
        ),
    )
    return service, states, artifacts, value


def test_complete_n3_runs_persisted_n4_pipeline_idempotently(tmp_path):
    service, states, artifacts, value = build(tmp_path)
    service.start("AGP-020", "USR-001")
    record = states.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    execution = record.n4_executions[-1]
    assert execution.status is RequirementN4Status.COMPLETE
    assert record.current_n4_execution_id == execution.execution_id
    assert execution.execution_id.startswith("N4-")
    assert execution.result_summary.quality_input_identity == value.input_identity
    assert len(execution.result_summary.artifact_digests) == 6
    replay = service.start("AGP-020", "USR-001")
    assert replay.execution_id == execution.execution_id
    assert len(states.load(agent_project_id="AGP-020", owner_user_id="USR-001").n4_executions) == 1


def test_all_s1_s6_artifacts_are_persisted_and_digest_backed(tmp_path):
    service, states, artifacts, _ = build(tmp_path)
    service.start("AGP-020", "USR-001")
    execution = states.load(agent_project_id="AGP-020", owner_user_id="USR-001").n4_executions[-1]
    models = (
        (RequirementArtifactKind.QUALITY_INPUT, ValidatedQualityInput),
        (RequirementArtifactKind.QUALITY_EXACT_DUPLICATES, ExactDuplicateResult),
        (RequirementArtifactKind.QUALITY_SEMANTIC_DUPLICATES, SemanticDuplicateResult),
        (RequirementArtifactKind.QUALITY_CONFLICTS, RequirementConflictResult),
        (RequirementArtifactKind.QUALITY_CLARITY, RequirementClarityResult),
        (RequirementArtifactKind.QUALITY_FINDINGS, QualityConsolidationResult),
    )
    for kind, model in models:
        assert artifacts.load("AGP-020", execution.execution_id, kind, model)


def test_failed_execution_requires_explicit_retry_and_preserves_history(tmp_path):
    service, states, _, _ = build(tmp_path)
    service._runner._exact = type("Broken", (), {"detect": lambda *_: (_ for _ in ()).throw(RuntimeError())})()
    first = service.start("AGP-020", "USR-001")
    record = states.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert record.n4_executions[-1].status is RequirementN4Status.FAILED
    assert service.start("AGP-020", "USR-001").execution_id == first.execution_id
    service._runner._exact = ExactDuplicateDetector()
    retry = service.retry("AGP-020", "USR-001")
    assert retry.attempt_number == 2
    record = states.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert len(record.n4_executions) == 2
    assert record.n4_executions[0].status is RequirementN4Status.FAILED
    assert record.n3_executions[-1].status.value == "COMPLETE"
