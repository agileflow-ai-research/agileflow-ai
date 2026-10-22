import re
from dataclasses import dataclass


TOKEN_PATTERN = re.compile(
    r"(?:https?://[^\s]+|/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+|"
    r"[A-Za-z_][A-Za-z0-9_.-]*|\d+(?:\.\d+)*|[^\s\w])",
    re.UNICODE,
)


@dataclass(frozen=True)
class TokenSlice:
    text: str
    start_offset: int
    end_offset: int
    overlap_token_count: int


def token_matches(text: str) -> list[re.Match[str]]:
    return list(TOKEN_PATTERN.finditer(text))


def count_tokens(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def bounded_token_slices(
    text: str, *, maximum: int, overlap: int
) -> list[TokenSlice]:
    matches = token_matches(text)
    if not matches:
        return []
    if len(matches) <= maximum:
        return [TokenSlice(text, 0, len(text), 0)]
    slices: list[TokenSlice] = []
    start = 0
    while start < len(matches):
        end = min(start + maximum, len(matches))
        char_start = matches[start].start()
        char_end = matches[end - 1].end()
        slices.append(
            TokenSlice(
                text=text[char_start:char_end],
                start_offset=char_start,
                end_offset=char_end,
                overlap_token_count=0 if not slices else min(overlap, end - start),
            )
        )
        if end == len(matches):
            break
        next_start = max(start + 1, end - overlap)
        if next_start <= start:  # Defensive guard for invalid future policies.
            next_start = start + 1
        start = next_start
    return slices
