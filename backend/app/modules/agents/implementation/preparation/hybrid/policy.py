from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel, ChunkRuleDetection, RuleStrength,
)
from app.modules.agents.implementation.preparation.classification.zero_shot.schemas import (
    ChunkZeroShotDetection, ZeroShotScore,
)

from . import constants
from .schemas import (
    ChunkHybridDetection, HybridCandidate, HybridChunkDiagnostics,
    HybridDecisionState as Decision, HybridEvidenceState as Evidence,
    HybridModelEvidence, HybridReasonCode as Reason, HybridRuleEvidence,
)


_OTHER = ArtifactDetectionLabel.OTHER_CONTEXT
_STRENGTH_ORDER = {None: 0, RuleStrength.WEAK: 1,
                   RuleStrength.MODERATE: 2, RuleStrength.STRONG: 3}
_CLASS_ORDER = {
    (Evidence.RULE_AND_MODEL, Decision.AUTO_CANDIDATE): 0,
    (Evidence.RULE_AND_MODEL, Decision.REVIEW_REQUIRED): 1,
    (Evidence.RULE_ONLY, Decision.REVIEW_REQUIRED): 2,
    (Evidence.MODEL_ONLY, Decision.REVIEW_REQUIRED): 3,
    (Evidence.RULE_MODEL_DISAGREEMENT, Decision.REVIEW_REQUIRED): 4,
    (Evidence.INSUFFICIENT_EVIDENCE, Decision.REJECTED): 5,
    (Evidence.INSUFFICIENT_EVIDENCE, Decision.REVIEW_REQUIRED): 5,
}


def decide_chunk(rule: ChunkRuleDetection,
                 model: ChunkZeroShotDetection) -> ChunkHybridDetection:
    scores = {item.label: item.score for item in model.scores}
    software = sorted(
        (item for item in model.scores if item.label is not _OTHER),
        key=lambda item: (-item.score, item.label.value),
    )
    high = [item for item in software
            if item.score >= constants.MODEL_LABEL_EXPLOSION_THRESHOLD]
    explosion = len(high) >= constants.MODEL_LABEL_EXPLOSION_COUNT
    margin = round(software[0].score - software[1].score, 6) if len(software) > 1 else None
    ambiguous = bool(
        len(software) > 1
        and software[0].score >= constants.MODEL_MODERATE_SUPPORT
        and margin is not None and margin < constants.TOP_SCORE_MARGIN_THRESHOLD
    )
    diagnostics = HybridChunkDiagnostics(
        model_label_explosion=explosion,
        model_ambiguous=ambiguous,
        top_model_margin=margin,
        top_model_scores=software[:4],
    )
    rules = [item for item in rule.predictions if item.label is not _OTHER]
    candidates: list[HybridCandidate] = []
    rule_labels = {item.label for item in rules}

    for prediction in rules:
        same = scores.get(prediction.label)
        competing = software[0] if software else None
        disagreement = bool(
            prediction.strength is RuleStrength.STRONG
            and (same is None or same < constants.MODEL_WEAK_SUPPORT)
            and competing is not None
            and competing.label != prediction.label
            and competing.score >= constants.MODEL_STRONG_SUPPORT
        )
        reasons = []
        if disagreement:
            state, decision = Evidence.RULE_MODEL_DISAGREEMENT, Decision.REVIEW_REQUIRED
            reasons.append(Reason.RULE_MODEL_DISAGREEMENT)
        elif same is not None and same >= constants.MODEL_MODERATE_SUPPORT:
            state = Evidence.RULE_AND_MODEL
            reasons.append(Reason.RULE_MODEL_AGREEMENT)
            if prediction.strength is RuleStrength.STRONG:
                reasons.append(Reason.STRONG_RULE_SUPPORT)
            elif prediction.strength is RuleStrength.MODERATE:
                reasons.append(Reason.MODERATE_RULE_SUPPORT)
            decision = (
                Decision.AUTO_CANDIDATE
                if prediction.strength in {RuleStrength.STRONG, RuleStrength.MODERATE}
                and same >= constants.MODEL_STRONG_SUPPORT
                else Decision.REVIEW_REQUIRED
            )
            if prediction.strength is RuleStrength.WEAK:
                decision = Decision.REVIEW_REQUIRED
        elif prediction.strength in {RuleStrength.STRONG, RuleStrength.MODERATE}:
            state, decision = Evidence.RULE_ONLY, Decision.REVIEW_REQUIRED
            reasons.append(Reason.STRONG_RULE_SUPPORT if prediction.strength is RuleStrength.STRONG else Reason.MODERATE_RULE_SUPPORT)
        else:
            state, decision = Evidence.INSUFFICIENT_EVIDENCE, Decision.REJECTED
            reasons.append(Reason.WEAK_EVIDENCE)
        if explosion:
            reasons.append(Reason.MODEL_LABEL_EXPLOSION)
            if decision is Decision.AUTO_CANDIDATE:
                decision = Decision.REVIEW_REQUIRED
        if ambiguous:
            reasons.append(Reason.MODEL_AMBIGUOUS)
            if decision is Decision.AUTO_CANDIDATE:
                decision = Decision.REVIEW_REQUIRED
        candidates.append(_candidate(prediction.label, state, decision,
                                     prediction, same, reasons))

    model_only = [item for item in software
                  if item.label not in rule_labels
                  and item.score >= constants.MODEL_MODERATE_SUPPORT]
    if explosion:
        model_only = model_only[:1]
    for item in model_only:
        reasons = [Reason.MODEL_ONLY_REQUIRES_REVIEW]
        if item.score >= constants.MODEL_STRONG_SUPPORT:
            reasons.insert(0, Reason.STRONG_MODEL_ONLY_SUPPORT)
        if explosion:
            reasons.append(Reason.MODEL_LABEL_EXPLOSION)
        if ambiguous:
            reasons.append(Reason.MODEL_AMBIGUOUS)
        candidates.append(_candidate(
            item.label, Evidence.MODEL_ONLY, Decision.REVIEW_REQUIRED,
            None, item.score, reasons,
        ))

    if not candidates:
        candidates.append(_candidate(
            _OTHER, Evidence.INSUFFICIENT_EVIDENCE, Decision.REVIEW_REQUIRED,
            None, scores.get(_OTHER),
            [Reason.NO_ARTIFACT_EVIDENCE, Reason.OTHER_CONTEXT_FALLBACK],
        ))
    candidates.sort(key=_sort_key)
    return ChunkHybridDetection(chunk_id=rule.chunk_id, text_hash=rule.text_hash,
                                diagnostics=diagnostics, candidates=candidates)


def _candidate(label, state, decision, rule, score, reasons):
    return HybridCandidate(
        label=label, evidence_state=state, decision=decision,
        rule=HybridRuleEvidence(
            matched=rule is not None,
            score=rule.rule_score if rule else None,
            strength=rule.strength if rule else None,
            evidence=rule.evidence if rule else [],
        ),
        model=HybridModelEvidence(score=score),
        reason_codes=list(dict.fromkeys(reasons)),
    )


def _sort_key(candidate):
    return (
        _CLASS_ORDER.get((candidate.evidence_state, candidate.decision), 9),
        -_STRENGTH_ORDER[candidate.rule.strength],
        -(candidate.model.score if candidate.model.score is not None else -1),
        candidate.label.value,
    )
