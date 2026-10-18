import json
import re

import yaml

from ..schemas import CanonicalSourceRef, CanonicalStatus, TestCaseItem, TestCasesData
from .common import ExtractionOutcome, content_lines, unresolved


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    structured = _structured_test_cases(text, source)
    if structured:
        partial = any(case.expected_result is None for case in structured)
        return ExtractionOutcome(
            TestCasesData(test_cases=structured),
            CanonicalStatus.PARTIAL if partial else CanonicalStatus.COMPLETE,
            unresolved("TEST_EXPECTED_RESULT_NOT_EXPLICIT", source) if partial else [],
        )
    raw = "\n".join(content_lines(text))
    identifier = re.search(r"\b((?:TC|API-T)[- ]?\d+)\s*[:.-]?\s*", raw, re.I)
    gwt = re.search(r"\bGiven\s+(.+?)\s+When\s+(.+?)\s+Then\s+(.+?)(?:$|\n)", raw, re.I | re.S)
    expected = re.search(r"\bExpected\s+Result\s*[:.-]\s*(.+)", raw, re.I)
    steps = [match.group(1).strip() for match in re.finditer(r"(?:^|\n)\s*\d+[.)]\s+(.+)", text)]
    if not (identifier or gwt or expected or steps):
        return ExtractionOutcome(TestCasesData(test_cases=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_TEST_CASE_STRUCTURE", source))
    item_id = identifier.group(1).upper().replace(" ", "-") if identifier else None
    description = raw[identifier.end():].splitlines()[0].strip() if identifier and raw[identifier.end():].strip() else None
    preconditions = [gwt.group(1).strip()] if gwt else []
    if gwt:
        steps = [gwt.group(2).strip()]
    expected_result = gwt.group(3).strip() if gwt else (expected.group(1).strip() if expected else None)
    item = TestCaseItem(
        id=item_id, description=description, preconditions=preconditions,
        steps=steps, expected_result=expected_result, source_refs=[source],
    )
    partial = expected_result is None
    return ExtractionOutcome(TestCasesData(test_cases=[item]),
                             CanonicalStatus.PARTIAL if partial else CanonicalStatus.COMPLETE,
                             unresolved("TEST_EXPECTED_RESULT_NOT_EXPLICIT", source) if partial else [])


def _structured_test_cases(text: str, source: CanonicalSourceRef) -> list[TestCaseItem]:
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            value = yaml.safe_load(text)
        except (TypeError, ValueError, yaml.YAMLError):
            return []
    if isinstance(value, dict):
        raw_cases = value.get("test_cases", value.get("tests"))
    else:
        raw_cases = value
    if not isinstance(raw_cases, list):
        return []
    cases = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            continue
        raw_steps = raw_case.get("steps", [])
        raw_preconditions = raw_case.get("preconditions", [])
        steps = [str(step) for step in raw_steps] if isinstance(raw_steps, list) else []
        preconditions = (
            [str(condition) for condition in raw_preconditions]
            if isinstance(raw_preconditions, list) else []
        )
        expected = raw_case.get("expected_result", raw_case.get("expected"))
        description = raw_case.get("description", raw_case.get("name"))
        if not any((raw_case.get("id"), description, steps, preconditions, expected)):
            continue
        cases.append(TestCaseItem(
            id=str(raw_case["id"]) if raw_case.get("id") is not None else None,
            description=str(description) if description is not None else None,
            preconditions=preconditions,
            steps=steps,
            expected_result=str(expected) if expected is not None else None,
            source_refs=[source],
        ))
    return cases

