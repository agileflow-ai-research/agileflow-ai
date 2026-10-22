from collections.abc import Sequence


def combine_with_offsets(parts: Sequence[str]) -> tuple[str, list[tuple[int, int]]]:
    """Join non-empty extracted parts while retaining deterministic source offsets."""
    combined = ""
    offsets: list[tuple[int, int]] = []
    for part in parts:
        if not part:
            offsets.append((len(combined), len(combined)))
            continue
        if combined:
            combined += "\n\n"
        start_offset = len(combined)
        combined += part
        offsets.append((start_offset, len(combined)))
    return combined, offsets
