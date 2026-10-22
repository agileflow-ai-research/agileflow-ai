"""Deterministic identity for an authoritative validated quality input."""

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256


QUALITY_INPUT_CONTRACT_VERSION = "1"


def quality_input_identity(
    *, agent_project_id: str, n3_execution_id: str, n3_attempt: int,
    discovery_input_identity: str, chunk_set_digest: str,
    candidate_artifact_digest: str, classification_artifact_digest: str,
    structured_artifact_digest: str, structured_set_identity: str,
    classifier_configuration_fingerprint: str,
    ordered_requirement_ids: tuple[str, ...],
) -> str:
    return stable_json_sha256({
        "agent_project_id": agent_project_id,
        "contract_version": QUALITY_INPUT_CONTRACT_VERSION,
        "n3_execution_id": n3_execution_id,
        "n3_attempt": n3_attempt,
        "discovery_input_identity": discovery_input_identity,
        "chunk_set_digest": chunk_set_digest,
        "candidate_artifact_digest": candidate_artifact_digest,
        "classification_artifact_digest": classification_artifact_digest,
        "structured_artifact_digest": structured_artifact_digest,
        "structured_set_identity": structured_set_identity,
        "classifier_configuration_fingerprint": classifier_configuration_fingerprint,
        "ordered_requirement_ids": list(ordered_requirement_ids),
    })
