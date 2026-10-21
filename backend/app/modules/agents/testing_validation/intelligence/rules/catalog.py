"""Immutable precision-first R1 rule catalog."""

import hashlib
import json
from dataclasses import asdict, dataclass

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    TestingIntelligenceLabel,
)


AGENT4_RULES_VERSION = "R1"


@dataclass(frozen=True, slots=True)
class TestingRuleDefinition:
    rule_id: str
    label: TestingIntelligenceLabel
    description: str
    pattern: str
    artifact_types: tuple[TestGenerationInputArtifactType, ...] = ()


def _rule(rule_id, label, description, pattern, *, artifacts=()):
    return TestingRuleDefinition(rule_id, label, description, pattern, tuple(artifacts))


L = TestingIntelligenceLabel
A = TestGenerationInputArtifactType

# Ordering is a versioned part of the research baseline. Patterns match only
# original chunk text; artifact constraints narrow a match but never create one.
TESTING_RULE_CATALOG: tuple[TestingRuleDefinition, ...] = (
    _rule("A4R-FUNC-001", L.FUNCTIONAL_BEHAVIOR, "Explicit system behavior", r"\b(?:the system|the application)\s+(?:shall|must|will)\s+[a-z][^\n.!?]{1,180}"),
    _rule("A4R-FUNC-002", L.FUNCTIONAL_BEHAVIOR, "Observable user capability", r"\b(?:the user|users?|customers?)\s+(?:can|shall be able to|must be able to)\s+[a-z][^\n.!?]{1,160}"),
    _rule("A4R-FUNC-003", L.FUNCTIONAL_BEHAVIOR, "Triggered system behavior", r"\bwhen\s+[^\n.!?]{2,100},\s*(?:the system|the application)\s+(?:shall|must|will)\s+[^\n.!?]{1,140}"),
    _rule("A4R-VALID-001", L.INPUT_VALIDATION, "Required or mandatory input", r"\b(?:field|input|value|parameter)\s+(?:is|required|must be)\s+(?:required|mandatory)\b|\brequired\s+(?:field|input|value|parameter)\b"),
    _rule("A4R-VALID-002", L.INPUT_VALIDATION, "Explicit input format", r"\b(?:email|input|field|value|parameter)\s+must\s+(?:be a valid|match(?:es)?(?: the)? (?:format|pattern))\b"),
    _rule("A4R-VALID-003", L.INPUT_VALIDATION, "Empty or invalid input rejection", r"\b(?:must not be empty|invalid (?:input|value|format) (?:is|must be|shall be) rejected|allowed values? (?:are|include))\b"),
    _rule("A4R-BOUND-001", L.BOUNDARY_CONSTRAINT, "Explicit lower or upper bound", r"\b(?:at least|at most|minimum(?: of)?|maximum(?: of)?|no more than|no fewer than|greater than|less than)\s+\d+(?:\.\d+)?(?:\s+(?!m(?:illi)?s\b|seconds?\b)[a-z]+)?"),
    _rule("A4R-BOUND-002", L.BOUNDARY_CONSTRAINT, "Explicit range", r"\bbetween\s+\d+(?:\.\d+)?\s+and\s+\d+(?:\.\d+)?\b|\brange\s+(?:of\s+)?\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\b"),
    _rule("A4R-BOUND-003", L.BOUNDARY_CONSTRAINT, "Explicit length constraint", r"\b(?:length (?:is|must be|shall be)|exactly)\s+\d+\s+(?:characters?|digits?|items?)\b|\b(?:minimum|maximum) length\s+(?:of\s+)?\d+\b"),
    _rule("A4R-DATA-001", L.DATA_INTEGRITY, "Uniqueness constraint", r"\b(?:must be unique|unique constraint|prevent duplicate|duplicate records? (?:must|shall) not)\b"),
    _rule("A4R-DATA-002", L.DATA_INTEGRITY, "Referential consistency", r"\b(?:referential integrity|foreign key (?:constraint|consistency)|no orphan(?:ed)? records?|data consistency)\b"),
    _rule("A4R-DATA-003", L.DATA_INTEGRITY, "Atomic transaction", r"\b(?:atomic transaction|transactional(?:ly)? (?:save|persist|update)|rollback (?:the )?transaction)\b"),
    _rule("A4R-API-001", L.API_CONTRACT, "HTTP method and endpoint", r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/(?:api/)?[A-Za-z0-9][A-Za-z0-9._~!$&'()*+,;=:@%{}\[\]/-]*"),
    _rule("A4R-API-002", L.API_CONTRACT, "HTTP response status", r"\b(?:return|respond with)\s+HTTP\s+(?:200|201|202|204|400|401|403|404|409|422|429|500|502|503)\b|\b(?:HTTP\s+)?(?:200|201|202|204|400|401|403|404|409|422|429|500|502|503)\s+(?:status|response|response code)\b|\bstatus code\s+(?:200|201|202|204|400|401|403|404|409|422|429|500|502|503)\b"),
    _rule("A4R-API-003", L.API_CONTRACT, "Request or response schema", r"\b(?:request|response)\s+(?:body|schema)\b|\b(?:request|response)\s+header\b", artifacts=(A.API_SPECIFICATION, A.FUNCTIONAL_REQUIREMENTS, A.SRS)),
    _rule("A4R-UI-001", L.UI_WORKFLOW, "Explicit UI action", r"\b(?:click|tap|select)\s+(?:the\s+)?[^\n.!?]{1,50}\s+(?:button|option|link)\b"),
    _rule("A4R-UI-002", L.UI_WORKFLOW, "Explicit navigation", r"\b(?:navigate|redirect(?:ed)?|return)\s+to\s+(?:the\s+)?[^\n.!?]{1,60}\s+(?:screen|page|dashboard|form)\b|\b(?:modal|dialog)\s+(?:opens|appears|is displayed)\b"),
    _rule("A4R-AUTHN-001", L.AUTHENTICATION, "Login or credential verification", r"\b(?:log in|login|sign in)\s+(?:with|using|requires?)\s+[^\n.!?]{1,80}|\b(?:password|credential) authentication\b"),
    _rule("A4R-AUTHN-002", L.AUTHENTICATION, "Multi-factor verification", r"\b(?:multi-factor authentication|two-factor authentication|MFA|2FA|one-time password|OTP)\b"),
    _rule("A4R-AUTHN-003", L.AUTHENTICATION, "Session or token authentication", r"\b(?:session|access token|bearer token) authentication\b|\bidentity verification\b"),
    _rule("A4R-AUTHZ-001", L.AUTHORIZATION, "Role restriction", r"\bonly\s+(?:administrators?|admins?|managers?|authorized users?)\s+(?:may|can|shall)\b|\baccess (?:is )?restricted to\s+[^\n.!?]{1,80}"),
    _rule("A4R-AUTHZ-002", L.AUTHORIZATION, "Permission requirement", r"\b(?:requires?|must have)\s+(?:the\s+)?(?:permission|role)\s+[^\n.!?]{1,80}|\brole-based access\b"),
    _rule("A4R-AUTHZ-003", L.AUTHORIZATION, "Ownership restriction", r"\b(?:owner|record owner|resource owner)\s+(?:may|can|must)\s+[^\n.!?]{1,100}|\bonly (?:the )?owner\s+(?:may|can)\b"),
    _rule("A4R-SEC-001", L.SECURITY_CONTROL, "Encryption transport or storage", r"\b(?:encrypt(?:ed|ion)? (?:at rest|in transit)|TLS\s*1\.[23]|HTTPS only|secure cookie)\b"),
    _rule("A4R-SEC-002", L.SECURITY_CONTROL, "Application security control", r"\b(?:CSRF protection|XSS prevention|security headers?|content security policy)\b"),
    _rule("A4R-SEC-003", L.SECURITY_CONTROL, "Abuse or lockout control", r"\b(?:rate limit(?:ing|ed)?|account lockout|lock(?:ed)? (?:the )?account after\s+\d+\s+(?:failed )?(?:login )?attempts?)\b"),
    _rule("A4R-PERF-001", L.PERFORMANCE_SLO, "Response-time objective", r"\b(?:response time|latency|request)\s+(?:shall|must|should|is required to)?\s*(?:be|complete|respond)?\s*(?:within|under|below|at most|less than)\s+\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?)\b"),
    _rule("A4R-PERF-002", L.PERFORMANCE_SLO, "Throughput objective", r"\b(?:throughput|process|support)\s+(?:of\s+|at least\s+|up to\s+)?\d+(?:\.\d+)?\s+(?:requests?|transactions?)\s*(?:per second|/s|per minute)\b"),
    _rule("A4R-PERF-003", L.PERFORMANCE_SLO, "Concurrent capacity", r"\b(?:support|handle)\s+(?:at least\s+|up to\s+)?\d+\s+concurrent users?\b"),
    _rule("A4R-REL-001", L.RELIABILITY_RECOVERY, "Availability objective", r"\b(?:availability|uptime)\s+(?:of\s+|must be\s+|shall be\s+)?\d+(?:\.\d+)?%\b"),
    _rule("A4R-REL-002", L.RELIABILITY_RECOVERY, "Retry or failover behavior", r"\b(?:automatically retry|retry (?:the )?(?:request|operation)|failover to|graceful degradation)\b"),
    _rule("A4R-REL-003", L.RELIABILITY_RECOVERY, "Recovery behavior", r"\b(?:recover|restore)\s+(?:service|data|operation)\s+(?:after|from|within)\b|\bbackup recovery\b"),
    _rule("A4R-ERROR-001", L.ERROR_HANDLING, "Required error response", r"\b(?:return|respond with|display|show)\s+(?:an?\s+)?(?:error|failure|validation)\s+(?:message|response|code)\b"),
    _rule("A4R-ERROR-002", L.ERROR_HANDLING, "Required rejection", r"\b(?:invalid|unauthorized|forbidden)\s+(?:operation|request|input)\s+(?:is|must be|shall be)\s+rejected\b"),
    _rule("A4R-ERROR-003", L.ERROR_HANDLING, "HTTP failure response", r"\b(?:return|respond with)\s+(?:HTTP\s+)?(?:400|401|403|404|409|422|429|500|503)\b"),
    _rule("A4R-ACCEPT-001", L.ACCEPTANCE_CONDITION, "Given When Then scenario", r"\bGiven\b[^\n]{1,300}\bWhen\b[^\n]{1,300}\bThen\b[^\n]{1,300}"),
    _rule("A4R-ACCEPT-002", L.ACCEPTANCE_CONDITION, "Explicit acceptance condition", r"\b(?:feature is accepted|considered complete|acceptance criteria)\s+(?:when|if|:)\s*[^\n.!?]{1,180}"),
    _rule("A4R-ACCEPT-003", L.ACCEPTANCE_CONDITION, "Named scenario", r"^Scenario:\s*[^\n]{2,180}", artifacts=(A.ACCEPTANCE_CRITERIA, A.USER_STORIES, A.SRS)),
    _rule("A4R-STATE-001", L.STATE_PERSISTENCE, "Required persisted state", r"\b(?:save|store|persist|retain)\s+(?:the\s+)?(?:record|value|state|data|changes)\b"),
    _rule("A4R-STATE-002", L.STATE_PERSISTENCE, "State survives restart", r"\b(?:state|data|record)\s+(?:must|shall)\s+(?:survive|persist across)\s+(?:a\s+)?restart\b"),
    _rule("A4R-STATE-003", L.STATE_PERSISTENCE, "Stored update or deletion", r"\b(?:update|delete)\s+(?:the\s+)?(?:stored|persisted|database)\s+(?:record|value|state|data)\b"),
)


def rule_catalog_fingerprint(
    rules: tuple[TestingRuleDefinition, ...] = TESTING_RULE_CATALOG,
) -> str:
    payload = {
        "taxonomy_version": AGENT4_TESTING_TAXONOMY_VERSION,
        "rules_version": AGENT4_RULES_VERSION,
        "rules": [
            {
                **asdict(rule),
                "label": rule.label.value,
                "artifact_types": [item.value for item in rule.artifact_types],
            }
            for rule in rules
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


AGENT4_RULE_CATALOG_FINGERPRINT = rule_catalog_fingerprint()

