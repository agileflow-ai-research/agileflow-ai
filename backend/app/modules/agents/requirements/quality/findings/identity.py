"""Stable S6 identities and configuration fingerprint."""

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256


FINDING_CONTRACT_VERSION = "1"
CLARIFICATION_CANDIDATE_CONTRACT_VERSION = "1"
CONSOLIDATION_POLICY_VERSION = "1"


def consolidation_fingerprint():
    return stable_json_sha256({
        "contract_version": FINDING_CONTRACT_VERSION,
        "consolidation_policy_version": CONSOLIDATION_POLICY_VERSION,
        "finding_type_taxonomy_version": "1",
        "clarification_intent_taxonomy_version": "1",
        "stage_ordering_policy": "EXACT_SEMANTIC_CONFLICT_CLARITY",
        "candidate_policy": "ONE_FINDING_ONE_CANDIDATE",
    })


def finding_identity(*, quality_input_identity, finding_type, evidence_kind,
                     evidence_id, requirement_ids, detector_fingerprint):
    return stable_json_sha256({
        "contract_version": FINDING_CONTRACT_VERSION,
        "quality_input_identity": quality_input_identity,
        "finding_type": finding_type,
        "upstream_evidence_kind": evidence_kind,
        "upstream_evidence_id": evidence_id,
        "ordered_affected_requirement_ids": list(requirement_ids),
        "detector_fingerprint": detector_fingerprint,
    })


def candidate_identity(*, quality_input_identity, finding_id, intent):
    return stable_json_sha256({
        "contract_version": CLARIFICATION_CANDIDATE_CONTRACT_VERSION,
        "quality_input_identity": quality_input_identity,
        "finding_id": finding_id,
        "clarification_intent": intent,
    })
