import re

from ..schemas import (
    AcceptanceCriteriaData, AcceptanceCriterionItem, CanonicalSourceRef,
    CanonicalStatus, FunctionalRequirementsData, NfrCategory,
    NonFunctionalRequirementItem, NonFunctionalRequirementsData,
    RequirementItem, TechnicalConstraintItem, TechnicalConstraintsData,
    UserStoriesData, UserStoryItem,
)
from .common import ExtractionOutcome, content_lines, unique, unresolved


def functional(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    items = []
    for raw in text.splitlines():
        numbered = re.match(r"^\s*\d+[.)]\s+(.+)$", raw)
        line = numbered.group(1).strip() if numbered else re.sub(r"^\s*[-*+]\s+", "", raw).strip()
        if not line:
            continue
        match = re.match(r"^(FR[- ]?\d+)\s*[:.-]?\s*(.+)$", line, re.I)
        if match:
            item_id, statement = _normalized_id(match.group(1), "FR"), match.group(2).strip()
        elif re.search(r"\b(?:the system|the user)\s+shall\b", line, re.I):
            item_id, statement = None, line
        elif numbered:
            item_id, statement = None, line
        else:
            continue
        if statement:
            items.append(RequirementItem(id=item_id, statement=statement, source_refs=[source]))
    items = _dedupe(items, lambda item: (item.id or "", item.statement.casefold()))
    if not items:
        return ExtractionOutcome(FunctionalRequirementsData(requirements=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_FUNCTIONAL_REQUIREMENT", source))
    return ExtractionOutcome(FunctionalRequirementsData(requirements=items), CanonicalStatus.COMPLETE, [])


def non_functional(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    items = []
    for line in content_lines(text):
        match = re.match(r"^(NFR[- ]?\d+)\s*[:.-]?\s*(.+)$", line, re.I)
        item_id, statement = (None, line)
        if match:
            item_id, statement = _normalized_id(match.group(1), "NFR"), match.group(2).strip()
        category = _nfr_category(statement)
        target = _measurable_target(statement)
        if match or category or re.search(r"\bshall\b", statement, re.I):
            items.append(NonFunctionalRequirementItem(
                id=item_id, statement=statement, category=category,
                measurable_target=target, source_refs=[source],
            ))
    items = _dedupe(items, lambda item: (item.id or "", item.statement.casefold()))
    if not items:
        return ExtractionOutcome(NonFunctionalRequirementsData(requirements=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_NON_FUNCTIONAL_REQUIREMENT", source))
    return ExtractionOutcome(NonFunctionalRequirementsData(requirements=items), CanonicalStatus.COMPLETE, [])


def user_stories(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    raw = " ".join(content_lines(text))
    story_id_match = re.match(r"^(US[- ]?\d+)\s*[:.-]?\s*", raw, re.I)
    story_id = _normalized_id(story_id_match.group(1), "US") if story_id_match else None
    statement = raw[story_id_match.end():] if story_id_match else raw
    match = re.search(
        r"\bAs\s+an?\s+(.+?),\s*I\s+want\s+(.*?)(?:\s+so\s+that\s+(.+?))?[.]?$",
        statement, re.I,
    )
    if not match:
        return ExtractionOutcome(UserStoriesData(stories=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_USER_STORY_STRUCTURE", source))
    role, goal, benefit = (match.group(1).strip(), match.group(2).strip(),
                           match.group(3).strip() if match.group(3) else None)
    item = UserStoryItem(id=story_id, role=role, goal=goal, benefit=benefit,
                         raw_statement=statement, source_refs=[source])
    missing = [] if benefit else unresolved("USER_STORY_BENEFIT_NOT_EXPLICIT", source)
    return ExtractionOutcome(UserStoriesData(stories=[item]),
                             CanonicalStatus.COMPLETE if benefit else CanonicalStatus.PARTIAL,
                             missing)


def acceptance(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    raw = "\n".join(content_lines(text))
    criterion_id_match = re.search(r"\b(AC[- ]?\d+)\s*[:.-]?\s*", raw, re.I)
    criterion_id = _normalized_id(criterion_id_match.group(1), "AC") if criterion_id_match else None
    statement = raw[criterion_id_match.end():].strip() if criterion_id_match else raw
    gwt = re.search(r"\bGiven\s+(.+?)\s+When\s+(.+?)\s+Then\s+(.+?)(?:$|\n)", statement, re.I | re.S)
    expected = re.search(r"\bExpected\s+Result\s*[:.-]\s*(.+)", statement, re.I)
    if not (criterion_id_match or gwt or expected):
        return ExtractionOutcome(AcceptanceCriteriaData(criteria=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_ACCEPTANCE_CRITERION", source))
    item = AcceptanceCriterionItem(
        id=criterion_id, statement=statement,
        given=gwt.group(1).strip() if gwt else None,
        when=gwt.group(2).strip() if gwt else None,
        then=gwt.group(3).strip() if gwt else (expected.group(1).strip() if expected else None),
        source_refs=[source],
    )
    partial = not criterion_id_match and not (gwt and all(gwt.groups()))
    missing = unresolved("ACCEPTANCE_CRITERION_STRUCTURE_PARTIAL", source) if partial else []
    return ExtractionOutcome(AcceptanceCriteriaData(criteria=[item]),
                             CanonicalStatus.PARTIAL if partial else CanonicalStatus.COMPLETE,
                             missing)


def constraints(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    items = []
    for line in content_lines(text):
        match = re.match(r"^((?:CONSTRAINT|CONST|TC)[- ]?\d+)\s*[:.-]?\s*(.+)$", line, re.I)
        statement = match.group(2).strip() if match else line
        if not (match or re.search(r"\b(?:must use|must not use|required to use|only supports?|restricted to|browser|runtime|deployment)\b", statement, re.I)):
            continue
        kind = _constraint_type(statement)
        items.append(TechnicalConstraintItem(
            id=match.group(1).upper().replace(" ", "-") if match else None,
            statement=statement, constraint_type=kind, source_refs=[source],
        ))
    items = _dedupe(items, lambda item: (item.id or "", item.statement.casefold()))
    if not items:
        return ExtractionOutcome(TechnicalConstraintsData(constraints=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_TECHNICAL_CONSTRAINT", source))
    return ExtractionOutcome(TechnicalConstraintsData(constraints=items), CanonicalStatus.COMPLETE, [])


def _normalized_id(value, prefix):
    digits = re.search(r"\d+", value).group()
    return f"{prefix}-{digits.zfill(3)}"


def _nfr_category(statement):
    mappings = (
        (NfrCategory.PERFORMANCE, r"response time|latency|throughput|performance"),
        (NfrCategory.SECURITY, r"security|secure|encrypt|authentication|authorization"),
        (NfrCategory.AVAILABILITY, r"availability|uptime"),
        (NfrCategory.USABILITY, r"usability|accessible|accessibility|user experience"),
        (NfrCategory.SCALABILITY, r"scalab"),
        (NfrCategory.RELIABILITY, r"reliab|fault tolerance"),
        (NfrCategory.MAINTAINABILITY, r"maintainab"),
        (NfrCategory.COMPATIBILITY, r"compatib"),
    )
    return next((category for category, pattern in mappings if re.search(pattern, statement, re.I)), None)


def _measurable_target(statement):
    match = re.search(
        r"\b(?:below|under|within|at least|at most|no more than|greater than|less than)\s+"
        r"\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|minutes?|%|percent|requests?/s|rps)\b",
        statement, re.I,
    )
    return match.group(0) if match else None


def _constraint_type(statement):
    for value, pattern in (("PROHIBITION", r"must not|do not|prohibited"),
                           ("RUNTIME", r"runtime|python|java|node"),
                           ("DEPLOYMENT", r"deploy|container|cloud"),
                           ("BROWSER", r"browser")):
        if re.search(pattern, statement, re.I):
            return value
    return None


def _dedupe(items, key):
    seen, result = set(), []
    for item in items:
        marker = key(item)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result
