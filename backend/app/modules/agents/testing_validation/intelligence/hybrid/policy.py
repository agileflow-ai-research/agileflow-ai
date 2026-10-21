"""Versioned, provisional H1 hybrid policy.

The thresholds are conservative engineering defaults. They are not calibrated
probabilities and must be revisited through research evaluation before H2.
"""

import hashlib
import json
from dataclasses import asdict, dataclass

from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
)


HYBRID_POLICY_VERSION = "H1"
RULE_MODEL_SUPPORT_THRESHOLD = 0.60
RULE_MODEL_CONFLICT_THRESHOLD = 0.35
MODEL_ONLY_REVIEW_THRESHOLD = 0.80
HYBRID_SCHEMA_VERSION = "1"
POLICY_SEMANTICS = "PROVISIONAL_CONSERVATIVE_ENGINEERING_DEFAULTS_NOT_CALIBRATED"


@dataclass(frozen=True, slots=True)
class HybridPolicy:
    version: str = HYBRID_POLICY_VERSION
    taxonomy_version: str = AGENT4_TESTING_TAXONOMY_VERSION
    rule_model_support_threshold: float = RULE_MODEL_SUPPORT_THRESHOLD
    rule_model_conflict_threshold: float = RULE_MODEL_CONFLICT_THRESHOLD
    model_only_review_threshold: float = MODEL_ONLY_REVIEW_THRESHOLD
    semantics: str = POLICY_SEMANTICS
    decision_rules_version: str = "H1-DECISIONS-1"
    non_testable_policy: str = "SUPPRESS_WHEN_ANY_TESTABLE_CANDIDATE"

    def __post_init__(self):
        if not (
            0 <= self.rule_model_conflict_threshold
            <= self.rule_model_support_threshold
            <= self.model_only_review_threshold
            <= 1
        ):
            raise ValueError("hybrid thresholds must be ordered within 0..1")


H1_POLICY = HybridPolicy()


def hybrid_policy_fingerprint(policy: HybridPolicy = H1_POLICY) -> str:
    canonical = json.dumps(asdict(policy), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


HYBRID_POLICY_FINGERPRINT = hybrid_policy_fingerprint()
