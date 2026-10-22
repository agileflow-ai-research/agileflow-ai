"""Chunker v1 engineering defaults.

These lexical-token thresholds are a PP1 baseline and are intentionally
centralized so later section-aware versus fixed-window experiments can tune
them without changing the persisted result contract.
"""

CHUNKER_VERSION = "1"
TARGET_CHUNK_TOKENS = 350
MAX_CHUNK_TOKENS = 500
MIN_CHUNK_TOKENS = 80
OVERLAP_TOKENS = 60
MAX_CHUNKS_PER_DOCUMENT = 2000

# Rule detector v1 engineering defaults. Scores are explainable heuristic
# strengths, not calibrated probabilities. Thresholds are expected to be
# evaluated and tuned during the offline research comparison.
RULE_DETECTOR_VERSION = "1"
MIN_RULE_SCORE = 0.35
MODERATE_RULE_SCORE = 0.55
STRONG_RULE_SCORE = 0.80
MAX_LABELS_PER_CHUNK = 4
MAX_EVIDENCE_PER_PREDICTION = 8
