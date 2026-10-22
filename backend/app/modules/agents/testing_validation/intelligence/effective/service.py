import hashlib
import json
from datetime import datetime, timezone

from app.modules.agents.testing_validation.intelligence.hybrid.service import manifest_fingerprint
from app.modules.agents.testing_validation.intelligence.schemas import HybridLabelDecisionStatus
from app.modules.agents.testing_validation.intelligence.taxonomy import TestingIntelligenceLabel
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N3ReviewDecision,
    Agent4N3ReviewEvent,
)

from .schemas import (
    EFFECTIVE_CLASSIFICATION_POLICY_VERSION,
    EffectiveClassificationCounts,
    EffectiveDecisionOrigin,
    EffectiveDecisionStatus,
    EffectiveLabelDecision,
    TestingEffectiveClassificationManifest,
    TestingEffectiveClassificationResult,
)


class Agent4EffectiveClassificationError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


def effective_manifest_fingerprint(manifest):
    payload = manifest.model_dump(mode="json", exclude={"created_at"})
    for result in payload.get("results", []):
        result.pop("created_at", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Agent4EffectiveClassificationService:
    def __init__(self, storage, *, clock=utc_now):
        self._storage = storage
        self._clock = clock

    def get_current(self, agent_project_id, source_id, owner_user_id):
        return self._storage.load(
            agent_project_id=agent_project_id,
            owner_user_id=owner_user_id,
            source_id=source_id,
        )

    def build(self, hybrid, *, owner_user_id, review: Agent4N3ReviewEvent | None = None):
        fingerprint = manifest_fingerprint(hybrid)
        resolutions = {}
        if review:
            resolutions = {
                (item.source_id, item.chunk_id, item.label): item
                for item in review.resolutions
                if item.source_id == hybrid.source_id
            }
        results = []
        now = self._clock()
        for hybrid_result in hybrid.results:
            decisions = []
            for decision in hybrid_result.decisions:
                if decision.status is HybridLabelDecisionStatus.ACCEPTED:
                    status = EffectiveDecisionStatus.ACCEPTED
                    origin = EffectiveDecisionOrigin.H1_AUTO_ACCEPTED
                    review_id = None
                elif decision.status is HybridLabelDecisionStatus.REJECTED:
                    status = EffectiveDecisionStatus.REJECTED
                    origin = EffectiveDecisionOrigin.H1_AUTO_REJECTED
                    review_id = None
                else:
                    resolution = resolutions.get((hybrid.source_id, hybrid_result.chunk.chunk_id, decision.label.value))
                    if resolution is None:
                        raise Agent4EffectiveClassificationError("Classification review is unresolved")
                    accepted = resolution.decision is Agent4N3ReviewDecision.ACCEPT
                    status = EffectiveDecisionStatus.ACCEPTED if accepted else EffectiveDecisionStatus.REJECTED
                    origin = EffectiveDecisionOrigin.HUMAN_ACCEPTED if accepted else EffectiveDecisionOrigin.HUMAN_REJECTED
                    review_id = review.review_id
                decisions.append(EffectiveLabelDecision(
                    label=decision.label, status=status, origin=origin,
                    hybrid_status=decision.status, review_id=review_id,
                ))
            accepted_labels = [d.label for d in decisions if d.status is EffectiveDecisionStatus.ACCEPTED]
            testable = [label for label in accepted_labels if label is not TestingIntelligenceLabel.NON_TESTABLE_CONTEXT]
            if testable and TestingIntelligenceLabel.NON_TESTABLE_CONTEXT in accepted_labels:
                human_non_testable = next(
                    d for d in decisions if d.label is TestingIntelligenceLabel.NON_TESTABLE_CONTEXT
                )
                if human_non_testable.origin is EffectiveDecisionOrigin.HUMAN_ACCEPTED:
                    raise Agent4EffectiveClassificationError(
                        "NON_TESTABLE_CONTEXT cannot be accepted with testable concerns"
                    )
                accepted_labels.remove(TestingIntelligenceLabel.NON_TESTABLE_CONTEXT)
                decisions = [
                    d.model_copy(update={"status": EffectiveDecisionStatus.REJECTED})
                    if d.label is TestingIntelligenceLabel.NON_TESTABLE_CONTEXT else d
                    for d in decisions
                ]
            rejected_labels = [d.label for d in decisions if d.status is EffectiveDecisionStatus.REJECTED]
            identity = {
                "version": EFFECTIVE_CLASSIFICATION_POLICY_VERSION,
                "chunk_id": hybrid_result.chunk.chunk_id,
                "hybrid_result_id": hybrid_result.result_id,
                "decisions": [
                    {"label": d.label.value, "status": d.status.value, "origin": d.origin.value}
                    for d in decisions
                ],
            }
            effective_id = "A4EFF-" + hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:32]
            results.append(TestingEffectiveClassificationResult(
                effective_result_id=effective_id,
                chunk=hybrid_result.chunk,
                taxonomy_version=hybrid.taxonomy_version,
                hybrid_result_id=hybrid_result.result_id,
                hybrid_policy_version=hybrid.hybrid_policy_version,
                hybrid_manifest_fingerprint=fingerprint,
                accepted_labels=accepted_labels,
                rejected_labels=rejected_labels,
                decisions=decisions,
                review_id=review.review_id if review and any(d.review_id for d in decisions) else None,
                effective_policy_version=EFFECTIVE_CLASSIFICATION_POLICY_VERSION,
                created_at=now,
            ))
        counts = EffectiveClassificationCounts(
            chunk_count=len(results),
            accepted_label_count=sum(len(item.accepted_labels) for item in results),
            rejected_label_count=sum(len(item.rejected_labels) for item in results),
            human_accepted_count=sum(d.origin is EffectiveDecisionOrigin.HUMAN_ACCEPTED for r in results for d in r.decisions),
            human_rejected_count=sum(d.origin is EffectiveDecisionOrigin.HUMAN_REJECTED for r in results for d in r.decisions),
        )
        manifest = TestingEffectiveClassificationManifest(
            agent_project_id=hybrid.agent_project_id,
            source_id=hybrid.source_id,
            taxonomy_version=hybrid.taxonomy_version,
            effective_policy_version=EFFECTIVE_CLASSIFICATION_POLICY_VERSION,
            hybrid_policy_version=hybrid.hybrid_policy_version,
            hybrid_manifest_fingerprint=fingerprint,
            review_ids=sorted({r.review_id for r in results if r.review_id}),
            chunk_ids=hybrid.chunk_ids,
            results=results,
            counts=counts,
            created_at=now,
        )
        cached = self._storage.load(
            agent_project_id=hybrid.agent_project_id,
            owner_user_id=owner_user_id,
            source_id=hybrid.source_id,
        )
        if cached and effective_manifest_fingerprint(cached) == effective_manifest_fingerprint(manifest):
            return cached
        self._storage.save(manifest, owner_user_id=owner_user_id)
        return manifest
