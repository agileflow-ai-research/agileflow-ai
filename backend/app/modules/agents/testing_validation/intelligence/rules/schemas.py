from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.modules.agents.testing_validation.intelligence.schemas import (
    StrictIntelligenceContract,
    TestingRuleClassificationResult,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
)

from .catalog import AGENT4_RULES_VERSION


class TestingRuleClassificationManifest(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    rules_version: Literal[AGENT4_RULES_VERSION]
    rule_catalog_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    chunk_set_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_ids: list[str] = Field(min_length=1)
    results: list[TestingRuleClassificationResult] = Field(min_length=1)
    processed_at: datetime

    @model_validator(mode="after")
    def validate_manifest(self) -> "TestingRuleClassificationManifest":
        result_ids = [result.chunk.chunk_id for result in self.results]
        if result_ids != self.chunk_ids:
            raise ValueError("rule results must match the ordered chunk manifest")
        if len(self.chunk_ids) != len(set(self.chunk_ids)):
            raise ValueError("rule manifest chunk identities must be unique")
        if any(
            result.chunk.agent_project_id != self.agent_project_id
            or result.chunk.source_id != self.source_id
            or result.chunk.chunk_set_fingerprint != self.chunk_set_fingerprint
            or result.taxonomy_version != self.taxonomy_version
            or result.rules_version != self.rules_version
            for result in self.results
        ):
            raise ValueError("rule result provenance does not match its manifest")
        return self

