import re

from ..schemas import CanonicalSourceRef, CanonicalStatus, UiFlowData, UiFlowItem, UiFlowStep
from .common import ExtractionOutcome, unresolved


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    name_match = re.search(r"(?:UI\s+Flow|Flow)\s*[:#-]\s*([^\n]+)", text, re.I)
    arrow_line = next((line.strip() for line in text.splitlines() if "->" in line or "→" in line), None)
    values = []
    if arrow_line:
        values = [value.strip() for value in re.split(r"\s*(?:->|→)\s*", arrow_line) if value.strip()]
    if not values:
        numbered = []
        for line in text.splitlines():
            match = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
            if match:
                numbered.append(match.group(1).strip())
        values = numbered
    if not values:
        return ExtractionOutcome(UiFlowData(flows=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_UI_FLOW", source))
    flow = UiFlowItem(
        name=name_match.group(1).strip() if name_match else None,
        steps=[UiFlowStep(order=index + 1, screen_or_action=value)
               for index, value in enumerate(values)],
        source_refs=[source],
    )
    partial = len(values) < 2
    return ExtractionOutcome(UiFlowData(flows=[flow]),
                             CanonicalStatus.PARTIAL if partial else CanonicalStatus.COMPLETE,
                             unresolved("UI_FLOW_HAS_SINGLE_STEP", source) if partial else [])

