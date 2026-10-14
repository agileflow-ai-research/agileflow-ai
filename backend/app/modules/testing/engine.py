import ast
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, create_model

from app.common.model_provider import ModelStructuredOutputError, StructuredModelProvider
from app.common.status import AgentRunMode
from app.modules.testing.executor import (
    SandboxedValidationExecutor,
    ValidationCommandResult,
    ValidationExecutionRequest,
    ValidationExecutor,
    resolve_validation_profile,
)
from app.modules.testing.schemas import (
    Agent4InputContext,
    TEST_OUTPUT_MODELS,
    TestGenerationOutputCode,
    ValidationOutputCode,
)


class StructuredOutputInvalidError(ValueError):
    """Agent 4 generated output did not satisfy its structured contract."""


TEST_GENERATION_PROMPT = """You are Agent 4 in TEST_GENERATION mode. Generate only the selected structured
test artifacts, grounded in supplied SRC references. A test must include purpose, preconditions, test data,
steps, expected result, and source coverage. Use TEST-001 identifiers. Mark a test EXECUTABLE_CODE only when
the context includes both existing source code and a technology stack and provide real framework-oriented
code; otherwise use SPECIFICATION, executable=false, framework=null, code=null. Generated code has not been
executed: execution_status is always NOT_EXECUTED. Security tests must be safe. TEST_TRACEABILITY is local
standalone result mapping only (scope STANDALONE_RESULT); never claim a database traceability write. Return
strict JSON with exactly the requested top-level keys and no lifecycle or ownership metadata."""


def _make_schema_strict(node: Any) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["required"] = list(properties)
            node["additionalProperties"] = False
        for nested in node.values():
            _make_schema_strict(nested)
    elif isinstance(node, list):
        for nested in node:
            _make_schema_strict(nested)


def selected_test_schema(selected: list[TestGenerationOutputCode]) -> dict[str, Any]:
    response_model = create_model(
        "Agent4SelectedTestOutputs",
        __config__=ConfigDict(extra="forbid"),
        **{code.value: (TEST_OUTPUT_MODELS[code], ...) for code in selected},
    )
    schema = response_model.model_json_schema()
    _make_schema_strict(schema)
    return schema


