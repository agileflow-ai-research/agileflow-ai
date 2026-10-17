import re
from collections import defaultdict

from . import constants
from .rule_catalog import RULES, RuleDefinition
from .schemas import (
    ArtifactDetectionLabel,
    ChunkRuleDetection,
    RuleEvidence,
    RuleEvidenceSource,
    RulePrediction,
    RuleStrength,
    SemanticChunk,
)


NEGATION = re.compile(r"\b(?:do not|don't|must not|not available|is not|isn't|without)\b", re.IGNORECASE)


def strength_for_score(score: float) -> RuleStrength:
    if score >= constants.STRONG_RULE_SCORE:
        return RuleStrength.STRONG
    if score >= constants.MODERATE_RULE_SCORE:
        return RuleStrength.MODERATE
    return RuleStrength.WEAK


def _sources(chunk: SemanticChunk, rule: RuleDefinition) -> list[str]:
    if rule.source is RuleEvidenceSource.HEADING:
        return [*chunk.context.heading_path]
    if rule.source is RuleEvidenceSource.STRUCTURED_PATH:
        return [chunk.provenance.structured_path] if chunk.provenance.structured_path else []
    return [chunk.text]


def _negated(source: str, start: int, end: int) -> bool:
    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", end)
    if line_end < 0:
        line_end = len(source)
    return bool(NEGATION.search(source[line_start:line_end]))


def detect_chunk(chunk: SemanticChunk) -> ChunkRuleDetection:
    scores: dict[ArtifactDetectionLabel, float] = defaultdict(float)
    evidence: dict[ArtifactDetectionLabel, list[RuleEvidence]] = defaultdict(list)
    for definition in RULES:
        for source_text in _sources(chunk, definition):
            matches = list(definition.pattern.finditer(source_text))
            usable = [match for match in matches if not (
                definition.suppress_when_negated
                and _negated(source_text, match.start(), match.end())
            )]
            if not usable:
                continue
            # A rule contributes its primary weight once. Repeated independent
            # matches add only a small bounded reinforcement.
            scores[definition.label] += definition.weight + min(.10, .02 * (len(usable) - 1))
            for match in usable[:3]:
                matched = " ".join(match.group(0).split())[:240]
                item = RuleEvidence(
                    rule_id=definition.rule_id,
                    matched_text=matched,
                    source=definition.source,
                )
                if item not in evidence[definition.label]:
                    evidence[definition.label].append(item)

    predictions: list[RulePrediction] = []
    for label, raw_score in scores.items():
        score = round(min(1.0, raw_score), 2)
        if score < constants.MIN_RULE_SCORE:
            continue
        predictions.append(RulePrediction(
            label=label,
            rule_score=score,
            strength=strength_for_score(score),
            evidence=evidence[label][: constants.MAX_EVIDENCE_PER_PREDICTION],
        ))
    predictions.sort(key=lambda item: (-item.rule_score, item.label.value))
    predictions = predictions[: constants.MAX_LABELS_PER_CHUNK]
    if predictions:
        return ChunkRuleDetection(
            chunk_id=chunk.chunk_id,
            text_hash=chunk.text_hash,
            predictions=predictions,
            unclassified=False,
        )
    return ChunkRuleDetection(
        chunk_id=chunk.chunk_id,
        text_hash=chunk.text_hash,
        predictions=[RulePrediction(
            label=ArtifactDetectionLabel.OTHER_CONTEXT,
            rule_score=0.0,
            strength=RuleStrength.WEAK,
            evidence=[RuleEvidence(
                rule_id="NO_ARTIFACT_RULE_MATCH",
                matched_text="No artifact rule met the emission threshold.",
                source=RuleEvidenceSource.TEXT,
            )],
        )],
        unclassified=True,
    )
