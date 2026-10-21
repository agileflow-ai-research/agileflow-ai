from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.modules.agents.testing_validation.intelligence.schemas import (
    StrictIntelligenceContract,
    TestingZeroShotClassificationResult,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
)

from . import constants


class TestingZeroShotManifest(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    zero_shot_version: Literal["Z1"] = "Z1"
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    label_description_version: Literal[
        AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION
    ]
    hypothesis_template_version: Literal["ZH1"]
    hypothesis_template: str
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_id: str
    model_revision: str
    task: Literal["zero-shot-classification"]
    multi_label: Literal[True]
    device: Literal["cpu", "cuda"]
    batch_size: int = Field(ge=1)
    truncation_strategy: Literal["ONLY_FIRST_PRESERVE_HYPOTHESIS"]
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    chunk_set_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_ids: list[str] = Field(min_length=1)
    results: list[TestingZeroShotClassificationResult] = Field(min_length=1)
    processed_at: datetime

    @model_validator(mode="after")
    def validate_complete_manifest(self):
        if self.chunk_ids != [result.chunk.chunk_id for result in self.results]:
            raise ValueError("zero-shot results must match ordered chunk IDs")
        if len(self.chunk_ids) != len(set(self.chunk_ids)):
            raise ValueError("zero-shot chunk IDs must be unique")
        if any(
            result.chunk.agent_project_id != self.agent_project_id
            or result.chunk.source_id != self.source_id
            or result.chunk.chunk_set_fingerprint != self.chunk_set_fingerprint
            or result.taxonomy_version != self.taxonomy_version
            or result.model_id != self.model_id
            or result.model_revision != self.model_revision
            or result.label_description_version != self.label_description_version
            or result.hypothesis_template_version != self.hypothesis_template_version
            for result in self.results
        ):
            raise ValueError("zero-shot result provenance does not match manifest")
        return self