class Agent4Engine:
    def __init__(
        self,
        provider: StructuredModelProvider,
        executor: ValidationExecutor | None = None,
    ) -> None:
        self._provider = provider
        self._executor = executor or SandboxedValidationExecutor()

    def execute(self, context: Agent4InputContext, selected_outputs: list[str]) -> dict[str, Any]:
        if context.run_mode is AgentRunMode.TEST_GENERATION:
            return self._generate_tests(context, [TestGenerationOutputCode(code) for code in selected_outputs])
        if context.run_mode is AgentRunMode.VALIDATION:
            return self._validate(context, [ValidationOutputCode(code) for code in selected_outputs])
        raise StructuredOutputInvalidError("Agent 4 does not support DEFAULT mode")

    def _generate_tests(
        self, context: Agent4InputContext, selected: list[TestGenerationOutputCode]
    ) -> dict[str, Any]:
        try:
            raw = self._provider.generate_structured(
                system_prompt=TEST_GENERATION_PROMPT,
                user_prompt=(
                    "Requested outputs: " + ", ".join(code.value for code in selected)
                    + "\nNormalized input context:\n"
                    + json.dumps(context.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
                ),
                json_schema=selected_test_schema(selected),
            )
        except ModelStructuredOutputError as exc:
            raise StructuredOutputInvalidError("Model response was not valid structured JSON") from exc
        if set(raw) != {code.value for code in selected}:
            raise StructuredOutputInvalidError("Model output keys did not match selected outputs")

        validated: dict[str, Any] = {}
        try:
            for code in selected:
                value = TypeAdapter(TEST_OUTPUT_MODELS[code]).validate_python(raw[code.value])
                if not value:
                    raise StructuredOutputInvalidError(f"{code.value} must not be empty")
                validated[code.value] = [item.model_dump(mode="json") for item in value]
        except (ValidationError, KeyError, TypeError) as exc:
            raise StructuredOutputInvalidError("Generated tests failed Agent 4 structured validation") from exc

        source_refs = {source["source_id"] for source in context.inputs.get("sources", [])}
        executable_context = bool(context.inputs.get("existing_source_code") and context.inputs.get("technology_stack"))
        test_ids: set[str] = set()
        for code, items in validated.items():
            if code == TestGenerationOutputCode.TEST_TRACEABILITY.value:
                continue
            for item in items:
                if not set(item["source_refs"]).issubset(source_refs):
                    raise StructuredOutputInvalidError(f"{code} contains an invalid source reference")
                if item["id"] in test_ids:
                    raise StructuredOutputInvalidError("Generated tests contain duplicate identifiers")
                test_ids.add(item["id"])
                if item["executable"] and not executable_context:
                    raise StructuredOutputInvalidError("Executable test code requires source code and technology stack context")
        for link in validated.get(TestGenerationOutputCode.TEST_TRACEABILITY.value, []):
            if link["source_ref"] not in source_refs:
                raise StructuredOutputInvalidError("TEST_TRACEABILITY contains an invalid source reference")
            if test_ids and not set(link["test_refs"]).issubset(test_ids):
                raise StructuredOutputInvalidError("TEST_TRACEABILITY contains an invalid generated test reference")
        return validated

    def _validate(self, context: Agent4InputContext, selected: list[ValidationOutputCode]) -> dict[str, Any]:
        inputs = context.inputs
        source = inputs["source_code_or_project"]
        profile = resolve_validation_profile(
            inputs.get("validation_profile"),
            inputs.get("build_command"),
            inputs.get("run_command"),
        )
        execution = self._executor.execute(
            ValidationExecutionRequest(source=source, profile=profile)
        )
        build, tests = execution.build, execution.tests
        security = self._security_scan(source)
        quality = self._quality_scan(source)
        coverage = self._coverage_evidence(tests)
        bugs = self._bug_reports(build, tests, quality)
        acceptance = self._acceptance_results(
            inputs.get("acceptance_criteria"), inputs.get("test_cases"), tests
        )

        outputs: dict[str, Any] = {}
        for code in selected:
            if code is ValidationOutputCode.TEST_EXECUTION_REPORT:
                outputs[code.value] = {
                    "status": tests.outcome,
                    "environment": {
                        "supplied_information": inputs.get("environment_information"),
                        "sandbox": execution.sandbox,
                    },
                    "build_evidence": build.as_dict(),
                    "evidence": tests.as_dict(),
                    "failures": bugs,
                    "test_cases_supplied": bool(inputs.get("test_cases")),
                }
            elif code is ValidationOutputCode.COVERAGE_REPORT:
                outputs[code.value] = coverage
            elif code is ValidationOutputCode.BUG_REPORTS:
                outputs[code.value] = bugs
            elif code is ValidationOutputCode.SECURITY_FINDINGS:
                outputs[code.value] = {
                    "scanner": "AGILEFLOW_PYTHON_AST_SECURITY_SCANNER",
                    "executed": True,
                    "findings": security,
                    "llm_suggested_observations": [],
                }
            elif code is ValidationOutputCode.CODE_QUALITY_REPORT:
                outputs[code.value] = quality
            elif code is ValidationOutputCode.ACCEPTANCE_CRITERIA_VALIDATION:
                outputs[code.value] = acceptance
            elif code is ValidationOutputCode.FINAL_VALIDATION_REPORT:
                outputs[code.value] = self._final_report(
                    build, tests, coverage, security, quality, acceptance,
                    execution.sandbox,
                )
        return outputs

    @staticmethod
    def _source_files(source: str | dict[str, str]) -> dict[str, str]:
        return {"source.py": source} if isinstance(source, str) else source

    @classmethod
    def _security_scan(cls, source: str | dict[str, str]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for filename, content in cls._source_files(source).items():
            if not filename.lower().endswith(".py"):
                continue
            try:
                tree = ast.parse(content, filename=filename)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                finding = None
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    finding = ("AST-DYNAMIC-EXECUTION", "HIGH", f"Use of {node.func.id} can execute untrusted input")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"run", "Popen", "call"}:
                    if any(keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in node.keywords):
                        finding = ("AST-SHELL-TRUE", "HIGH", "Subprocess execution enables shell=True")
                elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    names = [target.id for target in node.targets if isinstance(target, ast.Name)]
                    if any(re.search(r"(?i)(password|secret|api_?key|token)", name) for name in names) and node.value.value:
                        finding = ("AST-HARDCODED-SECRET", "HIGH", "Possible hardcoded secret assigned in source")
                if finding:
                    rule, severity, message = finding
                    findings.append({
                        "id": f"SEC-{len(findings) + 1:03d}", "rule_id": rule,
                        "severity": severity, "message": message, "file": filename,
                        "line": getattr(node, "lineno", None), "evidence_type": "ACTUAL_SCANNER_FINDING",
                        "scanner": "AGILEFLOW_PYTHON_AST_SECURITY_SCANNER",
                        "recommendation": "Review the affected code and replace the unsafe construct with a bounded alternative.",
                    })
        return findings

    @classmethod
    def _quality_scan(cls, source: str | dict[str, str]) -> dict[str, Any]:
        files = cls._source_files(source)
        findings: list[dict[str, Any]] = []
        python_files = 0
        for filename, content in files.items():
            if not filename.lower().endswith(".py"):
                continue
            python_files += 1
            try:
                tree = ast.parse(content, filename=filename)
            except SyntaxError as exc:
                findings.append({"code": "PYTHON_SYNTAX_ERROR", "file": filename, "line": exc.lineno, "message": exc.msg})
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(node.body) > 40:
                    findings.append({"code": "LONG_FUNCTION", "file": filename, "line": node.lineno, "message": f"{node.name} has more than 40 statements"})
        return {
            "tool": "PYTHON_AST_QUALITY_CHECK", "executed": True,
            "scope": {"files_received": len(files), "python_files_analyzed": python_files},
            "status": "ISSUES_FOUND" if findings else "PASSED", "findings": findings,
        }

    @staticmethod
    def _coverage_evidence(tests: ValidationCommandResult) -> dict[str, Any]:
        combined = f"{tests.stdout}\n{tests.stderr}"
        measured = tests.exit_code is not None and (
            "coverage" in " ".join(tests.command).lower()
            or any(argument.startswith("--cov") for argument in tests.command)
        )
        percentages = []
        if measured:
            percentages.extend(re.findall(r"(?im)^TOTAL\s+\d+\s+\d+\s+(\d{1,3}(?:\.\d+)?)%", combined))
            percentages.extend(re.findall(r"(?im)^coverage(?:\s+total)?\s*[:=]\s*(\d{1,3}(?:\.\d+)?)%", combined))
        return {
            "status": "MEASURED" if percentages else "NOT_MEASURED",
            "tool": tests.tool if measured else None,
            "metrics": {"reported_percentages": [float(value) for value in percentages]} if percentages else {},
            "evidence": tests.as_dict() if measured else None,
            "reason": None if percentages else "No coverage-capable command produced measurable coverage output",
        }

    @staticmethod
    def _bug_reports(
        build: ValidationCommandResult,
        tests: ValidationCommandResult,
        quality: dict[str, Any],
    ) -> list[dict[str, Any]]:
        bugs: list[dict[str, Any]] = []
        for kind, evidence in (("BUILD_FAILURE", build), ("TEST_FAILURE", tests)):
            if evidence.outcome in {"FAILED", "TIMED_OUT"}:
                bugs.append({
                    "id": f"BUG-{len(bugs) + 1:03d}", "title": kind.replace("_", " ").title(),
                    "severity": "HIGH" if kind == "BUILD_FAILURE" else "MEDIUM",
                    "status": "OPEN", "evidence_type": "ACTUAL_SANDBOX_EXECUTION",
                    "command": evidence.command, "exit_code": evidence.exit_code,
                    "observed": evidence.stderr or evidence.stdout or evidence.reason,
                    "source_refs": [], "test_refs": [],
                })
        for finding in quality["findings"]:
            if finding["code"] == "PYTHON_SYNTAX_ERROR":
                bugs.append({
                    "id": f"BUG-{len(bugs) + 1:03d}", "title": "Python syntax error",
                    "severity": "HIGH", "status": "OPEN", "evidence_type": "ACTUAL_STATIC_ANALYSIS",
                    "command": [], "exit_code": None, "observed": finding["message"],
                    "source_refs": [f"{finding['file']}:{finding['line']}"], "test_refs": [],
                })
        return bugs

    @staticmethod
    def _acceptance_results(
        criteria: str | None,
        test_cases: str | None,
        tests: ValidationCommandResult,
    ) -> list[dict[str, Any]]:
        if not criteria:
            return []
        items = [item.strip(" -*\t") for item in criteria.splitlines() if item.strip(" -*\t")]
        results = []
        normalized_cases = (test_cases or "").casefold()
        for item in items:
            linked = bool(normalized_cases and item.casefold() in normalized_cases)
            supported = tests.outcome == "PASSED" and linked
            results.append({
                "criterion": item,
                "status": "SUPPORTED_BY_EXECUTED_TEST" if supported else "UNABLE_TO_VALIDATE",
                "evidence": tests.as_dict() if supported else None,
                "limitation": None if supported else "No explicitly linked passing test execution establishes this criterion",
            })
        return results

    @staticmethod
    def _final_report(
        build: ValidationCommandResult,
        tests: ValidationCommandResult,
        coverage: dict[str, Any],
        security: list[dict[str, Any]],
        quality: dict[str, Any],
        acceptance: list[dict[str, Any]],
        sandbox: dict[str, Any],
    ) -> dict[str, Any]:
        failures = sum(item.outcome in {"FAILED", "TIMED_OUT"} for item in (build, tests))
        limitations = []
        if tests.outcome == "SKIPPED": limitations.append("Tests were not executed")
        if coverage["status"] != "MEASURED": limitations.append("Coverage was not measured")
        if not acceptance: limitations.append("Acceptance criteria were not validated")
        return {
            "readiness": "NOT_READY" if failures or security else ("CONDITIONALLY_READY" if limitations else "READY"),
            "build_status": build.outcome, "test_status": tests.outcome,
            "coverage_status": coverage["status"], "security_finding_count": len(security),
            "quality_status": quality["status"], "acceptance_results": acceptance,
            "limitations": limitations,
            "evidence_summary": {
                "build_executed": build.exit_code is not None,
                "tests_executed": tests.exit_code is not None,
                "security_scanner_executed": True,
                "coverage_measured": coverage["status"] == "MEASURED",
            },
            "sandbox": sandbox,
        }
