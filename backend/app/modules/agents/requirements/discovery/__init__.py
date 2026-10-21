"""Trusted evidence boundary for Agent 1 requirement discovery."""

from app.modules.agents.requirements.discovery.contracts import (
    CandidateDiscoverySignal,
    DiscoveryInputReference,
    ExcludedCandidateReference,
    FunctionalRequirement,
    NonFunctionalRequirement,
    RequirementCandidate,
    RequirementCandidateSet,
    StructuredRequirementSet,
    ValidatedDiscoveryChunk,
    ValidatedDiscoveryInput,
)
from app.modules.agents.requirements.discovery.structuring import (
    RequirementStructuringError,
    RequirementStructuringService,
)
from app.modules.agents.requirements.discovery.candidate_detection import (
    RequirementCandidateDetector,
)
from app.modules.agents.requirements.discovery.input import (
    DiscoveryInputError,
    DiscoveryInputErrorCode,
    DiscoveryInputLoader,
)

__all__ = [
    "DiscoveryInputError",
    "DiscoveryInputErrorCode",
    "DiscoveryInputLoader",
    "DiscoveryInputReference",
    "ExcludedCandidateReference",
    "FunctionalRequirement",
    "NonFunctionalRequirement",
    "CandidateDiscoverySignal",
    "RequirementCandidate",
    "RequirementCandidateDetector",
    "RequirementCandidateSet",
    "RequirementStructuringError",
    "RequirementStructuringService",
    "StructuredRequirementSet",
    "ValidatedDiscoveryChunk",
    "ValidatedDiscoveryInput",
]
