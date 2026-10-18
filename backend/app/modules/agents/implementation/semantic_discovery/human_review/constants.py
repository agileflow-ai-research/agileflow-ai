"""Versioned research-mode human-review contract."""

HUMAN_REVIEW_SCHEMA_VERSION = "1"
HUMAN_REVIEW_POLICY_VERSION = "1"
MAX_REVIEW_NOTE_LENGTH = 500

# PP1 research mode deliberately requires every chunk to be verified so the
# resulting sample is not biased toward uncertain machine predictions.
RESEARCH_REQUIRES_ALL_CHUNKS = True

