import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.modules.agents.implementation.infrastructure.digests import (
    stable_json_sha256,
)

from ..schemas import (
    AdherenceCheckStatus,
    AdherenceFindingSeverity,
    CodeAdherenceCheck,
    CodeAdherenceFinding,
    CodeAdherenceReport,
    CodeAdherenceStatus,
    FileContentType,
    FileDependencyContext,
    FileGenerationContext,
    GeneratedCandidateStatus,
    GeneratedContentCandidate,
)


ADHERENCE_POLICY_VERSION = "GEN-R1.3D-1"

_STATIC_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<clause>.+?)\s+from\s+(?P<quote>['\"])(?P<source>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)
_SIDE_EFFECT_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<quote>['\"])(?P<source>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)
_REQUIRE_ASSIGN_RE = re.compile(
    r"^\s*(?:const|let|var)\s+(?P<clause>[^=;]+?)\s*=\s*require\s*\(\s*"
    r"(?P<quote>['\"])(?P<source>[^'\"]+)(?P=quote)\s*\)",
    re.MULTILINE,
)
_BARE_REQUIRE_RE = re.compile(
    r"require\s*\(\s*(?P<quote>['\"])(?P<source>[^'\"]+)(?P=quote)\s*\)"
)
_ROUTE_RE = re.compile(
    r"\b(?P<receiver>router|app)\s*\.\s*"
    r"(?P<method>get|post|put|patch|delete|options|head)\s*\(\s*"
    r"(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_NODE_BUILTINS = frozenset(
    {
        "assert",
        "buffer",
        "crypto",
        "events",
        "fs",
        "http",
        "https",
        "os",
        "path",
        "stream",
        "url",
        "util",
    }
)
_PERSISTENCE_METHODS = frozenset(
    {"save", "findById", "findOne", "find", "create", "updateOne", "deleteOne"}
)


@dataclass(frozen=True)
class _Binding:
    local_name: str
    imported_name: str
    source: str
    line: int
    column: int


@dataclass(frozen=True)
class _ModuleRef:
    source: str
    line: int
    column: int


@dataclass(frozen=True)
class _Route:
    method: str
    path: str
    start: int
    end: int
    line: int
    column: int


class CodeAdherenceValidator:
    """Conservative evidence-backed validation; it never executes generated code."""

    def validate(
        self,
        context: FileGenerationContext,
        candidate: GeneratedContentCandidate,
    ) -> CodeAdherenceReport:
        findings: list[CodeAdherenceFinding] = []
        check_states: dict[str, tuple[AdherenceCheckStatus, str]] = {}
        self._validate_identity(context, candidate, findings)
        identity_findings = tuple(findings)
        check_states["IDENTITY_BINDING"] = _check_state(
            identity_findings,
            "Candidate identity, traceability, and dependency hashes match the "
            "approved file context.",
            "At least one server-owned candidate binding is inconsistent.",
        )
        self._validate_missing_information(candidate, findings, check_states)

        content = candidate.generated_content
        if candidate.validation_status is not GeneratedCandidateStatus.VALIDATED or not content:
            for name in (
                "JAVASCRIPT_PARSER",
                "MODULE_SYSTEM",
                "DEPENDENCIES",
                "INTERFACES",
                "API_CONTRACT",
                "TECHNOLOGY_STACK",
            ):
                check_states[name] = (
                    AdherenceCheckStatus.NOT_CHECKED,
                    "No structurally validated content was available for this check.",
                )
        elif context.content_type is not FileContentType.JAVASCRIPT:
            findings.append(
                self._finding(
                    "ADHERENCE_VALIDATOR_NOT_IMPLEMENTED",
                    AdherenceFindingSeverity.REVIEW_REQUIRED,
                    "Deterministic adherence validation is not implemented for this content type.",
                    "Unsupported content types must receive a dedicated validator "
                    "or human review.",
                    f"The content type is {context.content_type.value}.",
                )
            )
            for name in (
                "JAVASCRIPT_PARSER",
                "MODULE_SYSTEM",
                "DEPENDENCIES",
                "INTERFACES",
                "API_CONTRACT",
                "TECHNOLOGY_STACK",
            ):
                check_states[name] = (
                    AdherenceCheckStatus.NOT_CHECKED,
                    f"No {context.content_type.value} adherence validator is available.",
                )
        else:
            findings.append(
                self._finding(
                    "JAVASCRIPT_PARSER_UNAVAILABLE",
                    AdherenceFindingSeverity.INFORMATIONAL,
                    "No approved JavaScript AST parser is installed.",
                    "Use a non-executing parser for complete syntax-aware analysis.",
                    "Conservative static lexical checks were used instead.",
                )
            )
            check_states["JAVASCRIPT_PARSER"] = (
                AdherenceCheckStatus.NOT_CHECKED,
                "AST parsing was unavailable; this report does not claim syntax completeness.",
            )
            imports, bindings = _parse_imports(content)
            module_system, package_names, package_detail = _package_contract(context)
            module_findings = self._module_system_findings(
                content, module_system, package_detail
            )
            findings.extend(module_findings)
            check_states["MODULE_SYSTEM"] = _check_state(
                module_findings,
                "Generated module syntax is consistent with the validated package contract.",
                "The module convention could not be established conclusively.",
            )

            dependency_findings, matched_dependencies, unverified_bindings = (
                self._dependency_findings(
                    context, imports, bindings, package_names
                )
            )
            findings.extend(dependency_findings)
            check_states["DEPENDENCIES"] = _check_state(
                dependency_findings,
                "All statically identifiable imports are authorized.",
                "At least one module reference could not be verified.",
            )

            interface_findings = self._interface_findings(
                content,
                bindings,
                matched_dependencies,
                unverified_bindings,
            )
            findings.extend(interface_findings)
            check_states["INTERFACES"] = _check_state(
                interface_findings,
                "Statically identifiable imported interfaces are declared by dependencies.",
                "At least one interface could not be established from approved evidence.",
            )

            api_findings = self._api_findings(context, content)
            findings.extend(api_findings)
            check_states["API_CONTRACT"] = _check_state(
                api_findings,
                "Express routes matched the supplied API contracts.",
                "The final route binding could not be established conclusively.",
            )

            stack_findings = self._stack_findings(
                context, imports
            )
            findings.extend(stack_findings)
            check_states["TECHNOLOGY_STACK"] = _check_state(
                stack_findings,
                "No statically identifiable stack conflict was detected.",
                "Some technology usage requires review.",
            )

        findings = sorted(
            findings,
            key=lambda item: (
                item.code,
                item.line or 0,
                item.column or 0,
                item.observed_behavior,
                item.evidence_refs,
            ),
        )
        status = _report_status(findings, content is not None)
        checks = tuple(
            CodeAdherenceCheck(name=name, status=value[0], detail=value[1])
            for name, value in sorted(check_states.items())
        )
        payload = {
            "candidate_file_id": candidate.planned_file_id,
            "generation_plan_id": candidate.generation_plan_id,
            "plan_fingerprint": candidate.plan_fingerprint,
            "validation_policy_version": ADHERENCE_POLICY_VERSION,
            "content_sha256": candidate.content_sha256,
            "approved_context_fingerprint": candidate.source_snapshot_fingerprint,
            "status": status.value,
            "findings": [item.model_dump(mode="json") for item in findings],
            "checks": [item.model_dump(mode="json") for item in checks],
            "writer_eligible": status is CodeAdherenceStatus.PASS,
        }
        return CodeAdherenceReport(
            **payload,
            report_fingerprint=stable_json_sha256(payload),
        )

    def _validate_identity(self, context, candidate, findings):
        if (
            candidate.agent_project_id != context.agent_project_id
            or candidate.run_id != context.run_id
            or candidate.generation_plan_id != context.generation_plan_id
            or candidate.plan_fingerprint != context.plan_fingerprint
            or candidate.source_snapshot_fingerprint
            != context.source_snapshot_fingerprint
            or candidate.planned_file_id != context.planned_file_id
            or candidate.relative_output_path != context.relative_output_path
            or candidate.authorized_output_codes != context.authorized_output_codes
        ):
            findings.append(
                self._finding(
                    "CANDIDATE_CONTEXT_BINDING_MISMATCH",
                    AdherenceFindingSeverity.BLOCKING,
                    "The generated candidate is not bound to the approved file context.",
                    "Project, run, plan, file, path, snapshot, and output bindings "
                    "must match the server-owned context exactly.",
                    "At least one server-owned candidate binding differs.",
                )
            )
        trusted_ids = {
            item.project_item_id for item in context.trusted_specification_items
        }
        candidate_ids = set(candidate.relevant_specification_item_ids)
        for item_id in sorted(candidate_ids - trusted_ids):
            findings.append(
                self._finding(
                    "UNKNOWN_SPECIFICATION_REFERENCE",
                    AdherenceFindingSeverity.BLOCKING,
                    "The candidate references a specification item absent from its "
                    "approved file context.",
                    "Every candidate PSI reference must be supplied by the approved file context.",
                    f"Unknown reference: {item_id}.",
                    evidence_refs=(item_id,),
                )
            )
        for item_id in sorted(trusted_ids - candidate_ids):
            findings.append(
                self._finding(
                    "MISSING_SPECIFICATION_REFERENCE",
                    AdherenceFindingSeverity.BLOCKING,
                    "The candidate dropped an approved file-level specification reference.",
                    "Candidate traceability must retain all file-level approved PSI references.",
                    f"Missing reference: {item_id}.",
                    evidence_refs=(item_id,),
                )
            )
        expected_dependencies = {
            item.planned_file_id: item.content_sha256 for item in context.dependencies
        }
        candidate_dependencies = {
            item.planned_file_id: item.content_sha256
            for item in candidate.dependency_fingerprints
        }
        for dependency_id in sorted(
            set(expected_dependencies) | set(candidate_dependencies)
        ):
            if expected_dependencies.get(dependency_id) != candidate_dependencies.get(
                dependency_id
            ):
                findings.append(
                    self._finding(
                        "DEPENDENCY_FINGERPRINT_MISMATCH",
                        AdherenceFindingSeverity.BLOCKING,
                        "Candidate dependency evidence differs from its approved file context.",
                        "Every validated dependency identity and content hash must be preserved.",
                        f"Dependency binding mismatch: {dependency_id}.",
                        evidence_refs=(dependency_id,),
                    )
                )

    def _validate_missing_information(self, candidate, findings, check_states):
        if candidate.missing_information:
            findings.append(
                self._finding(
                    "MODEL_REPORTED_MISSING_INFORMATION",
                    AdherenceFindingSeverity.BLOCKING,
                    "The model reported mandatory information as missing.",
                    "Writer eligibility requires all mandatory generation facts.",
                    "; ".join(candidate.missing_information)[:500],
                )
            )
            check_states["MISSING_INFORMATION"] = (
                AdherenceCheckStatus.FAILED,
                "The model reported missing mandatory information.",
            )
        else:
            check_states["MISSING_INFORMATION"] = (
                AdherenceCheckStatus.PASSED,
                "The model did not report missing mandatory information.",
            )
        check_states["TRACEABILITY"] = (
            AdherenceCheckStatus.FAILED
            if any(item.code.endswith("SPECIFICATION_REFERENCE") for item in findings)
            else AdherenceCheckStatus.PASSED,
            "Candidate PSI references were compared with the approved file context.",
        )

    def _module_system_findings(self, content, module_system, package_detail):
        findings = []
        if module_system is None:
            return [
                self._finding(
                    "MODULE_SYSTEM_UNRESOLVED",
                    AdherenceFindingSeverity.REVIEW_REQUIRED,
                    "The JavaScript module convention could not be established.",
                    "A validated package.json dependency should establish ESM or CommonJS.",
                    package_detail,
                )
            ]
        conflicts = (
            ((r"\brequire\s*\(", "require(...)"), (r"\bmodule\.exports\b", "module.exports"))
            if module_system == "ESM"
            else ((r"^\s*import\s", "import"), (r"^\s*export\s", "export"))
        )
        for pattern, label in conflicts:
            for match in re.finditer(pattern, content, re.MULTILINE):
                line, column = _location(content, match.start())
                findings.append(
                    self._finding(
                        "MODULE_SYSTEM_MISMATCH",
                        AdherenceFindingSeverity.BLOCKING,
                        "Generated module syntax conflicts with the validated package convention.",
                        f"Use {module_system}-compatible module syntax.",
                        f"Found {label} in a {module_system} project.",
                        line=line,
                        column=column,
                    )
                )
        for pattern in (
            r"\brequire\s*\((?!\s*['\"])",
            r"\bimport\s*\((?!\s*['\"])",
        ):
            for match in re.finditer(pattern, content):
                line, column = _location(content, match.start())
                findings.append(
                    self._finding(
                        "DYNAMIC_MODULE_REFERENCE",
                        AdherenceFindingSeverity.REVIEW_REQUIRED,
                        "A computed module reference cannot be resolved deterministically.",
                        "Module locations should be server-verifiable static string references.",
                        "Generated code uses a non-literal module reference.",
                        line=line,
                        column=column,
                    )
                )
        return findings

    def _dependency_findings(self, context, imports, bindings, package_names):
        findings = []
        matched: dict[tuple[str, int], FileDependencyContext] = {}
        unverified_bindings: set[tuple[str, int]] = set()
        framework_packages = _approved_framework_packages(context)
        dependencies = tuple(context.dependencies)
        for module in imports:
            source = module.source
            if source.startswith(("./", "../")):
                dependency = _resolve_dependency(
                    context.relative_output_path.root, source, dependencies
                )
                if dependency is None:
                    findings.append(
                        self._finding(
                            "UNVERIFIED_MODULE_IMPORT",
                            AdherenceFindingSeverity.BLOCKING,
                            "A relative module import is not an approved planned dependency.",
                            "Relative imports must resolve to a validated dependency candidate.",
                            f"Unverified import: {source}.",
                            line=module.line,
                            column=module.column,
                        )
                    )
                    for binding in bindings:
                        if binding.source == source and binding.line == module.line:
                            unverified_bindings.add((binding.local_name, binding.line))
                else:
                    matched[(source, module.line)] = dependency
            else:
                package = _package_root(source)
                if (
                    package not in package_names
                    and package not in framework_packages
                    and not _is_node_builtin(source)
                ):
                    findings.append(
                        self._finding(
                            "UNAPPROVED_EXTERNAL_DEPENDENCY",
                            AdherenceFindingSeverity.BLOCKING,
                            "An imported external package is not approved by stack or "
                            "package evidence.",
                            "External imports must be declared or explicitly supplied "
                            "by the approved stack.",
                            f"Unapproved package: {package}.",
                            line=module.line,
                            column=module.column,
                        )
                    )
                    for binding in bindings:
                        if binding.source == source and binding.line == module.line:
                            unverified_bindings.add((binding.local_name, binding.line))
        return findings, matched, unverified_bindings

    def _interface_findings(
        self, content, bindings, matched_dependencies, unverified_bindings
    ):
        findings = []
        unresolved_names: set[str] = set()
        for binding in bindings:
            dependency = matched_dependencies.get((binding.source, binding.line))
            verified = False
            if dependency is not None:
                exports = _declared_exports(dependency.validated_content)
                verified = binding.imported_name in exports or "*" in exports
            elif (binding.local_name, binding.line) not in unverified_bindings:
                # Approved external frameworks own their public interface contract.
                verified = True
            if not verified:
                unresolved_names.add(binding.local_name)
                findings.append(
                    self._finding(
                        "UNVERIFIED_IMPORTED_INTERFACE",
                        AdherenceFindingSeverity.BLOCKING,
                        "An imported interface is not established by approved "
                        "dependency evidence.",
                        "Imported names must be exported by a validated dependency "
                        "or approved framework.",
                        f"Unverified interface {binding.local_name!r} from {binding.source!r}.",
                        line=binding.line,
                        column=binding.column,
                    )
                )
        instance_sources = {
            match.group("instance"): match.group("class")
            for match in re.finditer(
                r"\b(?:const|let|var)\s+(?P<instance>[A-Za-z_$][\w$]*)\s*=\s*new\s+"
                r"(?P<class>[A-Za-z_$][\w$]*)\s*\(",
                content,
            )
            if match.group("class") in unresolved_names
        }
        for match in re.finditer(
            r"\b(?P<receiver>[A-Za-z_$][\w$]*)\s*\.\s*"
            r"(?P<method>save|findById|findOne|find|create|updateOne|deleteOne)\s*\(",
            content,
        ):
            receiver = match.group("receiver")
            if receiver not in unresolved_names and receiver not in instance_sources:
                continue
            method = match.group("method")
            if method not in _PERSISTENCE_METHODS:
                continue
            line, column = _location(content, match.start())
            findings.append(
                self._finding(
                    "UNVERIFIED_PERSISTENCE_INTERFACE",
                    AdherenceFindingSeverity.BLOCKING,
                    "A persistence-style method is invoked on an unverified imported interface.",
                    "Persistence operations must be declared by validated dependency evidence.",
                    f"Unverified call: {receiver}.{method}(...).",
                    line=line,
                    column=column,
                )
            )
        return findings

    def _api_findings(self, context, content):
        approved = _approved_api_contracts(context)
        if not approved:
            if any(item.value == "API_IMPLEMENTATION" for item in context.authorized_output_codes):
                return [
                    self._finding(
                        "API_CONTRACT_UNAVAILABLE",
                        AdherenceFindingSeverity.REVIEW_REQUIRED,
                        "No verified API specification items were supplied for an API file.",
                        "API implementation requires endpoint-level trusted PSI evidence.",
                        "The approved file context contains no parseable API contract.",
                    )
                ]
            return []
        routes = _parse_routes(content)
        findings = []
        matched_approved: set[tuple[str, str]] = set()
        mount_uncertain: set[tuple[str, str]] = set()
        for route in routes:
            normalized = _normalize_route_path(route.path)
            exact = next(
                (
                    item
                    for item in approved
                    if item["method"] == route.method and item["path"] == normalized
                ),
                None,
            )
            same_path = [item for item in approved if item["path"] == normalized]
            if exact is None and same_path:
                refs = tuple(item["psi_id"] for item in same_path)
                findings.append(
                    self._finding(
                        "UNAPPROVED_HTTP_METHOD",
                        AdherenceFindingSeverity.BLOCKING,
                        "A route uses an HTTP method absent from the approved endpoint contract.",
                        "Use only the approved method for this route path.",
                        f"Observed {route.method} {route.path}.",
                        line=route.line,
                        column=route.column,
                        evidence_refs=refs,
                    )
                )
                continue
            if exact is None:
                possible = [
                    item
                    for item in approved
                    if item["method"] == route.method
                    and _could_be_mounted(item["path"], normalized)
                ]
                if possible:
                    refs = tuple(item["psi_id"] for item in possible)
                    mount_uncertain.update(
                        (item["method"], item["path"]) for item in possible
                    )
                    findings.append(
                        self._finding(
                            "ROUTE_MOUNT_CONTEXT_UNRESOLVED",
                            AdherenceFindingSeverity.REVIEW_REQUIRED,
                            "The final Express path depends on an unavailable router "
                            "mount prefix.",
                            "Supply the parent router interface before accepting the "
                            "final endpoint path.",
                            f"Generated local route: {route.method} {route.path}.",
                            line=route.line,
                            column=route.column,
                            evidence_refs=refs,
                        )
                    )
                    continue
                findings.append(
                    self._finding(
                        "UNAPPROVED_API_ENDPOINT",
                        AdherenceFindingSeverity.BLOCKING,
                        "Generated code introduces an endpoint absent from approved API evidence.",
                        "Generate only endpoints established by supplied API PSI items.",
                        f"Unexpected endpoint: {route.method} {route.path}.",
                        line=route.line,
                        column=route.column,
                    )
                )
                continue
            matched_approved.add((exact["method"], exact["path"]))
            block = content[route.start : route.end]
            for status_match in re.finditer(
                r"\bres\s*\.\s*(?:status|sendStatus)\s*\(\s*(\d{3})\s*\)",
                block,
            ):
                status = int(status_match.group(1))
                if status not in exact["statuses"]:
                    line, column = _location(content, route.start + status_match.start())
                    findings.append(
                        self._finding(
                            "UNAPPROVED_HTTP_STATUS",
                            AdherenceFindingSeverity.BLOCKING,
                            "Generated route emits an HTTP status absent from the "
                            "approved contract.",
                            f"Approved statuses: {sorted(exact['statuses'])}.",
                            f"Observed explicit status {status}.",
                            line=line,
                            column=column,
                            evidence_refs=(exact["psi_id"],),
                        )
                    )
            body_fields = set()
            for body_match in re.finditer(
                r"\{(?P<fields>[^{}]+)\}\s*=\s*req\s*\.\s*body",
                block,
            ):
                body_fields.update(
                    part.strip().split(":", 1)[0].strip()
                    for part in body_match.group("fields").split(",")
                    if part.strip()
                )
            for field in sorted(body_fields - exact["request_fields"]):
                findings.append(
                    self._finding(
                        "UNAPPROVED_REQUEST_FIELD",
                        AdherenceFindingSeverity.BLOCKING,
                        "Generated route reads a request field absent from approved API evidence.",
                        f"Approved fields: {sorted(exact['request_fields'])}.",
                        f"Observed request field: {field}.",
                        line=route.line,
                        column=route.column,
                        evidence_refs=(exact["psi_id"],),
                    )
                )
        for item in approved:
            identity = (item["method"], item["path"])
            if identity not in matched_approved and identity not in mount_uncertain:
                findings.append(
                    self._finding(
                        "APPROVED_ENDPOINT_NOT_IMPLEMENTED",
                        AdherenceFindingSeverity.BLOCKING,
                        "A required approved endpoint is absent from the generated route file.",
                        "Implement every endpoint assigned to this planned file.",
                        f"Missing endpoint: {item['method']} {item['path']}.",
                        evidence_refs=(item["psi_id"],),
                    )
                )
        return findings

    def _stack_findings(self, context, imports):
        findings = []
        database = context.effective_stack.database.casefold()
        if "mysql" not in database:
            return findings
        for module in imports:
            package = _package_root(module.source).casefold()
            if package in {"mongoose", "mongodb", "pg", "postgres", "sequelize-postgres"}:
                findings.append(
                    self._finding(
                        "INCOMPATIBLE_DATABASE_DEPENDENCY",
                        AdherenceFindingSeverity.BLOCKING,
                        "An explicit database dependency conflicts with the approved "
                        "effective stack.",
                        "Use dependencies compatible with the approved MySQL stack.",
                        f"Observed explicit dependency {package!r}.",
                        line=module.line,
                        column=module.column,
                    )
                )
        return findings

    @staticmethod
    def _finding(
        code,
        severity,
        description,
        expected,
        observed,
        *,
        line=None,
        column=None,
        evidence_refs=(),
    ):
        return CodeAdherenceFinding(
            code=code,
            severity=severity,
            description=description,
            expected_behavior=expected,
            observed_behavior=observed,
            line=line,
            column=column,
            evidence_refs=tuple(sorted(set(evidence_refs))),
        )


def _parse_imports(content: str):
    modules: list[_ModuleRef] = []
    bindings: list[_Binding] = []
    occupied: set[tuple[str, int]] = set()
    for regex, kind in (
        (_STATIC_IMPORT_RE, "esm"),
        (_REQUIRE_ASSIGN_RE, "cjs"),
    ):
        for match in regex.finditer(content):
            line, column = _location(content, match.start())
            source = match.group("source")
            modules.append(_ModuleRef(source, line, column))
            occupied.add((source, line))
            bindings.extend(_bindings(match.group("clause"), source, line, column, kind))
    for match in _SIDE_EFFECT_IMPORT_RE.finditer(content):
        line, column = _location(content, match.start())
        source = match.group("source")
        if (source, line) not in occupied:
            modules.append(_ModuleRef(source, line, column))
            occupied.add((source, line))
    for match in _BARE_REQUIRE_RE.finditer(content):
        line, column = _location(content, match.start())
        source = match.group("source")
        if (source, line) not in occupied:
            modules.append(_ModuleRef(source, line, column))
    modules.sort(key=lambda item: (item.line, item.column, item.source))
    bindings.sort(key=lambda item: (item.line, item.column, item.local_name))
    return tuple(modules), tuple(bindings)


def _bindings(clause, source, line, column, kind):
    clause = clause.strip()
    result = []
    if clause.startswith("{") and clause.endswith("}"):
        for raw in clause[1:-1].split(","):
            parts = [part.strip() for part in re.split(r"\s+as\s+|\s*:\s*", raw) if part.strip()]
            if parts:
                result.append(_Binding(parts[-1], parts[0], source, line, column))
        return result
    if clause.startswith("*"):
        name = clause.split()[-1]
        return [_Binding(name, "*", source, line, column)]
    if kind == "cjs":
        name = clause.strip()
        return [_Binding(name, "default", source, line, column)]
    default = clause.split(",", 1)[0].strip()
    if default:
        result.append(_Binding(default, "default", source, line, column))
    if "{" in clause and "}" in clause:
        result.extend(
            _bindings(
                clause[clause.index("{") : clause.rindex("}") + 1],
                source,
                line,
                column,
                kind,
            )
        )
    return result


def _package_contract(context):
    names: set[str] = set()
    packages = [
        item
        for item in context.dependencies
        if PurePosixPath(item.relative_output_path.root).name == "package.json"
    ]
    if not packages:
        return None, names, "No validated package.json dependency was supplied."
    try:
        package = json.loads(packages[0].validated_content)
    except (json.JSONDecodeError, TypeError):
        return None, names, "The validated package.json dependency is not parseable JSON."
    if not isinstance(package, dict):
        return None, names, "The validated package.json dependency has no object root."
    for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = package.get(field, {})
        if isinstance(value, dict):
            names.update(str(item) for item in value)
    module_system = "ESM" if package.get("type") == "module" else "COMMONJS"
    return module_system, names, f"package.json establishes {module_system}."


def _approved_framework_packages(context):
    approved = set()
    stack = context.effective_stack
    if "express" in stack.backend.casefold():
        approved.add("express")
    if "react" in stack.frontend.casefold():
        approved.update({"react", "react-dom"})
    if "vite" in stack.frontend.casefold():
        approved.add("vite")
    return approved


def _resolve_dependency(current_path, source, dependencies):
    if "\\" in source or "\x00" in source or source.startswith("/"):
        return None
    base = str(PurePosixPath(current_path).parent)
    normalized = posixpath.normpath(posixpath.join(base, source))
    if normalized == ".." or normalized.startswith("../"):
        return None
    candidates = {
        normalized,
        normalized + ".js",
        normalized + ".jsx",
        normalized + ".json",
        normalized + "/index.js",
        normalized + "/index.jsx",
    }
    return next(
        (
            item
            for item in dependencies
            if item.relative_output_path.root in candidates
        ),
        None,
    )


def _declared_exports(content):
    exports = set()
    for match in re.finditer(
        r"\bexport\s+(?:async\s+)?(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)",
        content,
    ):
        exports.add(match.group(1))
    if re.search(r"\bexport\s+default\b", content):
        exports.add("default")
    for match in re.finditer(r"\bexports\.([A-Za-z_$][\w$]*)\s*=", content):
        exports.add(match.group(1))
    for match in re.finditer(r"\bmodule\.exports\.([A-Za-z_$][\w$]*)\s*=", content):
        exports.add(match.group(1))
    if re.search(r"\bmodule\.exports\s*=", content):
        exports.update({"default", "*"})
    return exports


def _approved_api_contracts(context):
    contracts = []
    for item in context.trusted_specification_items:
        if item.artifact_type != "API_SPECIFICATION":
            continue
        try:
            data = json.loads(item.trusted_data_json)
            method = str(data["method"]).upper()
            path = _normalize_route_path(str(data["path"]))
            statuses = {int(value) for value in data.get("response_statuses", [])}
            fields = {str(value) for value in data.get("request_fields", [])}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        contracts.append(
            {
                "psi_id": item.project_item_id,
                "method": method,
                "path": path,
                "statuses": statuses,
                "request_fields": fields,
            }
        )
    return tuple(sorted(contracts, key=lambda item: (item["path"], item["method"])))


def _parse_routes(content):
    matches = list(_ROUTE_RE.finditer(content))
    routes = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        line, column = _location(content, match.start())
        routes.append(
            _Route(
                method=match.group("method").upper(),
                path=match.group("path"),
                start=match.start(),
                end=end,
                line=line,
                column=column,
            )
        )
    return tuple(routes)


def _normalize_route_path(path):
    value = re.sub(r"/:([A-Za-z_][A-Za-z0-9_]*)", r"/{\1}", path.strip())
    if len(value) > 1:
        value = value.rstrip("/")
    return value


def _could_be_mounted(approved_path, generated_path):
    if generated_path == "/":
        return True
    return approved_path.endswith(generated_path) and approved_path != generated_path


def _package_root(source):
    if source.startswith("node:"):
        return source
    parts = source.split("/")
    return "/".join(parts[:2]) if source.startswith("@") else parts[0]


def _is_node_builtin(source):
    if source.startswith("node:"):
        return source[5:].split("/", 1)[0] in _NODE_BUILTINS
    return source.split("/", 1)[0] in _NODE_BUILTINS


def _location(content, index):
    line = content.count("\n", 0, index) + 1
    previous = content.rfind("\n", 0, index)
    return line, index - previous


def _check_state(findings, passed_detail, inconclusive_detail):
    if any(item.severity is AdherenceFindingSeverity.BLOCKING for item in findings):
        return AdherenceCheckStatus.FAILED, inconclusive_detail
    if any(item.severity is AdherenceFindingSeverity.REVIEW_REQUIRED for item in findings):
        return AdherenceCheckStatus.INCONCLUSIVE, inconclusive_detail
    return AdherenceCheckStatus.PASSED, passed_detail


def _report_status(findings, has_content):
    severities = {item.severity for item in findings}
    if AdherenceFindingSeverity.BLOCKING in severities:
        return CodeAdherenceStatus.BLOCKED
    if AdherenceFindingSeverity.REVIEW_REQUIRED in severities:
        return CodeAdherenceStatus.REVIEW_REQUIRED
    if not has_content:
        return CodeAdherenceStatus.NOT_CHECKED
    return CodeAdherenceStatus.PASS
