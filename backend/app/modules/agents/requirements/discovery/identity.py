"""Deterministic identity for validated discovery input (not an execution key)."""

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256


DISCOVERY_INPUT_CONTRACT_VERSION = "1"


def discovery_input_identity(
    *, agent_project_id: str, n2_execution_id: str, n2_attempt: int, chunk_set_digest: str
) -> str:
    return stable_json_sha256(
        {
            "agent_project_id": agent_project_id,
            "contract_version": DISCOVERY_INPUT_CONTRACT_VERSION,
            "n2_attempt": n2_attempt,
            "n2_execution_id": n2_execution_id,
            "chunk_set_digest": chunk_set_digest,
        }
    )
