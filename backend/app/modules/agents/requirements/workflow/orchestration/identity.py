"""Pure deterministic identities and snapshots for N2 execution."""

from datetime import datetime

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.workflow.constants import (
    N2_CHUNK_SET_CONTRACT_VERSION,
    N2_NODE_ID,
    N2_NODE_VERSION,
    N2_ORCHESTRATION_CONTRACT_VERSION,
)
from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2Execution,
    RequirementN2SourceProgress,
    RequirementN2SourceSnapshot,
    RequirementN2Status,
)


def n2_execution_key(
    agent_project_id: str,
    confirmed_source_set_digest: str,
    confirmed_selection_digest: str,
) -> str:
    return stable_json_sha256(
        {
            "agent_project_id": agent_project_id,
            "contract_version": N2_ORCHESTRATION_CONTRACT_VERSION,
            "node_id": N2_NODE_ID,
            "node_version": N2_NODE_VERSION,
            "source_set_digest": confirmed_source_set_digest,
            "selection_digest": confirmed_selection_digest,
        }
    )


def n2_chunk_set_digest(
    confirmed_source_set_digest: str,
    source_chunks: list[dict[str, object]],
) -> str:
    return stable_json_sha256(
        {
            "contract_version": N2_CHUNK_SET_CONTRACT_VERSION,
            "node_version": N2_NODE_VERSION,
            "source_set_digest": confirmed_source_set_digest,
            "sources": sorted(source_chunks, key=lambda item: str(item["source_id"])),
        }
    )


def snapshot_sources(sources) -> list[RequirementN2SourceSnapshot]:
    return sorted(
        [
            RequirementN2SourceSnapshot(
                source_id=source.source_id,
                source_type=source.source_type.value,
                sha256=source.sha256,
            )
            for source in sources
        ],
        key=lambda source: source.source_id,
    )


def chunk_source_identity(source, chunks) -> dict[str, object]:
    return {
        "source_id": source.source_id,
        "source_sha256": source.sha256,
        "parent_result_fingerprint": chunks.parent_result_fingerprint,
        "normalizer_version": chunks.normalizer_version,
        "chunker_fingerprint": chunks.chunker.fingerprint,
        "chunk_ids": sorted(chunk.chunk_id for chunk in chunks.chunks),
    }


def build_queued_execution(
    *,
    key: str,
    confirmed_source_set_digest: str,
    confirmed_selection_digest: str,
    sources,
    attempt_number: int,
    created_at: datetime,
) -> RequirementN2Execution:
    snapshot = snapshot_sources(sources)
    return RequirementN2Execution(
        node_version=N2_NODE_VERSION,
        execution_id=f"N2-{key[:16].upper()}-{attempt_number:03d}",
        attempt_id=f"ATT-{attempt_number:03d}",
        execution_key=key,
        attempt_number=attempt_number,
        status=RequirementN2Status.QUEUED,
        confirmed_source_set_digest=confirmed_source_set_digest,
        confirmed_selection_digest=confirmed_selection_digest,
        input_sources=snapshot,
        source_progress=[
            RequirementN2SourceProgress(source_id=source.source_id)
            for source in snapshot
        ],
        created_at=created_at,
    )
