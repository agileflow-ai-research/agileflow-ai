import re
from dataclasses import dataclass

from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
    RuleEvidenceSource,
)


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    label: ArtifactDetectionLabel
    pattern: re.Pattern[str]
    weight: float
    source: RuleEvidenceSource = RuleEvidenceSource.TEXT
    suppress_when_negated: bool = False


def rule(rule_id: str, label: ArtifactDetectionLabel, pattern: str, weight: float,
         *, source: RuleEvidenceSource = RuleEvidenceSource.TEXT,
         suppress_when_negated: bool = False) -> RuleDefinition:
    return RuleDefinition(
        rule_id, label, re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL),
        weight, source, suppress_when_negated,
    )


L = ArtifactDetectionLabel
S = RuleEvidenceSource

# Rules favor exact identifiers, declarations, and structural phrases. Generic
# domain words intentionally have no rule or remain below the emission threshold.
RULES: tuple[RuleDefinition, ...] = (
    rule("FR_IDENTIFIER", L.FUNCTIONAL_REQUIREMENTS, r"\bFR-?\d{1,6}\b", .90),
    rule("FR_HEADING", L.FUNCTIONAL_REQUIREMENTS, r"^functional requirements?$", .85, source=S.HEADING),
    rule("FR_SYSTEM_SHALL", L.FUNCTIONAL_REQUIREMENTS, r"\b(?:the system|the user|users)\s+(?:shall|must)\b", .82),
    rule("FR_ABILITY", L.FUNCTIONAL_REQUIREMENTS, r"\busers?\s+shall\s+be\s+able\s+to\b", .88),
    rule("FR_ALLOW_DECLARATION", L.FUNCTIONAL_REQUIREMENTS, r"\b(?:must|should)\s+allow\b|\bshall\s+provide\b", .60),

    rule("NFR_IDENTIFIER", L.NON_FUNCTIONAL_REQUIREMENTS, r"\bNFR-?\d{1,6}\b", .92),
    rule("NFR_HEADING", L.NON_FUNCTIONAL_REQUIREMENTS, r"^non[- ]?functional requirements?$", .88, source=S.HEADING),
    rule("NFR_MEASURABLE", L.NON_FUNCTIONAL_REQUIREMENTS,
         r"\b(?:response time|latency|availability|uptime|throughput|concurrent users?)\b.{0,70}\b(?:shall|must|at least|at most|below|under|over|\d+(?:\.\d+)?\s*(?:ms|seconds?|%|requests?/?s|users?))\b", .88),
    rule("NFR_STANDARD_REQUIREMENT", L.NON_FUNCTIONAL_REQUIREMENTS,
         r"\b(?:encryption|accessibility|performance)\s+(?:standard|requirement)\b", .78),

    rule("USER_STORY_TEMPLATE", L.USER_STORIES,
         r"\bas an?\s+[^\n,.]{2,80},?\s+i want\s+.{2,180}?\s+so that\s+[^\n]{2,180}", .96),
    rule("USER_STORY_IDENTIFIER", L.USER_STORIES, r"\bUS-?\d{1,6}\b", .88),
    rule("USER_STORY_HEADING", L.USER_STORIES, r"^user stor(?:y|ies)(?:\s*:\s*.*)?$", .84, source=S.HEADING),

    rule("AC_IDENTIFIER", L.ACCEPTANCE_CRITERIA, r"\bAC-?\d{1,6}\b", .90),
    rule("AC_HEADING", L.ACCEPTANCE_CRITERIA, r"^acceptance criteria(?:\s*:\s*.*)?$", .88, source=S.HEADING),
    rule("AC_GIVEN_WHEN_THEN", L.ACCEPTANCE_CRITERIA,
         r"\bgiven\b.{0,300}\bwhen\b.{0,300}\bthen\b", .94),
    rule("AC_EXPECTED_RESULT", L.ACCEPTANCE_CRITERIA, r"\bexpected result\s*:", .45),
    rule("AC_PASS_CRITERIA", L.ACCEPTANCE_CRITERIA, r"\b(?:pass criteria|success condition)\s*:", .48),

    rule("API_HTTP_METHOD_PATH", L.API_SPECIFICATION,
         r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/(?:[A-Za-z0-9._~!$&'()*+,;=:@%{}\[\]/-]*)", .96),
    rule("API_HEADING", L.API_SPECIFICATION, r"^(?:api specification|api endpoints?|endpoint specification)$", .90, source=S.HEADING),
    rule("API_ENDPOINT_DECLARATION", L.API_SPECIFICATION, r"\bendpoint\s*:\s*/[^\s]+", .65),
    rule("API_REQUEST_DECLARATION", L.API_SPECIFICATION, r"\brequest\s*:", .28),
    rule("API_RESPONSE_DECLARATION", L.API_SPECIFICATION, r"\bresponse\s*:", .28),
    rule("API_HTTP_STATUS", L.API_SPECIFICATION, r"\bHTTP\s+(?:200|201|204|400|401|403|404|409|422|500)\b", .38),

    rule("DB_CREATE_TABLE", L.DATABASE_SCHEMA, r"\bCREATE\s+TABLE\b", .95),
    rule("DB_PRIMARY_KEY", L.DATABASE_SCHEMA, r"\bPRIMARY\s+KEY\b", .60),
    rule("DB_FOREIGN_KEY", L.DATABASE_SCHEMA, r"\b(?:FOREIGN\s+KEY|REFERENCES\s+[A-Za-z_])", .60),
    rule("DB_SCHEMA_TABLE", L.DATABASE_SCHEMA, r"\bColumn\s*\|\s*Type\s*\|\s*Constraint\b|\bTable\s*\|\s*Field\s*\|\s*Data Type\b", .90),
    rule("DB_REPEATED_COLUMN_TYPES", L.DATABASE_SCHEMA,
         r"\b(?:VARCHAR\(\d+\)|INT|BIGINT|BOOLEAN|TIMESTAMP)\b.{0,120}\b(?:VARCHAR\(\d+\)|INT|BIGINT|BOOLEAN|TIMESTAMP)\b", .72),
    rule("DB_STRUCTURED_PATH", L.DATABASE_SCHEMA, r"(?:^|\.)(?:tables|columns|foreign_keys|primary_key)(?:\.|\[|$)", .92, source=S.STRUCTURED_PATH),

    rule("ARCH_HEADING", L.SYSTEM_ARCHITECTURE, r"^(?:system architecture|architecture overview|component diagram)$", .92, source=S.HEADING),
    rule("ARCH_COMPONENT_FLOW", L.SYSTEM_ARCHITECTURE, r"\bclient\s*(?:->|→)\s*api\s*(?:->|→)\s*database\b", .94),
    rule("ARCH_THREE_TIERS", L.SYSTEM_ARCHITECTURE, r"\bfrontend\b.{0,100}\bbackend\b.{0,100}\bdatabase\b", .84),
    rule("ARCH_LAYER_PAIR", L.SYSTEM_ARCHITECTURE, r"\b(?:presentation|service|data) layer\b.{0,100}\b(?:presentation|service|data) layer\b", .78),
    rule("ARCH_STYLE", L.SYSTEM_ARCHITECTURE, r"\b(?:microservice architecture|monolithic architecture|layered architecture)\b", .82),

    rule("UI_FLOW_HEADING", L.UI_FLOW, r"^(?:ui flow|user flow|screen flow|navigation flow)$", .92, source=S.HEADING),
    rule("UI_SCREEN_ARROW_FLOW", L.UI_FLOW,
         r"\b(?:login|home|screen|dashboard|slots?|booking form)\b\s*(?:->|→)\s*[^\n]{1,100}(?:->|→)\s*[^\n]{1,100}", .90),
    rule("UI_SCREEN_DECLARATION", L.UI_FLOW, r"\b(?:next screen|navigate to|screen)\s*:", .58),

    rule("STACK_HEADING", L.TECHNOLOGY_STACK, r"^technology stack$", .94, source=S.HEADING),
    rule("STACK_DECLARATION", L.TECHNOLOGY_STACK,
         r"^(?:frontend|backend|database|language|framework|styling|api style)\s*:\s*[^\n]+$", .48, suppress_when_negated=True),
    rule("STACK_STRUCTURED_PATH", L.TECHNOLOGY_STACK,
         r"(?:^|\.)(?:technology_stack|tech_stack|frontend|backend|framework|language|styling|api_style)(?:\.|\[|$)", .86, source=S.STRUCTURED_PATH),

    rule("CONSTRAINT_HEADING", L.TECHNICAL_CONSTRAINTS,
         r"^(?:technical constraints|implementation constraints|constraints)$", .92, source=S.HEADING),
    rule("CONSTRAINT_MUST_USE", L.TECHNICAL_CONSTRAINTS, r"\b(?:must|do)\s+(?:not\s+)?use\b", .88),
    rule("CONSTRAINT_EXPLICIT", L.TECHNICAL_CONSTRAINTS,
         r"\b(?:required framework|only supported on|deployment constraint|browser support|runtime version)\b", .82),

    rule("TASK_IDENTIFIER", L.IMPLEMENTATION_TASKS, r"\bTASK-?\d{1,6}\b", .92),
    rule("TASK_HEADING", L.IMPLEMENTATION_TASKS, r"^(?:implementation tasks|development tasks)$", .90, source=S.HEADING),
    rule("TASK_TODO", L.IMPLEMENTATION_TASKS, r"\bTODO\s*:", .84),
    rule("TASK_DECLARATION", L.IMPLEMENTATION_TASKS, r"\bTask\s*:\s*(?:create|implement|add|configure|build|update)\b", .82),
    rule("TASK_REPEATED_IMPERATIVES", L.IMPLEMENTATION_TASKS,
         r"(?:^[-*]\s+(?:create|implement|add|configure|build|update)\b[^\n]*\n?){2,}", .82),

    rule("TEST_IDENTIFIER", L.TEST_CASES, r"\b(?:TC|API-T|UNIT-T)-?\d{1,6}\b", .94),
    rule("TEST_HEADING", L.TEST_CASES, r"^(?:test cases?|test steps)$", .90, source=S.HEADING),
    rule("TEST_GWT_CONTEXT", L.TEST_CASES, r"\btest(?: case| scenario)?\b.{0,150}\bgiven\b.{0,250}\bwhen\b.{0,250}\bthen\b", .90),
    rule("TEST_EXPECTED_ACTUAL", L.TEST_CASES, r"\bexpected result\s*:.{0,250}\bactual result\s*:", .84),
    rule("TEST_STEPS", L.TEST_CASES, r"\btest steps\s*:", .78),
    rule("TEST_STRUCTURED_PATH", L.TEST_CASES,
         r"(?:^|\.)(?:tests|test_cases|api_tests|acceptance_tests)(?:\.|\[|$)", .94, source=S.STRUCTURED_PATH),
)
