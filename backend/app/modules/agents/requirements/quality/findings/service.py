"""Pure deterministic consolidation of authoritative S2-S5 evidence."""

from enum import StrEnum

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.contracts import (
    ExactDuplicateResult, RequirementClarityIssueType, RequirementClarityResult,
    RequirementConflictResult, SemanticDuplicateResult, ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.findings.contracts import (
    ClarificationCandidate, ClarificationIntent, QualityConsolidationResult,
    QualityFindingEvidence, QualityFindingEvidenceKind, QualityFindingType,
    UnifiedQualityFinding,
)
from app.modules.agents.requirements.quality.findings.identity import (
    CLARIFICATION_CANDIDATE_CONTRACT_VERSION, FINDING_CONTRACT_VERSION,
    candidate_identity, consolidation_fingerprint, finding_identity,
)


class QualityConsolidationErrorCode(StrEnum):
    IDENTITY_MISMATCH = "QUALITY_CONSOLIDATION_IDENTITY_MISMATCH"
    TRACEABILITY_INVALID = "QUALITY_CONSOLIDATION_TRACEABILITY_INVALID"
    UPSTREAM_INCONSISTENT = "QUALITY_CONSOLIDATION_UPSTREAM_INCONSISTENT"


class QualityConsolidationError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


_FINDING_REASONS = {
    QualityFindingType.EXACT_DUPLICATE: "Multiple requirements contain the same requirement statement.",
    QualityFindingType.SEMANTIC_DUPLICATE: "Two requirements contain strong semantic similarity evidence.",
    QualityFindingType.CONFLICT: "Two requirements contain contradiction evidence.",
}
_CANDIDATE_POLICY = {
    QualityFindingType.EXACT_DUPLICATE: (
        ClarificationIntent.DUPLICATE_REVIEW,
        "Multiple requirements contain the same requirement statement and require human review to confirm whether the duplication is intentional.",
    ),
    QualityFindingType.SEMANTIC_DUPLICATE: (
        ClarificationIntent.SEMANTIC_DUPLICATE_REVIEW,
        "Two requirements have strong semantic similarity and require human review to confirm whether they express the same intent.",
    ),
    QualityFindingType.CONFLICT: (
        ClarificationIntent.CONFLICT_RESOLUTION,
        "Two requirements contain contradiction evidence and require human resolution.",
    ),
    QualityFindingType.AMBIGUITY: (
        ClarificationIntent.AMBIGUITY_CLARIFICATION,
        "The requirement contains language that may support more than one interpretation.",
    ),
    QualityFindingType.MISSING_INFORMATION: (
        ClarificationIntent.MISSING_INFORMATION_REQUEST,
        "The requirement appears to require additional measurable or contextual information.",
    ),
}


class QualityFindingConsolidationService:
    @property
    def configuration_fingerprint(self):
        return consolidation_fingerprint()

    def consolidate(self, value: ValidatedQualityInput,
                    exact: ExactDuplicateResult,
                    semantic: SemanticDuplicateResult,
                    conflicts: RequirementConflictResult,
                    clarity: RequirementClarityResult) -> QualityConsolidationResult:
        by_id = self._validate(value, exact, semantic, conflicts, clarity)
        findings = []
        for group in exact.duplicate_groups:
            requirements = tuple(member.requirement for member in group.members)
            findings.append(self._finding(
                value, QualityFindingType.EXACT_DUPLICATE,
                QualityFindingEvidenceKind.EXACT_DUPLICATE_GROUP,
                group.duplicate_group_id, requirements, exact.detector_fingerprint,
                QualityFindingEvidence(
                    kind=QualityFindingEvidenceKind.EXACT_DUPLICATE_GROUP,
                    upstream_evidence_id=group.duplicate_group_id,
                    exact_duplicate_group=group,
                ),
                _FINDING_REASONS[QualityFindingType.EXACT_DUPLICATE],
            ))
        for pair in semantic.pairs:
            findings.append(self._finding(
                value, QualityFindingType.SEMANTIC_DUPLICATE,
                QualityFindingEvidenceKind.SEMANTIC_DUPLICATE_PAIR,
                pair.semantic_duplicate_id, (pair.left, pair.right),
                semantic.detector_fingerprint,
                QualityFindingEvidence(
                    kind=QualityFindingEvidenceKind.SEMANTIC_DUPLICATE_PAIR,
                    upstream_evidence_id=pair.semantic_duplicate_id,
                    semantic_duplicate_pair=pair,
                ), _FINDING_REASONS[QualityFindingType.SEMANTIC_DUPLICATE],
            ))
        for pair in conflicts.conflicts:
            findings.append(self._finding(
                value, QualityFindingType.CONFLICT,
                QualityFindingEvidenceKind.REQUIREMENT_CONFLICT_PAIR,
                pair.conflict_id, (pair.left, pair.right),
                conflicts.detector_fingerprint,
                QualityFindingEvidence(
                    kind=QualityFindingEvidenceKind.REQUIREMENT_CONFLICT_PAIR,
                    upstream_evidence_id=pair.conflict_id, conflict_pair=pair,
                ), _FINDING_REASONS[QualityFindingType.CONFLICT],
            ))
        for issue in clarity.issues:
            finding_type = (QualityFindingType.AMBIGUITY
                            if issue.issue_type is RequirementClarityIssueType.AMBIGUITY
                            else QualityFindingType.MISSING_INFORMATION)
            findings.append(self._finding(
                value, finding_type,
                QualityFindingEvidenceKind.REQUIREMENT_CLARITY_ISSUE,
                issue.issue_id, (issue.requirement,), clarity.detector_fingerprint,
                QualityFindingEvidence(
                    kind=QualityFindingEvidenceKind.REQUIREMENT_CLARITY_ISSUE,
                    upstream_evidence_id=issue.issue_id, clarity_issue=issue,
                ), issue.explanation,
            ))
        candidates = tuple(self._candidate(value, finding) for finding in findings)
        counts = {kind: sum(item.finding_type is kind for item in findings)
                  for kind in QualityFindingType}
        result_identity = stable_json_sha256({
            "quality_input_identity": value.input_identity,
            "exact_duplicate_result_identity": exact.result_identity,
            "semantic_duplicate_result_identity": semantic.result_identity,
            "conflict_result_identity": conflicts.result_identity,
            "clarity_result_identity": clarity.result_identity,
            "consolidation_fingerprint": self.configuration_fingerprint,
            "ordered_finding_ids": [item.finding_id for item in findings],
            "ordered_clarification_candidate_ids": [item.clarification_candidate_id for item in candidates],
        })
        affected = {requirement.requirement_id for finding in findings
                    for requirement in finding.affected_requirements}
        return QualityConsolidationResult(
            contract_version=FINDING_CONTRACT_VERSION,
            agent_project_id=value.agent_project_id,
            quality_input_identity=value.input_identity,
            exact_duplicate_result_identity=exact.result_identity,
            semantic_duplicate_result_identity=semantic.result_identity,
            conflict_result_identity=conflicts.result_identity,
            clarity_result_identity=clarity.result_identity,
            consolidation_fingerprint=self.configuration_fingerprint,
            findings=tuple(findings), clarification_candidates=candidates,
            exact_duplicate_findings=counts[QualityFindingType.EXACT_DUPLICATE],
            semantic_duplicate_findings=counts[QualityFindingType.SEMANTIC_DUPLICATE],
            conflict_findings=counts[QualityFindingType.CONFLICT],
            ambiguity_findings=counts[QualityFindingType.AMBIGUITY],
            missing_information_findings=counts[QualityFindingType.MISSING_INFORMATION],
            total_findings=len(findings), clarification_candidate_count=len(candidates),
            affected_requirement_count=len(affected), result_identity=result_identity,
        )

    def _validate(self, value, exact, semantic, conflicts, clarity):
        upstream = (exact, semantic, conflicts, clarity)
        if any(item.agent_project_id != value.agent_project_id
               or item.quality_input_identity != value.input_identity for item in upstream):
            self._reject(QualityConsolidationErrorCode.IDENTITY_MISMATCH,
                         "Quality evidence belongs to another input")
        if (semantic.exact_duplicate_result_identity != exact.result_identity
                or conflicts.exact_duplicate_result_identity != exact.result_identity
                or conflicts.semantic_duplicate_result_identity != semantic.result_identity):
            self._reject(QualityConsolidationErrorCode.IDENTITY_MISMATCH,
                         "Quality evidence relationships are incompatible")
        by_id = {item.requirement_id: item for item in value.requirements}
        if len(by_id) != len(value.requirements):
            self._reject(QualityConsolidationErrorCode.TRACEABILITY_INVALID,
                         "Quality input contains duplicate requirement identities")
        exact_pairs = set()
        evidence_ids = []
        for group in exact.duplicate_groups:
            evidence_ids.append(group.duplicate_group_id)
            self._requirements_match(by_id, tuple(item.requirement for item in group.members))
            for left in range(len(group.members)):
                for right in range(left + 1, len(group.members)):
                    exact_pairs.add(frozenset((group.members[left].requirement.requirement_id,
                                               group.members[right].requirement.requirement_id)))
        for pair in semantic.pairs:
            evidence_ids.append(pair.semantic_duplicate_id)
            self._requirements_match(by_id, (pair.left, pair.right))
            if frozenset((pair.left.requirement_id, pair.right.requirement_id)) in exact_pairs:
                self._reject(QualityConsolidationErrorCode.UPSTREAM_INCONSISTENT,
                             "Semantic evidence duplicates exact evidence")
        for pair in conflicts.conflicts:
            evidence_ids.append(pair.conflict_id)
            self._requirements_match(by_id, (pair.left, pair.right))
            if frozenset((pair.left.requirement_id, pair.right.requirement_id)) in exact_pairs:
                self._reject(QualityConsolidationErrorCode.UPSTREAM_INCONSISTENT,
                             "Conflict evidence duplicates exact evidence")
        for issue in clarity.issues:
            evidence_ids.append(issue.issue_id)
            self._requirements_match(by_id, (issue.requirement,))
        if len(evidence_ids) != len(set(evidence_ids)):
            self._reject(QualityConsolidationErrorCode.UPSTREAM_INCONSISTENT,
                         "Upstream evidence identities are duplicated")
        return by_id

    def _requirements_match(self, by_id, requirements):
        for requirement in requirements:
            if by_id.get(requirement.requirement_id) != requirement:
                self._reject(QualityConsolidationErrorCode.TRACEABILITY_INVALID,
                             "Upstream requirement traceability is inconsistent")

    def _finding(self, value, finding_type, kind, evidence_id, requirements,
                 detector_fingerprint, evidence, reason):
        identity = finding_identity(
            quality_input_identity=value.input_identity,
            finding_type=finding_type.value, evidence_kind=kind.value,
            evidence_id=evidence_id,
            requirement_ids=tuple(item.requirement_id for item in requirements),
            detector_fingerprint=detector_fingerprint,
        )
        return UnifiedQualityFinding(
            finding_id=f"QF-{identity[:16].upper()}",
            contract_version=FINDING_CONTRACT_VERSION,
            finding_type=finding_type, agent_project_id=value.agent_project_id,
            quality_input_identity=value.input_identity,
            affected_requirements=requirements, evidence=evidence,
            detector_fingerprint=detector_fingerprint,
            reason=reason, requires_human_review=True,
        )

    @staticmethod
    def _candidate(value, finding):
        intent, reason = _CANDIDATE_POLICY[finding.finding_type]
        identity = candidate_identity(
            quality_input_identity=value.input_identity,
            finding_id=finding.finding_id, intent=intent.value,
        )
        return ClarificationCandidate(
            clarification_candidate_id=f"QCL-{identity[:16].upper()}",
            contract_version=CLARIFICATION_CANDIDATE_CONTRACT_VERSION,
            finding_id=finding.finding_id, finding_type=finding.finding_type,
            quality_input_identity=value.input_identity,
            affected_requirements=finding.affected_requirements,
            intent=intent, reason=reason,
            upstream_evidence_kind=finding.evidence.kind,
            upstream_evidence_id=finding.evidence.upstream_evidence_id,
            requires_human_input=True,
        )

    @staticmethod
    def _reject(code, message):
        raise QualityConsolidationError(code, message)
