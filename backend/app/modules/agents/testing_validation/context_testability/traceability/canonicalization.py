import hashlib
import json
import re

from .constants import STOPWORDS


ID_PATTERN = re.compile(
    r"\b(FR|NFR|US|AC|FEAT(?:URE)?)[- ]([0-9]{1,6}|[0-9A-F]{16})\b",
    re.IGNORECASE,
)
API_PATTERN = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[A-Za-z0-9_./:{}-]+)",
    re.IGNORECASE,
)
MALFORMED_API_PATTERN = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(api/[A-Za-z0-9_./:{}-]+)",
    re.IGNORECASE,
)
ENTITY_FIELD_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*)[.]([A-Za-z][A-Za-z0-9_]*)\b"
)


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def deterministic_id(prefix: str, value) -> str:
    return f"{prefix}-{fingerprint(value)[:32]}"


def normalize_external_id(prefix: str, value: str) -> str:
    canonical_prefix = "FEATURE" if prefix.upper() in {"FEAT", "FEATURE"} else prefix.upper()
    suffix = value.upper()
    if suffix.isdigit():
        suffix = suffix.zfill(3)
    return f"{canonical_prefix}-{suffix}"


def external_ids(text: str):
    return [
        (normalize_external_id(match.group(1), match.group(2)), match.start(), match.end())
        for match in ID_PATTERN.finditer(text)
    ]


def normalize_api_path(path: str) -> str:
    value = path.strip().rstrip(".,;)")
    value = re.sub(r"/:([A-Za-z_][A-Za-z0-9_]*)", r"/{\1}", value)
    value = re.sub(r"/\{[^}/]+\}", "/{}", value)
    value = re.sub(r"/+", "/", value)
    return value.casefold()


def api_operations(text: str):
    return [
        (match.group(1).upper(), normalize_api_path(match.group(2)), match.start(), match.end())
        for match in API_PATTERN.finditer(text)
    ]


def normalize_identifier(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def lexical_tokens(value: str) -> tuple[str, ...]:
    return tuple(sorted({
        token for token in re.findall(r"[a-z0-9]+", normalize_identifier(value))
        if len(token) > 1 and token not in STOPWORDS
    }))


def lexical_jaccard(left: str, right: str) -> tuple[float, list[str]]:
    left_tokens, right_tokens = set(lexical_tokens(left)), set(lexical_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0, []
    shared = sorted(left_tokens & right_tokens)
    return len(shared) / len(left_tokens | right_tokens), shared


def canonical_feature_name(value: str) -> str:
    approved_forms = {
        "cancellation": "cancel", "cancelled": "cancel", "cancels": "cancel",
        "creation": "create", "created": "create", "creates": "create",
    }
    return " ".join(sorted(approved_forms.get(token, token) for token in lexical_tokens(value)))
