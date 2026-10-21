from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.workflow.constants import N4_NODE_VERSION, N4_ORCHESTRATION_CONTRACT_VERSION
from app.modules.agents.requirements.workflow.contracts.n4 import RequirementN4Execution, RequirementN4Status


def n4_configuration_fingerprint(*, exact, semantic, conflicts, clarity, findings):
    return stable_json_sha256({
        "exact": exact.configuration_fingerprint,
        "semantic": semantic.configuration_fingerprint,
        "conflicts": conflicts.configuration_fingerprint,
        "clarity": clarity.configuration_fingerprint,
        "findings": findings.configuration_fingerprint,
    })


def n4_execution_key(*, agent_project_id, n3_execution_id, n3_attempt,
                     structured_digest, quality_input_identity, configuration_fingerprint):
    return stable_json_sha256({
        "agent_project_id": agent_project_id,
        "contract_version": N4_ORCHESTRATION_CONTRACT_VERSION,
        "node_version": N4_NODE_VERSION,
        "n3_execution_id": n3_execution_id, "n3_attempt": n3_attempt,
        "structured_artifact_digest": structured_digest,
        "quality_input_identity": quality_input_identity,
        "configuration_fingerprint": configuration_fingerprint,
    })


def build_n4_execution(*, key, n3, quality_input_identity, configuration_fingerprint,
                       attempt_number, created_at):
    return RequirementN4Execution(
        node_version=N4_NODE_VERSION,
        execution_id=f"N4-{key[:16].upper()}-{attempt_number:03d}",
        attempt_id=f"ATT-{attempt_number:03d}", execution_key=key,
        attempt_number=attempt_number, status=RequirementN4Status.QUEUED,
        authoritative_n3_execution_id=n3.execution_id, n3_attempt=n3.attempt_number,
        n3_structured_artifact_digest=n3.result_summary.structured_artifact_digest,
        quality_input_identity=quality_input_identity,
        configuration_fingerprint=configuration_fingerprint, created_at=created_at,
    )
