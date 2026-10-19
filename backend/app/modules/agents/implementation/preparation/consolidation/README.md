# Trusted project specification consolidation

WF-R3 reads its inputs from the backend. Upload-backed sources are eligible only
when `SemanticReviewService.get_final()` validates a current final trusted
artifact against its canonical, semantic, and human-decision fingerprints.
Raw extraction, classification candidates, and unfinished previews are never
accepted.

Manual `TEXT` inputs use the persisted WF-R1 preparation snapshot as a generic
project source. Their stable identity is the existing `LOCAL-*` input ID; their
source fingerprint is the content digest. They do not create an upload record
or filesystem path. The input's declared artifact type is retained only as a
provenance hint. WF-R3 creates a server-owned category confirmation conflict,
and only the selected stored candidate becomes trusted project data. Thus a
client declaration cannot silently establish semantic truth or inject a fact.
Replaying a snapshot reuses the same source and decision; content changes alter
the source-set digest/fingerprint and require confirmation again.

Consolidation expands artifacts into typed project items, removes only exact
normalized duplicates, and merges every identical item's source references.
Conflicts are emitted only for deterministic shared identities. Human decisions
refer to stored conflict and candidate IDs plus the expected fingerprint, so the
client cannot inject trusted replacement content.

The final `TrustedProjectSpecification` is a separate immutable envelope. It
groups items by artifact category and preserves project item → final artifact →
canonical/semantic provenance → chunk → original source references. Explicit
source IDs may create relationships; fuzzy or model-generated links are out of
scope.
