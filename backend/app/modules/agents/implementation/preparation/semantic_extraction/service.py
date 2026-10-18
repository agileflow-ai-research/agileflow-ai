import hashlib
import json

from pydantic import TypeAdapter, ValidationError

from app.modules.agents.implementation.preparation.canonical.schemas import (
    CanonicalStatus,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)

from . import constants
from .grounding import ground_proposal
from .merge import merge_grounded
from .protocols import SemanticExtractorAdapter
from .schemas import (
    SemanticExtractionProposal, SemanticExtractionRequest,
    SemanticExtractionSessionResult, SemanticValidationReport,
    SemanticValidationStatus,
)


class SemanticExtractionContractError(ValueError):
    pass


class SemanticExtractionService:
    _proposal_adapter = TypeAdapter(SemanticExtractionProposal)

    def run(
        self, request: SemanticExtractionRequest,
        adapter: SemanticExtractorAdapter,
    ) -> SemanticExtractionSessionResult:
        self._validate_request(request)
        raw_proposal = adapter.extract(request)
        try:
            serialized = json.dumps(
                raw_proposal.model_dump(mode="json", by_alias=True)
                if hasattr(raw_proposal, "model_dump") else raw_proposal,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise SemanticExtractionContractError("MALFORMED_SEMANTIC_PROPOSAL") from exc
        if len(serialized) > constants.MAX_PROPOSAL_SERIALIZED_BYTES:
            raise SemanticExtractionContractError("SEMANTIC_PROPOSAL_TOO_LARGE")
        try:
            proposal = self._proposal_adapter.validate_json(serialized)
        except ValidationError as exc:
            raise SemanticExtractionContractError("MALFORMED_SEMANTIC_PROPOSAL") from exc
        if (self._semantic_item_count(proposal.model_dump(mode="python"))
                > constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT):
            raise SemanticExtractionContractError("TOO_MANY_SEMANTIC_ITEMS")
        if proposal.artifact_type is not request.artifact_type:
            raise SemanticExtractionContractError("WRONG_ARTIFACT_TYPE")
        grounding = ground_proposal(request, proposal)
        merged = merge_grounded(request, grounding)
        conflicts = merged.conflicts
        if conflicts:
            proposal_status = SemanticValidationStatus.HUMAN_REVIEW_REQUIRED
        elif not grounding.facts:
            proposal_status = SemanticValidationStatus.REJECTED
        elif grounding.rejections:
            proposal_status = SemanticValidationStatus.PARTIALLY_GROUNDED
        else:
            proposal_status = SemanticValidationStatus.GROUNDED
        report = SemanticValidationReport(
            proposal_status=proposal_status,
            accepted_facts=len(grounding.facts),
            rejected_facts=len(grounding.rejections),
            conflict_count=len(conflicts),
            rejections=grounding.rejections,
            conflicts=conflicts,
        )
        return SemanticExtractionSessionResult(
            artifact_id=request.deterministic_artifact.artifact_id,
            artifact_type=request.artifact_type,
            deterministic_status=request.deterministic_artifact.status,
            semantic_contract_version=constants.SEMANTIC_CONTRACT_VERSION,
            grounding_version=constants.EVIDENCE_GROUNDING_VERSION,
            merge_policy_version=constants.SEMANTIC_MERGE_POLICY_VERSION,
            proposal=proposal, validation=report, merged_artifact=merged,
        )

    @staticmethod
    def _validate_request(request):
        artifact = request.deterministic_artifact
        if artifact.status is CanonicalStatus.COMPLETE:
            raise SemanticExtractionContractError("COMPLETE_ARTIFACT_NOT_ELIGIBLE")
        if request.artifact_type is ArtifactDetectionLabel.OTHER_CONTEXT:
            raise SemanticExtractionContractError("OTHER_CONTEXT_NOT_ELIGIBLE")
        if request.artifact_type not in request.verified_labels:
            raise SemanticExtractionContractError("ARTIFACT_TYPE_NOT_HUMAN_VERIFIED")
        if artifact.artifact_type is not request.artifact_type:
            raise SemanticExtractionContractError("WRONG_ARTIFACT_TYPE")
        if (hashlib.sha256(request.source_text.encode("utf-8")).hexdigest()
                != request.chunk_text_hash):
            raise SemanticExtractionContractError("STALE_TRUSTED_SOURCE")
        if not artifact.source_refs or any(
            source.upload_id != request.upload_id
            or source.chunk_id != request.chunk_id
            or source.text_hash != request.chunk_text_hash
            for source in artifact.source_refs
        ):
            raise SemanticExtractionContractError("STALE_TRUSTED_SOURCE")

    @staticmethod
    def _semantic_item_count(value):
        if isinstance(value, dict):
            return (1 if "evidence" in value else 0) + sum(
                SemanticExtractionService._semantic_item_count(child)
                for child in value.values()
            )
        if isinstance(value, list):
            return sum(
                SemanticExtractionService._semantic_item_count(child)
                for child in value
            )
        return 0
