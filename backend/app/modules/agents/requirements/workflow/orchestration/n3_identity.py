from datetime import datetime

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.workflow.constants import (
    N3_NODE_VERSION, N3_ORCHESTRATION_CONTRACT_VERSION,
)
from app.modules.agents.requirements.workflow.contracts.n3 import (
    RequirementN3Execution, RequirementN3Status,
)


def n3_execution_key(*, agent_project_id, n2_execution_id, chunk_set_digest,
                     discovery_input_identity, candidate_detector_fingerprint,
                     classifier_configuration_fingerprint,
                     structuring_contract_version):
    return stable_json_sha256({
        "agent_project_id": agent_project_id,
        "contract_version": N3_ORCHESTRATION_CONTRACT_VERSION,
        "node_version": N3_NODE_VERSION,
        "n2_execution_id": n2_execution_id,
        "chunk_set_digest": chunk_set_digest,
        "discovery_input_identity": discovery_input_identity,
        "candidate_detector_fingerprint": candidate_detector_fingerprint,
        "classifier_configuration_fingerprint": classifier_configuration_fingerprint,
        "structuring_contract_version": structuring_contract_version,
    })


def build_n3_execution(*, key, input_value, detector_fingerprint,
                       classifier_fingerprint, structuring_version,
                       attempt_number, created_at: datetime):
    return RequirementN3Execution(
        node_version=N3_NODE_VERSION,
        execution_id=f"N3-{key[:16].upper()}-{attempt_number:03d}",
        attempt_id=f"ATT-{attempt_number:03d}",
        execution_key=key,
        attempt_number=attempt_number,
        status=RequirementN3Status.QUEUED,
        n2_execution_id=input_value.reference.n2_execution_id,
        chunk_set_digest=input_value.reference.chunk_set_digest,
        discovery_input_identity=input_value.input_identity,
        candidate_detector_fingerprint=detector_fingerprint,
        classifier_configuration_fingerprint=classifier_fingerprint,
        structuring_contract_version=structuring_version,
        created_at=created_at,
    )
