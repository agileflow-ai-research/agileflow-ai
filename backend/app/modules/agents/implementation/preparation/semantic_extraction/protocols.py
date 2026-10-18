from typing import Protocol

from .schemas import SemanticExtractionProposal, SemanticExtractionRequest


class SemanticExtractorAdapter(Protocol):
    """Boundary implemented by a future model adapter, never by the client."""

    def extract(
        self, request: SemanticExtractionRequest
    ) -> SemanticExtractionProposal:
        ...
