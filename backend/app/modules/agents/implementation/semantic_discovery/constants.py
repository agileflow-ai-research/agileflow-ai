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
