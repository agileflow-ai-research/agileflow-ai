"""Conservative, ordered clarity rule catalog."""

import re
from dataclasses import dataclass

from app.modules.agents.requirements.quality.contracts import (
    RequirementClarityIssueType,
    RequirementClaritySignal,
)


CLARITY_RULE_CATALOG_VERSION = "1"
AMBIGUITY_TAXONOMY_VERSION = "1"
MISSING_INFORMATION_TAXONOMY_VERSION = "1"


@dataclass(frozen=True)
class ClarityRule:
    signal: RequirementClaritySignal
    issue_type: RequirementClarityIssueType
    pattern: re.Pattern[str]
    explanation: str
    rule_version: str = "1"


def phrase(expression: str) -> re.Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


AMBIGUITY_RULES = (
    ClarityRule(
        RequirementClaritySignal.VAGUE_QUALIFIER,
        RequirementClarityIssueType.AMBIGUITY,
        phrase(r"(?<![\w-])(?:quickly|rapidly|soon|efficiently|adequate|sufficient|reasonable)(?![\w-])"),
        "The requirement uses a qualifier without measurable criteria.",
    ),
    ClarityRule(
        RequirementClaritySignal.VAGUE_QUANTIFIER,
        RequirementClarityIssueType.AMBIGUITY,
        phrase(r"(?<![\w-])(?:many|several|few|some|numerous|minimal)(?![\w-])"),
        "The requirement uses an imprecise quantity.",
    ),
    ClarityRule(
        RequirementClaritySignal.VAGUE_FREQUENCY,
        RequirementClarityIssueType.AMBIGUITY,
        phrase(r"(?<![\w-])(?:regularly|periodically)(?![\w-])"),
        "The requirement uses a frequency term without a concrete schedule.",
    ),
    ClarityRule(
        RequirementClaritySignal.SUBJECTIVE_TERM,
        RequirementClarityIssueType.AMBIGUITY,
        phrase(r"(?<![\w-])(?:user-friendly|easy\s+to\s+use|intuitive|seamless|robust|highly\s+available)(?![\w-])"),
        "The requirement uses a subjective quality term without objective criteria.",
    ),
    ClarityRule(
        RequirementClaritySignal.OPEN_ENDED_PHRASE,
        RequirementClarityIssueType.AMBIGUITY,
        phrase(r"(?<![\w-])(?:etc\.|etcetera|and\s+so\s+on|and\s+similar|and\s+related\s+items)(?![\w-])"),
        "The requirement uses open-ended language that does not define a closed scope.",
    ),
    ClarityRule(
        RequirementClaritySignal.UNCLEAR_CONDITION,
        RequirementClarityIssueType.AMBIGUITY,
        phrase(r"(?<![\w-])(?:when\s+appropriate|when\s+necessary|if\s+necessary|if\s+required|as\s+needed)(?![\w-])"),
        "The requirement depends on a condition whose criteria are not defined.",
    ),
)


EXPLICIT_DURATION = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:milliseconds?|ms|seconds?|secs?|minutes?|mins?|hours?)\b",
    re.IGNORECASE,
)
EXPLICIT_QUANTITY = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s+(?:concurrent\s+)?(?:users?|requests?|transactions?|records?|connections?|sessions?|files?)\b", re.IGNORECASE)
EXPLICIT_PERCENTAGE = re.compile(r"\b\d+(?:\.\d+)?\s*%", re.IGNORECASE)
EXPLICIT_FREQUENCY = re.compile(r"\b(?:every\s+\d+(?:\.\d+)?\s*(?:minutes?|hours?|days?|weeks?|months?)|daily|weekly|monthly)\b", re.IGNORECASE)
PERFORMANCE_CONTEXT = re.compile(r"\b(?:respond|response|load|latency)\b", re.IGNORECASE)
PERFORMANCE_VAGUE = re.compile(r"\b(?:quickly|rapidly|soon|fast)\b", re.IGNORECASE)
CAPACITY_CONTEXT = re.compile(r"\b(?:support|handle|process|scale\s+to)\b[^.]{0,80}\b(?:concurrent\s+)?(?:users?|requests?|transactions?|records?|connections?|sessions?|files?)\b", re.IGNORECASE)
CAPACITY_VAGUE = re.compile(r"\b(?:many|several|numerous|few|some)\b", re.IGNORECASE)
AVAILABILITY_CONTEXT = re.compile(r"\b(?:highly\s+available|availability|uptime)\b", re.IGNORECASE)
