"""Strict contracts exposed by the validated N3 input boundary."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.processing.preparation.schemas import EvidenceChunk


class StrictDiscoveryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DiscoveryInputReference(StrictDiscoveryContract):
    n2_execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    n2_attempt: int = Field(ge=1)
    chunk_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidatedDiscoveryChunk(StrictDiscoveryContract):
    """An existing N2 chunk plus its validated parent/source identity."""

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_version: str = Field(pattern=r"^\d+$")
    chunker_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk: EvidenceChunk


class ValidatedDiscoveryInput(StrictDiscoveryContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    reference: DiscoveryInputReference
    chunks: tuple[ValidatedDiscoveryChunk, ...] = Field(min_length=1)
    input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
