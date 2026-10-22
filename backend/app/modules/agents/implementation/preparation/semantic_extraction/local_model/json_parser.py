import json
import re


class SemanticModelJsonError(ValueError):
    pass


_JSON_FENCE = re.compile(r"\A```json\s*\n(?P<body>\{.*\})\s*\n```\Z", re.S)


def parse_single_json_object(output: str) -> dict:
    candidate = output.strip()
    fenced = _JSON_FENCE.fullmatch(candidate)
    if fenced:
        candidate = fenced.group("body")
    if not candidate.startswith("{") or not candidate.endswith("}"):
        raise SemanticModelJsonError("MODEL_OUTPUT_MUST_BE_ONE_JSON_OBJECT")
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise SemanticModelJsonError("MODEL_OUTPUT_INVALID_JSON") from exc
    if not isinstance(parsed, dict):
        raise SemanticModelJsonError("MODEL_OUTPUT_MUST_BE_ONE_JSON_OBJECT")
    return parsed
