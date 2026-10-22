"""Authenticated, persisted-only N4 result hydration boundary."""

from pydantic import model_validator

from app.modules.agents.requirements.discovery.contracts import StrictDiscoveryContract
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.infrastructure.artifact_paths import RequirementArtifactKind
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.contracts import (
    ExactDuplicateResult, RequirementClarityResult, RequirementConflictResult,
    SemanticDuplicateResult, ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.findings.contracts import QualityConsolidationResult
from app.modules.agents.requirements.workflow.contracts.n4 import (
    RequirementN4Execution, RequirementN4Status,
)


class QualityResultError(ValueError):
    pass


class QualityExecutionArtifacts(StrictDiscoveryContract):
    execution: RequirementN4Execution
    quality_input: ValidatedQualityInput | None = None
    exact_duplicates: ExactDuplicateResult | None = None
    semantic_duplicates: SemanticDuplicateResult | None = None
    conflicts: RequirementConflictResult | None = None
    clarity: RequirementClarityResult | None = None
    consolidation: QualityConsolidationResult | None = None

    @model_validator(mode="after")
    def complete_has_artifacts(self):
        values = (self.quality_input, self.exact_duplicates, self.semantic_duplicates,
                  self.conflicts, self.clarity, self.consolidation)
        if self.execution.status is RequirementN4Status.COMPLETE and any(v is None for v in values):
            raise ValueError("Complete quality execution requires all persisted artifacts")
        if self.execution.status is not RequirementN4Status.COMPLETE and any(v is not None for v in values):
            raise ValueError("Non-complete quality execution cannot expose result artifacts")
        return self


class QualityResultService:
    _ARTIFACTS = (
        ("quality_input", RequirementArtifactKind.QUALITY_INPUT, ValidatedQualityInput),
        ("exact", RequirementArtifactKind.QUALITY_EXACT_DUPLICATES, ExactDuplicateResult),
        ("semantic", RequirementArtifactKind.QUALITY_SEMANTIC_DUPLICATES, SemanticDuplicateResult),
        ("conflicts", RequirementArtifactKind.QUALITY_CONFLICTS, RequirementConflictResult),
        ("clarity", RequirementArtifactKind.QUALITY_CLARITY, RequirementClarityResult),
        ("findings", RequirementArtifactKind.QUALITY_FINDINGS, QualityConsolidationResult),
    )

    def __init__(self, standalone, workflows, artifacts):
        self._standalone = standalone
        self._workflows = workflows
        self._artifacts = artifacts

    def get(self, agent_project_id, execution_id, current_user):
        project = require_requirements_project(self._standalone, agent_project_id, current_user)
        record = self._workflows.load(
            agent_project_id=project.agent_project_id, owner_user_id=current_user.user_id
        )
        execution = next((x for x in record.n4_executions if x.execution_id == execution_id), None) if record else None
        if execution is None:
            raise QualityResultError("N4 execution is unavailable")
        if execution.status is not RequirementN4Status.COMPLETE:
            return QualityExecutionArtifacts(execution=execution)
        summary = execution.result_summary
        if summary is None:
            raise QualityResultError("Complete N4 result summary is unavailable")
        loaded = {}
        for digest_key, kind, model in self._ARTIFACTS:
            value = self._artifacts.load(agent_project_id, execution_id, kind, model)
            expected = summary.artifact_digests.get(digest_key)
            if expected is None or stable_json_sha256(value.model_dump(mode="json")) != expected:
                raise QualityResultError("Persisted N4 artifact integrity validation failed")
            loaded[digest_key] = value
        identity = summary.quality_input_identity
        if (
            loaded["quality_input"].input_identity != identity
            or execution.quality_input_identity != identity
            or any(loaded[key].quality_input_identity != identity for key in ("exact", "semantic", "conflicts", "clarity", "findings"))
            or loaded["semantic"].exact_duplicate_result_identity != loaded["exact"].result_identity
            or loaded["conflicts"].exact_duplicate_result_identity != loaded["exact"].result_identity
            or loaded["conflicts"].semantic_duplicate_result_identity != loaded["semantic"].result_identity
            or loaded["findings"].exact_duplicate_result_identity != loaded["exact"].result_identity
            or loaded["findings"].semantic_duplicate_result_identity != loaded["semantic"].result_identity
            or loaded["findings"].conflict_result_identity != loaded["conflicts"].result_identity
            or loaded["findings"].clarity_result_identity != loaded["clarity"].result_identity
        ):
            raise QualityResultError("Persisted N4 artifact identity validation failed")
        return QualityExecutionArtifacts(
            execution=execution, quality_input=loaded["quality_input"],
            exact_duplicates=loaded["exact"], semantic_duplicates=loaded["semantic"],
            conflicts=loaded["conflicts"], clarity=loaded["clarity"],
            consolidation=loaded["findings"],
        )
