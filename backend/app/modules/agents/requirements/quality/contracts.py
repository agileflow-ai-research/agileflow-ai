"""Immutable contracts at the validated N3-to-N4 boundary."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.contracts import StructuredRequirementType
from app.modules.agents.requirements.processing.preparation.schemas import (
    NormalizedProvenanceSpan,
)


class StrictQualityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QualityRequirement(StrictQualityContract):
    requirement_id: str = Field(pattern=r"^(?:FR|NFR)-[0-9A-F]{16}$")
    requirement_type: StructuredRequirementType
    statement: str = Field(min_length=1)
    candidate_id: str = Field(pattern=r"^RC-[0-9A-F]{16}$")
    candidate_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{16}$")
    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    provenance: tuple[NormalizedProvenanceSpan, ...] = Field(min_length=1)
    classification_confidence: float = Field(ge=0.0, le=1.0)
    classifier_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidatedQualityInput(StrictQualityContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    n3_execution_id: str = Field(pattern=r"^N3-[0-9A-F]{16}-\d{3}$")
    n3_attempt: int = Field(ge=1)
    n2_execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    discovery_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_set_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    classifier_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    requirements: tuple[QualityRequirement, ...] = ()
    input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
