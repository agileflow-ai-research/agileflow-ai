TRACEABILITY_SCHEMA_VERSION = "1"
TRACEABILITY_ENGINE_VERSION = "TR1"
LEXICAL_POLICY_VERSION = "LX1"

# Conservative engineering threshold, not calibrated semantic confidence.
LEXICAL_JACCARD_THRESHOLD = 0.72
LEXICAL_MINIMUM_SHARED_TOKENS = 3

STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "shall", "should", "that",
    "the", "to", "when", "with", "will", "must", "may", "can",
    "system", "application", "user", "users", "requirement", "feature",
})
