from typing import Any

from app.common.id_generator import validate_id


def next_event_sequence_from_collection(collection: Any) -> int:
    """Return one greater than the largest valid EVT sequence in a collection."""
    largest_sequence = 0
    for document in collection.find({}, {"event_id": 1, "_id": 0}):
        event_id = document.get("event_id")
        if not isinstance(event_id, str):
            continue
        try:
            validate_id(event_id, "EVT")
        except ValueError:
            continue
        largest_sequence = max(
            largest_sequence,
            int(event_id.rsplit("-", maxsplit=1)[1]),
        )
    return largest_sequence + 1
