"""Pure H1 rule/model decision engine; no I/O or inference."""

import hashlib
import json
from datetime import datetime

from app.modules.agents.testing_validation.intelligence.rules.catalog import (
    AGENT4_RULES_VERSION,
)
from app.modules.agents.testing_validation.intelligence.schemas import (
    HybridEvidenceState,
    HybridLabelDecision,
    HybridLabelDecisionStatus,
    TestingHybridClassificationResult,
    TestingRuleClassificationResult,
    TestingZeroShotClassificationResult,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TestingIntelligenceLabel,
)
from app.modules.agents.testing_validation.intelligence.zero_shot import constants as zc

from .policy import H1_POLICY, HybridPolicy, hybrid_policy_fingerprint


def _identity(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "A4HYB-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _validate_pair(rule, model):
    if rule.chunk != model.chunk:
        raise ValueError("rule and zero-shot results do not reference identical evidence")
    if rule.taxonomy_version != AGENT4_TESTING_TAXONOMY_VERSION:
        raise ValueError("rule result taxonomy is stale")
    if model.taxonomy_version != AGENT4_TESTING_TAXONOMY_VERSION:
        raise ValueError("zero-shot result taxonomy is stale")
    if rule.rules_version != AGENT4_RULES_VERSION:
        raise ValueError("rule result version is stale")
    if (
        model.model_id != zc.MODEL_ID
        or model.model_revision != zc.MODEL_REVISION
        or model.label_description_version != "ZL1"
        or model.hypothesis_template_version != zc.HYPOTHESIS_TEMPLATE_VERSION
    ):
        raise ValueError("zero-shot result configuration is stale")


def _decision(label, *, rule_ids, score, policy):
    detected = bool(rule_ids)
    if detected and score >= policy.rule_model_support_threshold:
        return HybridLabelDecision(
            label=label, status=HybridLabelDecisionStatus.ACCEPTED,
            evidence_state=HybridEvidenceState.AGREEMENT,
            reason_codes=["RULE_AND_MODEL_AGREE"],
            explanation="Deterministic rule evidence is supported at or above the H1 support threshold.",
            rule_evidence_ids=rule_ids, model_score=score, rule_detected=True,
            threshold_applied=policy.rule_model_support_threshold,
        )
    if detected and score >= policy.rule_model_conflict_threshold:
        return HybridLabelDecision(
            label=label, status=HybridLabelDecisionStatus.REVIEW_REQUIRED,
            evidence_state=HybridEvidenceState.RULE_ONLY,
            reason_codes=["RULE_WITH_MODERATE_MODEL_SUPPORT"],
            explanation="Deterministic rule evidence exists, but model support is below automatic agreement.",
            rule_evidence_ids=rule_ids, model_score=score, rule_detected=True,
            threshold_applied=policy.rule_model_support_threshold,
        )
    if detected:
        return HybridLabelDecision(
            label=label, status=HybridLabelDecisionStatus.REVIEW_REQUIRED,
            evidence_state=HybridEvidenceState.CONFLICT,
            reason_codes=["RULE_MODEL_CONFLICT"],
            explanation="Deterministic rule evidence exists, but the model score is below the H1 conflict threshold.",
            rule_evidence_ids=rule_ids, model_score=score, rule_detected=True,
            threshold_applied=policy.rule_model_conflict_threshold,
        )
    if score >= policy.model_only_review_threshold:
        return HybridLabelDecision(
            label=label, status=HybridLabelDecisionStatus.REVIEW_REQUIRED,
            evidence_state=HybridEvidenceState.MODEL_ONLY,
            reason_codes=["MODEL_ONLY_REVIEW"],
            explanation="Model-only support meets the H1 review threshold and requires human review.",
            model_score=score, threshold_applied=policy.model_only_review_threshold,
        )
    return HybridLabelDecision(
        label=label, status=HybridLabelDecisionStatus.REJECTED,
        evidence_state=HybridEvidenceState.AMBIGUOUS,
        reason_codes=["INSUFFICIENT_SUPPORT"],
        explanation="No rule evidence exists and model support is below the H1 review threshold.",
        model_score=score, threshold_applied=policy.model_only_review_threshold,
    )


def decide_hybrid_for_chunk(
    rule_result: TestingRuleClassificationResult,
    zero_shot_result: TestingZeroShotClassificationResult,
    *,
    processed_at: datetime,
    policy: HybridPolicy = H1_POLICY,
) -> TestingHybridClassificationResult:
    _validate_pair(rule_result, zero_shot_result)
    evidence_by_label = {label: [] for label in TESTING_INTELLIGENCE_LABEL_ORDER}
    for evidence in sorted(rule_result.rule_evidence, key=lambda item: item.evidence_id):
        evidence_by_label[evidence.label].append(evidence.evidence_id)

    non_testable = TestingIntelligenceLabel.NON_TESTABLE_CONTEXT
    decisions = [
        _decision(
            label,
            rule_ids=evidence_by_label[label],
            score=zero_shot_result.label_scores[label],
            policy=policy,
        )
        for label in TESTING_INTELLIGENCE_LABEL_ORDER
        if label is not non_testable
    ]
    has_testable_candidate = any(
        item.status in {
            HybridLabelDecisionStatus.ACCEPTED,
            HybridLabelDecisionStatus.REVIEW_REQUIRED,
        }
        for item in decisions
    )
    score = zero_shot_result.label_scores[non_testable]
    if has_testable_candidate:
        context = HybridLabelDecision(
            label=non_testable, status=HybridLabelDecisionStatus.REJECTED,
            evidence_state=HybridEvidenceState.AMBIGUOUS,
            reason_codes=["NON_TESTABLE_SUPPRESSED_BY_TESTABLE_EVIDENCE"],
            explanation="Testable accepted or reviewable concerns suppress non-testable context.",
            model_score=score, threshold_applied=policy.model_only_review_threshold,
        )
    elif score >= policy.model_only_review_threshold:
        context = HybridLabelDecision(
            label=non_testable, status=HybridLabelDecisionStatus.REVIEW_REQUIRED,
            evidence_state=HybridEvidenceState.MODEL_ONLY,
            reason_codes=["NON_TESTABLE_MODEL_ONLY_REVIEW"],
            explanation="Non-testable context has model-only support and requires human review.",
            model_score=score, threshold_applied=policy.model_only_review_threshold,
        )
    else:
        context = HybridLabelDecision(
            label=non_testable, status=HybridLabelDecisionStatus.REJECTED,
            evidence_state=HybridEvidenceState.AMBIGUOUS,
            reason_codes=["NON_TESTABLE_INSUFFICIENT_SUPPORT"],
            explanation="Non-testable context is below the H1 model-only review threshold.",
            model_score=score, threshold_applied=policy.model_only_review_threshold,
        )
    decisions.append(context)
    accepted = [d.label for d in decisions if d.status is HybridLabelDecisionStatus.ACCEPTED]
    review = [d.label for d in decisions if d.status is HybridLabelDecisionStatus.REVIEW_REQUIRED]
    rejected = [d.label for d in decisions if d.status is HybridLabelDecisionStatus.REJECTED]
    policy_fingerprint = hybrid_policy_fingerprint(policy)
    return TestingHybridClassificationResult(
        result_id=_identity({
            "chunk_id": rule_result.chunk.chunk_id,
            "rule_result_id": rule_result.result_id,
            "zero_shot_result_id": zero_shot_result.result_id,
            "taxonomy_version": AGENT4_TESTING_TAXONOMY_VERSION,
            "policy_fingerprint": policy_fingerprint,
        }),
        chunk=rule_result.chunk,
        taxonomy_version=AGENT4_TESTING_TAXONOMY_VERSION,
        rule_result_id=rule_result.result_id,
        zero_shot_result_id=zero_shot_result.result_id,
        hybrid_policy_version=policy.version,
        accepted_labels=accepted,
        review_required_labels=review,
        rejected_labels=rejected,
        decisions=decisions,
        processed_at=processed_at,
    )
