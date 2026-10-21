"""Pure ordered rule evaluation with exact evidence offsets."""

from dataclasses import dataclass

from app.modules.agents.requirements.quality.clarity.catalog import (
    AMBIGUITY_RULES, AVAILABILITY_CONTEXT, CAPACITY_CONTEXT, CAPACITY_VAGUE,
    EXPLICIT_DURATION, EXPLICIT_FREQUENCY, EXPLICIT_PERCENTAGE,
    EXPLICIT_QUANTITY, PERFORMANCE_CONTEXT, PERFORMANCE_VAGUE,
)
from app.modules.agents.requirements.quality.contracts import (
    RequirementClarityIssueType,
    RequirementClaritySignal,
)


@dataclass(frozen=True)
class DetectedClaritySignal:
    issue_type: RequirementClarityIssueType
    signal: RequirementClaritySignal
    start: int
    end: int
    explanation: str
    rule_version: str


class RequirementClarityDetector:
    def detect(self, statement: str) -> tuple[DetectedClaritySignal, ...]:
        detected: list[DetectedClaritySignal] = []
        matches_by_signal = {}
        for rule in AMBIGUITY_RULES:
            matches = tuple(rule.pattern.finditer(statement))
            matches_by_signal[rule.signal] = matches
            detected.extend(DetectedClaritySignal(
                issue_type=rule.issue_type, signal=rule.signal,
                start=match.start(), end=match.end(), explanation=rule.explanation,
                rule_version=rule.rule_version,
            ) for match in matches)

        performance = PERFORMANCE_CONTEXT.search(statement)
        vague_performance = PERFORMANCE_VAGUE.search(statement)
        if performance and vague_performance and not EXPLICIT_DURATION.search(statement):
            detected.append(self._missing(
                RequirementClaritySignal.PERFORMANCE_TARGET_MISSING,
                vague_performance,
                "The performance requirement does not provide a measurable time target.",
            ))
        capacity = CAPACITY_CONTEXT.search(statement)
        vague_capacity = CAPACITY_VAGUE.search(statement)
        if capacity and vague_capacity and not EXPLICIT_QUANTITY.search(statement):
            detected.append(self._missing(
                RequirementClaritySignal.CAPACITY_TARGET_MISSING,
                vague_capacity,
                "The capacity requirement does not provide a measurable quantity.",
            ))
        availability = AVAILABILITY_CONTEXT.search(statement)
        if availability and not EXPLICIT_PERCENTAGE.search(statement):
            detected.append(self._missing(
                RequirementClaritySignal.AVAILABILITY_TARGET_MISSING,
                availability,
                "The availability requirement does not provide a measurable percentage target.",
            ))
        for vague_frequency in matches_by_signal.get(RequirementClaritySignal.VAGUE_FREQUENCY, ()):
            if not EXPLICIT_FREQUENCY.search(statement):
                detected.append(self._missing(
                    RequirementClaritySignal.FREQUENCY_VALUE_MISSING,
                    vague_frequency,
                    "The frequency requirement does not provide a concrete schedule.",
                ))
        for condition in matches_by_signal.get(RequirementClaritySignal.UNCLEAR_CONDITION, ()):
            detected.append(self._missing(
                RequirementClaritySignal.CONDITION_DETAIL_MISSING,
                condition,
                "The conditional requirement does not define when the condition applies.",
            ))

        # Catalog order is represented by insertion order; offsets order repeated
        # matches of the same rule. Remove only identical rule/span emissions.
        unique = []
        seen = set()
        for item in detected:
            key = (item.issue_type, item.signal, item.start, item.end)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return tuple(unique)

    @staticmethod
    def _missing(signal, match, explanation):
        return DetectedClaritySignal(
            issue_type=RequirementClarityIssueType.MISSING_INFORMATION,
            signal=signal, start=match.start(), end=match.end(),
            explanation=explanation, rule_version="1",
        )
