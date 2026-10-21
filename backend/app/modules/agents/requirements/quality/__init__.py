"""Requirement quality engineering boundaries."""

from app.modules.agents.requirements.quality.contracts import (
    ExactDuplicateGroup,
    ExactDuplicateMember,
    ExactDuplicateResult,
    QualityRequirement,
    ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.exact_duplicates import ExactDuplicateDetector
from app.modules.agents.requirements.quality.input import (
    QualityInputError,
    QualityInputErrorCode,
    QualityInputLoader,
)

__all__ = [
    "QualityInputError",
    "QualityInputErrorCode",
    "QualityInputLoader",
    "QualityRequirement",
    "ValidatedQualityInput",
    "ExactDuplicateDetector",
    "ExactDuplicateGroup",
    "ExactDuplicateMember",
    "ExactDuplicateResult",
]
