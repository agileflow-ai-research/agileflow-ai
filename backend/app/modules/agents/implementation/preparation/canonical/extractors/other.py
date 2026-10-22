from ..schemas import CanonicalSourceRef, CanonicalStatus, OtherContextData, OtherContextItem
from .common import ExtractionOutcome


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    return ExtractionOutcome(
        OtherContextData(
            context_items=[OtherContextItem(text=text, source_refs=[source])],
            usable_for_generation=False,
        ),
        CanonicalStatus.COMPLETE,
        [],
    )
