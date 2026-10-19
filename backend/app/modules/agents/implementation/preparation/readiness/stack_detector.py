import re
from dataclasses import dataclass
from typing import Any

from app.modules.agents.implementation.preparation.readiness.schemas import NormalizedArtifact


KEY_ALIASES = {
    "frontend": "frontend",
    "frontend_framework": "frontend",
    "styling": "styling",
    "css_framework": "styling",
    "backend": "backend",
    "backend_framework": "backend",
    "database": "database",
    "language": "language",
    "api": "api_style",
    "api_style": "api_style",
}

SUPPORTED_MARKERS = {
    "frontend": (("react.js", "react", "vite"), "SUPPORTED_FRONTEND"),
    "styling": (("plain css", "vanilla css", "css"), "SUPPORTED_STYLING"),
    "backend": (("express.js", "express", "node.js", "node"), "SUPPORTED_BACKEND"),
    "database": (("mysql",), "SUPPORTED_DATABASE"),
    "language": (("javascript", "js"), "SUPPORTED_LANGUAGE"),
    "api_style": (("restful", "rest api", "rest"), "SUPPORTED_API"),
}

UNSUPPORTED_MARKERS = {
    "frontend": ("angular", "vue", "next.js", "nextjs", "svelte"),
    "styling": ("tailwind css", "tailwind", "bootstrap", "sass", "scss"),
    "backend": (
        "fastapi", "django", "flask", "spring boot", "asp.net", "nestjs"
    ),
    "database": (
        "mongodb", "postgresql", "postgres", "sqlite", "sql server", "oracle"
    ),
    "language": ("python", "typescript", "java", "c#", "php", "golang", "go"),
    "api_style": ("graphql", "grpc"),
}

DECLARATION_PATTERN = re.compile(
    r"^\s*(frontend(?:[_ ]framework)?|styling|css[_ ]framework|"
    r"backend(?:[_ ]framework)?|database|language|api(?:[_ ]style)?)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
NEGATED_PATTERN = re.compile(r"^\s*(?:do\s+not|don't|not|avoid|without)\b", re.I)


@dataclass(frozen=True)
class StackDeclaration:
    category: str
    provided_value: str
    canonical_value: str | None
    supported: bool | None
    artifact: NormalizedArtifact


def _category(value: str) -> str | None:
    normalized = re.sub(r"[ ]+", "_", value.strip().lower())
    return KEY_ALIASES.get(normalized)


def _contains_marker(value: str, marker: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(marker)}(?![A-Za-z0-9])",
        value,
        flags=re.IGNORECASE,
    ) is not None


def _classify(category: str, value: str) -> tuple[str | None, bool | None]:
    if NEGATED_PATTERN.match(value):
        return None, None
    lowered = value.strip().lower()
    for marker in UNSUPPORTED_MARKERS[category]:
        if _contains_marker(lowered, marker):
            return marker.upper(), False
    supported_markers, supported_canonical = SUPPORTED_MARKERS[category]
    if any(_contains_marker(lowered, marker) for marker in supported_markers):
        return supported_canonical, True
    return None, None


def classify_stack_value(category: str, value: str) -> tuple[str | None, bool | None]:
    """Apply the legacy PP1 stack semantics to an authoritative trusted value."""
    return _classify(category, value)


def _structured_declarations(value: Any, artifact: NormalizedArtifact):
    if not isinstance(value, dict):
        return
    for key, candidate in value.items():
        category = _category(str(key))
        if category and isinstance(candidate, (str, int, float)):
            provided = str(candidate).strip()
            if not provided or len(provided) > 200:
                continue
            canonical, supported = _classify(category, provided)
            yield StackDeclaration(
                category, provided, canonical, supported, artifact
            )
        if isinstance(candidate, dict):
            yield from _structured_declarations(candidate, artifact)


def detect_stack(artifacts: list[NormalizedArtifact]) -> list[StackDeclaration]:
    declarations: list[StackDeclaration] = []
    for artifact in artifacts:
        if artifact.structured_content is not None:
            declarations.extend(
                _structured_declarations(artifact.structured_content, artifact)
            )
            continue
        for line in artifact.text_content.splitlines():
            match = DECLARATION_PATTERN.match(line)
            if not match:
                continue
            category = _category(match.group(1))
            if category is None:
                continue
            provided = match.group(2).strip()
            if not provided or len(provided) > 200:
                continue
            canonical, supported = _classify(category, provided)
            declarations.append(
                StackDeclaration(
                    category, provided, canonical, supported, artifact
                )
            )
    return declarations
