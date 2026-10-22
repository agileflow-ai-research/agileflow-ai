from app.modules.agents.testing_validation.intelligence.schemas import (
    TestingHybridClassificationResult,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TestingIntelligenceLabel,
)

from .schemas import SemanticClassificationContext, SemanticEligibility


def effective_semantic_classification_context(effective, context_fingerprint):
    accepted = [
        label for label in effective.accepted_labels
        if label is not TestingIntelligenceLabel.NON_TESTABLE_CONTEXT
    ]
    return SemanticClassificationContext(
        chunk_id=effective.chunk.chunk_id,
        hybrid_result_id=effective.hybrid_result_id,
        effective_result_id=effective.effective_result_id,
        context_fingerprint=context_fingerprint,
        accepted_labels=accepted,
        review_required_labels=[],
        eligibility=(SemanticEligibility.ELIGIBLE if accepted else SemanticEligibility.NOT_APPLICABLE),
    )


def semantic_classification_context(hybrid: TestingHybridClassificationResult):
    accepted = [
        label for label in hybrid.accepted_labels
        if label is not TestingIntelligenceLabel.NON_TESTABLE_CONTEXT
    ]
    if hybrid.review_required_labels:
        eligibility = SemanticEligibility.WAITING_FOR_CLASSIFICATION_REVIEW
    elif accepted:
        eligibility = SemanticEligibility.ELIGIBLE
    else:
        eligibility = SemanticEligibility.NOT_APPLICABLE
    return SemanticClassificationContext(
        chunk_id=hybrid.chunk.chunk_id,
        hybrid_result_id=hybrid.result_id,
        accepted_labels=accepted,
        review_required_labels=hybrid.review_required_labels,
        eligibility=eligibility,
    )
