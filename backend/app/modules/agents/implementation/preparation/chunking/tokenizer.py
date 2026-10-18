import re

# Approximate lexical tokens, not model/subword tokens. Paths, identifiers,
# versions, numbers, and punctuation remain deterministic and useful for
# software documents without introducing a model tokenizer.
TOKEN_PATTERN = re.compile(
    r"(?:https?://[^\s]+|/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+|"
    r"[A-Za-z_][A-Za-z0-9_.-]*|\d+(?:\.\d+)*|[^\s\w])",
    re.UNICODE,
)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9#*`\"'])")


def lexical_tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text)


def count_tokens(text: str) -> int:
    return len(lexical_tokens(text))


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def bounded_slices(text: str, maximum: int, overlap: int) -> list[str]:
    """Split by token spans while retaining the original punctuation/spacing."""
    normalized = normalize_text(text)
    matches = list(TOKEN_PATTERN.finditer(normalized))
    if len(matches) <= maximum:
        return [normalized] if normalized else []
    result: list[str] = []
    start = 0
    while start < len(matches):
        end = min(start + maximum, len(matches))
        char_start = matches[start].start()
        char_end = matches[end - 1].end()
        result.append(normalized[char_start:char_end].strip())
        if end == len(matches):
            break
        start = max(start + 1, end - overlap)
    return result


def sentence_aware_slices(text: str, maximum: int, overlap: int) -> list[str]:
    """Prefer conservative sentence boundaries, then use bounded token windows."""
    normalized = normalize_text(text)
    sentences = [part.strip() for part in SENTENCE_BOUNDARY.split(normalized) if part.strip()]
    if len(sentences) <= 1:
        return bounded_slices(normalized, maximum, overlap)
    atomic: list[str] = []
    for sentence in sentences:
        atomic.extend(bounded_slices(sentence, maximum, overlap))
    result: list[str] = []
    current: list[str] = []
    for sentence in atomic:
        candidate = " ".join([*current, sentence])
        if current and count_tokens(candidate) > maximum:
            result.append(" ".join(current))
            tail: list[str] = []
            for prior in reversed(current):
                if count_tokens(" ".join([prior, *tail])) > overlap:
                    break
                tail.insert(0, prior)
            current = tail if count_tokens(" ".join([*tail, sentence])) <= maximum else []
        current.append(sentence)
    if current:
        result.append(" ".join(current))
    return result
