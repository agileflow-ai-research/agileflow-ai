"""
Versioned N4.3 technology catalog (TC1). Explicit-text patterns only.

Every pattern must appear in the target system's own text. The catalog does not
hold host-stack defaults and does not assume a framework from a file name alone.
Patterns that are common English words (for example "express", "vue", "yarn")
set requires_technical_context so they match only inside technical context.
"""

from dataclasses import dataclass
from types import MappingProxyType

from .constants import TechnicalEvidenceCategory as C


@dataclass(frozen=True, slots=True)
class TechnologyPattern:
    """One catalog entry: the canonical value, the regex, and whether technical context is required."""

    value: str
    pattern: str
    requires_technical_context: bool = False


_PATTERNS = {
    C.PROGRAMMING_LANGUAGE: (
        TechnologyPattern("PYTHON", r"\bpython\b", True),
        TechnologyPattern("JAVA", r"\bjava\b", True),
        TechnologyPattern("JAVASCRIPT", r"\bjavascript\b", True),
        TechnologyPattern("TYPESCRIPT", r"\btypescript\b", True),
        TechnologyPattern("C_SHARP", r"(?<![A-Za-z0-9])(?:c#|c\s+sharp)(?![A-Za-z0-9])", True),
        TechnologyPattern("GO", r"\b(?:golang|go\s+language)\b", False),
    ),
    C.TEST_FRAMEWORK: (
        TechnologyPattern("PYTEST", r"\bpytest\b"),
        TechnologyPattern("JUNIT", r"\bjunit(?:\s*5)?\b"),
        TechnologyPattern("JEST", r"\bjest\b"),
        TechnologyPattern("VITEST", r"\bvitest\b"),
        TechnologyPattern("PLAYWRIGHT", r"\bplaywright\b"),
        TechnologyPattern("CYPRESS", r"\bcypress\b"),
        TechnologyPattern("SELENIUM", r"\bselenium\b"),
        TechnologyPattern("REST_ASSURED", r"\brest[ -]assured\b"),
        TechnologyPattern("SUPERTEST", r"\bsupertest\b"),
        TechnologyPattern("CUCUMBER", r"\bcucumber\b"),
        TechnologyPattern("OWASP_ZAP", r"\bowasp\s+zap\b"),
    ),
    C.BACKEND_FRAMEWORK: (
        TechnologyPattern("FASTAPI", r"\bfastapi\b"),
        TechnologyPattern("SPRING_BOOT", r"\bspring\s+boot\b"),
        TechnologyPattern("EXPRESS", r"\bexpress(?:\.js|js)?\b", True),
        TechnologyPattern("NESTJS", r"\bnestjs\b"),
        TechnologyPattern("ASP_NET_CORE", r"\basp\.net\s+core\b"),
    ),
    C.FRONTEND_FRAMEWORK: (
        TechnologyPattern("REACT", r"\breact(?:\.js|js)?\b", True),
        TechnologyPattern("ANGULAR", r"\bangular\b"),
        TechnologyPattern("VUE", r"\bvue(?:\.js|js)?\b", True),
        TechnologyPattern("NEXTJS", r"\bnext(?:\.js|js)\b"),
    ),
    C.PACKAGE_ECOSYSTEM: (
        TechnologyPattern("NPM", r"\bnpm\b"),
        TechnologyPattern("PNPM", r"\bpnpm\b"),
        TechnologyPattern("YARN", r"\byarn\b", True),
        TechnologyPattern("MAVEN", r"\bmaven\b"),
        TechnologyPattern("GRADLE", r"\bgradle\b"),
        TechnologyPattern("PIP", r"\bpip\b", True),
        TechnologyPattern("POETRY", r"\bpoetry\b", True),
    ),
    C.DEPENDENCY_MANIFEST_TYPE: (
        TechnologyPattern("PACKAGE_JSON", r"\bpackage\.json\b"),
        TechnologyPattern("POM_XML", r"\bpom\.xml\b"),
        TechnologyPattern("BUILD_GRADLE", r"\bbuild\.gradle(?:\.kts)?\b"),
        TechnologyPattern("REQUIREMENTS_TXT", r"\brequirements\.txt\b"),
        TechnologyPattern("PYPROJECT_TOML", r"\bpyproject\.toml\b"),
    ),
    C.BUILD_TOOL: (
        TechnologyPattern("VITE", r"\bvite\b", True),
        TechnologyPattern("MAVEN", r"\bmaven\b"),
        TechnologyPattern("GRADLE", r"\bgradle\b"),
    ),
    C.DATABASE_TECHNOLOGY: (
        TechnologyPattern("POSTGRESQL", r"\b(?:postgresql|postgres)\b"),
        TechnologyPattern("MYSQL", r"\bmysql\b"),
        TechnologyPattern("MONGODB", r"\bmongodb\b"),
        TechnologyPattern("SQLITE", r"\bsqlite\b"),
    ),
    C.CONTAINER_CONTEXT: (
        TechnologyPattern("DOCKER", r"\bdocker(?:file)?\b"),
        TechnologyPattern("DOCKER_COMPOSE", r"\bdocker[ -]compose\b"),
        TechnologyPattern("KUBERNETES", r"\bkubernetes\b"),
    ),
}

TECHNOLOGY_PATTERNS = MappingProxyType(_PATTERNS)

# A framework is compatible only with the languages listed here. Engine
# _select_toolchain() rejects any explicit pair that is not in this map, so an
# unsupported toolchain cannot be marked EXECUTABLE_POSSIBLE.
FRAMEWORK_LANGUAGES = MappingProxyType({
    "PYTEST": frozenset({"PYTHON"}),
    "JUNIT": frozenset({"JAVA"}),
    "REST_ASSURED": frozenset({"JAVA"}),
    "JEST": frozenset({"JAVASCRIPT", "TYPESCRIPT"}),
    "VITEST": frozenset({"JAVASCRIPT", "TYPESCRIPT"}),
    "PLAYWRIGHT": frozenset({"JAVASCRIPT", "TYPESCRIPT", "PYTHON", "JAVA", "C_SHARP"}),
    "CYPRESS": frozenset({"JAVASCRIPT", "TYPESCRIPT"}),
    "SELENIUM": frozenset({"PYTHON", "JAVA", "JAVASCRIPT", "TYPESCRIPT", "C_SHARP"}),
    "SUPERTEST": frozenset({"JAVASCRIPT", "TYPESCRIPT"}),
    "CUCUMBER": frozenset({"JAVA", "JAVASCRIPT", "TYPESCRIPT"}),
    "OWASP_ZAP": frozenset({"PYTHON", "JAVA", "JAVASCRIPT", "TYPESCRIPT", "C_SHARP"}),
})

UI_FRAMEWORKS = frozenset({"PLAYWRIGHT", "CYPRESS", "SELENIUM"})
API_FRAMEWORKS = frozenset({
    "PYTEST", "JUNIT", "JEST", "VITEST", "REST_ASSURED", "SUPERTEST",
    "PLAYWRIGHT", "SELENIUM",
})
UNIT_FRAMEWORKS = frozenset({"PYTEST", "JUNIT", "JEST", "VITEST"})
SECURITY_FRAMEWORKS = frozenset({"PYTEST", "JUNIT", "OWASP_ZAP"})

TECHNICAL_CONTEXT_PATTERN = (
    r"\b(?:language|stack|runtime|backend|frontend|framework|service|application|"
    r"implemented|implementation|built|codebase|tests?|testing|tooling|dependency|"
    r"package|project)\b"
)
NEGATED_TECHNOLOGY_PATTERN = r"\b(?:no|not|without|avoid|exclude|unsupported)\b"
