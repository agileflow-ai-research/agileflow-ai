"""Adapt deterministic clarity signals into traceable N4 evidence."""

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.clarity.catalog import (
    AMBIGUITY_TAXONOMY_VERSION, CLARITY_RULE_CATALOG_VERSION,
    MISSING_INFORMATION_TAXONOMY_VERSION,
)
from app.modules.agents.requirements.quality.clarity.detector import RequirementClarityDetector
from app.modules.agents.requirements.quality.contracts import (
    RequirementClarityIssue, RequirementClarityIssueType,
    RequirementClarityResult, ValidatedQualityInput,
)


CLARITY_CONTRACT_VERSION = "1"
CLARITY_DETECTOR_VERSION = "1"


class RequirementClarityService:
    def __init__(self, detector=None):
        self._detector = detector or RequirementClarityDetector()

    @property
    def configuration_fingerprint(self):
        return stable_json_sha256({
            "detector_version": CLARITY_DETECTOR_VERSION,
            "rule_catalog_version": CLARITY_RULE_CATALOG_VERSION,
            "ambiguity_taxonomy_version": AMBIGUITY_TAXONOMY_VERSION,
            "missing_information_taxonomy_version": MISSING_INFORMATION_TAXONOMY_VERSION,
            "phrase_matching_policy": "EXPLICIT_CASE_INSENSITIVE_PHRASE_BOUNDARIES",
            "token_matching_policy": "UNICODE_WORD_AND_HYPHEN_BOUNDARIES",
            "numeric_evidence_policy": "BASIC_DURATION_QUANTITY_PERCENTAGE",
            "frequency_evidence_policy": "EVERY_INTERVAL_OR_DAILY_WEEKLY_MONTHLY",
            "case_handling_policy": "IGNORE_CASE_PRESERVE_ORIGINAL_EVIDENCE",
        })

    def analyze(self, value: ValidatedQualityInput) -> RequirementClarityResult:
        issues = []
        fingerprint = self.configuration_fingerprint
        for requirement in value.requirements:
            for signal in self._detector.detect(requirement.statement):
                identity = stable_json_sha256({
                    "contract_version": CLARITY_CONTRACT_VERSION,
                    "quality_input_identity": value.input_identity,
                    "requirement_id": requirement.requirement_id,
                    "issue_type": signal.issue_type.value,
                    "signal_code": signal.signal.value,
                    "evidence_offsets": [signal.start, signal.end],
                    "detector_fingerprint": fingerprint,
                })
                prefix = "QAMB" if signal.issue_type is RequirementClarityIssueType.AMBIGUITY else "QMISS"
                issues.append(RequirementClarityIssue(
                    issue_id=f"{prefix}-{identity[:16].upper()}",
                    issue_type=signal.issue_type, signal_code=signal.signal,
                    requirement=requirement,
                    evidence_text=requirement.statement[signal.start:signal.end],
                    evidence_start=signal.start, evidence_end=signal.end,
                    detector_fingerprint=fingerprint,
                    rule_version=signal.rule_version,
                    explanation=signal.explanation,
                ))
        result_identity = stable_json_sha256({
            "quality_input_identity": value.input_identity,
            "detector_fingerprint": fingerprint,
            "ordered_issue_ids": [item.issue_id for item in issues],
        })
        ambiguity_count = sum(item.issue_type is RequirementClarityIssueType.AMBIGUITY for item in issues)
        return RequirementClarityResult(
            contract_version=CLARITY_CONTRACT_VERSION,
            agent_project_id=value.agent_project_id,
            quality_input_identity=value.input_identity,
            detector_fingerprint=fingerprint,
            issues=tuple(issues), ambiguity_count=ambiguity_count,
            missing_information_count=len(issues) - ambiguity_count,
            affected_requirement_count=len({item.requirement.requirement_id for item in issues}),
            result_identity=result_identity,
        )
