# Agent 1 N2D evidence preparation

N2D consumes only validated, compatible `COMPLETED` N2A/N2B/N2C results. It never reads raw source bytes. It writes separate status, normalized-result, and chunk-result sidecars without changing source or parent-processing artifacts.

Normalization is conservative and versioned: line endings become LF, trailing line whitespace and outer whitespace are removed, and runs of more than one blank line are collapsed. Text is never summarized or rewritten.

Sentence segmentation uses a local cached `spacy.blank("en")` pipeline with the rule-based `sentencizer`; no language model is downloaded. The deterministic fallback exists only for environments where the declared spaCy dependency is not installed, and its distinct identity participates in the chunker fingerprint.

Defaults are 900 target characters, 1,200 maximum characters, and one overlapping sentence. Chunks never combine sources or structural units. Chunk IDs hash the project/source, parent result, versions/configuration, normalized range, content, and provenance.
