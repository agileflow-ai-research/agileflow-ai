"""Pure deterministic rule matcher with exact grounded evidence."""

import hashlib
import re

from app.modules.agents.testing_validation.intelligence.schemas import (
    ClassificationEvidence,
    ClassificationEvidenceType,
    TestingRuleClassificationResult,
    current_chunk_reference,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
)
from app.modules.agents.testing_validation.preparation.chunking.schemas import (
    TestingChunk,
    TestingChunkSet,
)

from .catalog import (
    AGENT4_RULE_CATALOG_FINGERPRINT,
    AGENT4_RULES_VERSION,
    TESTING_RULE_CATALOG,
    TestingRuleDefinition,
)


def _identity(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\x1f".join(map(str, parts)).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:32]}"


def classify_testing_chunk(
    chunk: TestingChunk,
    chunk_set: TestingChunkSet,
    *,
    confirmed_source_ids: set[str] | frozenset[str],
    processed_at,
    rules: tuple[TestingRuleDefinition, ...] = TESTING_RULE_CATALOG,
    catalog_fingerprint: str = AGENT4_RULE_CATALOG_FINGERPRINT,
) -> TestingRuleClassificationResult:
    reference = current_chunk_reference(
        chunk, chunk_set, confirmed_source_ids=confirmed_source_ids
    )
    found = {}
    for rule in rules:
        if rule.artifact_types and chunk.artifact_type not in rule.artifact_types:
            continue
        for match in re.finditer(rule.pattern, chunk.text, re.IGNORECASE | re.MULTILINE):
            start, end = match.span()
            if end <= start:
                continue
            quote = chunk.text[start:end]
            key = (rule.label, rule.rule_id, start, end, quote)
            if key in found:
                continue
            evidence_id = _identity(
                "A4EVD", chunk.chunk_id, rule.rule_id, rule.label.value,
                start, end, hashlib.sha256(quote.encode("utf-8")).hexdigest(),
                AGENT4_RULES_VERSION,
            )
            found[key] = ClassificationEvidence(
                evidence_id=evidence_id,
                chunk_id=chunk.chunk_id,
                label=rule.label,
                evidence_type=ClassificationEvidenceType.RULE,
                quote=quote,
                start_offset=start,
                end_offset=end,
                source_segment_ids=chunk.source_segment_ids,
                confidence=None,
                reason_code=rule.rule_id,
                explanation=rule.description,
            )
    order = {label: index for index, label in enumerate(TESTING_INTELLIGENCE_LABEL_ORDER)}
    evidence = sorted(
        found.values(),
        key=lambda item: (order[item.label], item.start_offset, item.reason_code),
    )
    labels = [label for label in TESTING_INTELLIGENCE_LABEL_ORDER if any(
        item.label is label for item in evidence
    )]
    return TestingRuleClassificationResult(
        result_id=_identity(
            "A4RUL", chunk.chunk_id, chunk.text_sha256, catalog_fingerprint
        ),
        chunk=reference,
        taxonomy_version=AGENT4_TESTING_TAXONOMY_VERSION,
        rules_version=AGENT4_RULES_VERSION,
        detected_labels=labels,
        rule_evidence=evidence,
        processed_at=processed_at,
    )
