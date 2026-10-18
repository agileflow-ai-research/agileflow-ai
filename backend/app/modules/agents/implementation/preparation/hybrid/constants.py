"""Versioned hybrid v1 engineering defaults.

These values are experimental defaults, not scientifically validated
thresholds. Changing policy behavior or any value requires a version bump.
"""

HYBRID_DECISION_VERSION = "1"
HYBRID_POLICY_VERSION = "1"

MODEL_STRONG_SUPPORT = 0.80
MODEL_MODERATE_SUPPORT = 0.60
MODEL_WEAK_SUPPORT = 0.50
MODEL_LABEL_EXPLOSION_COUNT = 4
MODEL_LABEL_EXPLOSION_THRESHOLD = 0.60
TOP_SCORE_MARGIN_THRESHOLD = 0.08

