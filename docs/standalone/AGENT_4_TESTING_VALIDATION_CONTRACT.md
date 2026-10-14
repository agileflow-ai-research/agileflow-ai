# Agent 4 — Testing, Validation and Security Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Agent type: `TESTING_VALIDATION`

Run modes: `TEST_GENERATION`, `VALIDATION`
Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Standalone Purpose and Mode Separation

Agent 4 — Testing, Validation and Security Agent is one research agent with two explicit standalone modes:

1. `TEST_GENERATION`
2. `VALIDATION`

They must not be combined into one ambiguous screen, input form, selection list, or process. A user chooses the mode before supplying mode-specific inputs and outputs. A single Agent 4 project may retain runs from either mode, with every run recording its own `run_mode`.

Agent 4 must not use `DEFAULT`.

## 2. Mode A — `TEST_GENERATION`

### Purpose

Generate test specifications and, where sufficient implementation context exists, executable test code. The result must distinguish a test specification from test code that has actually been generated or executed.

### Required inputs

```text
project_name
```

At least one usable functional/context source is required from:

```text
requirements
user_stories
acceptance_criteria
SRS
```

### Optional inputs

```text
system_architecture
api_specification
database_schema
ui_specification
existing_source_code
technology_stack
```

Executable test-code generation is conditional on adequate implementation and technology context. Missing source code or stack details must not be concealed by presenting abstract cases as executed tests.

### Selectable output codes

The allowed `TEST_GENERATION` `selected_outputs` values are exactly:

```text
UNIT_TEST_CASES
API_TEST_CASES
INTEGRATION_TEST_CASES
FUNCTIONAL_TEST_CASES
E2E_TEST_CASES
REGRESSION_TEST_CASES
SECURITY_TEST_CASES
ACCEPTANCE_TEST_CASES
TEST_TRACEABILITY
```

The selection must be non-empty. Each result identifies whether it is a specification, generated executable code, or other supported representation.

### Output expectations

- Test-case outputs describe purpose, preconditions, inputs/data, steps or automated structure, expected result, and source coverage where applicable.
- Security test cases are safe validation specifications and must not introduce uncontrolled harmful execution.
- Generated executable tests must identify their target stack/framework and remain subject to controlled tool/execution policy.
- `TEST_TRACEABILITY` connects a requirement, user story, or acceptance criterion to the generated test specification within the standalone result context.

`TEST_TRACEABILITY` does not force persistence in the integrated Project's `traceability_links` collection.

## 3. Mode B — `VALIDATION`

### Purpose

Execute applicable tests/tools and validate an implementation using supplied source/project context.

### Required inputs

```text
project_name
source_code_or_project
```

### Recommended or conditionally required inputs

```text
requirements
acceptance_criteria
test_cases
technology_stack
build_command
run_command
environment_information
```

These inputs are optional only when the requested validation can be performed reliably without them. Examples:

- `ACCEPTANCE_CRITERIA_VALIDATION` requires usable `acceptance_criteria`.
- Executing user-supplied `test_cases` requires those cases and enough project/environment context.
- A build/run step requires safe known or derived commands and a supported environment.
- A coverage report requires applicable executable tests and tooling capable of collecting coverage.

The validator must reject or warn about an impossible selection rather than fabricate evidence.

### Selectable output codes

The allowed `VALIDATION` `selected_outputs` values are exactly:

```text
TEST_EXECUTION_REPORT
COVERAGE_REPORT
BUG_REPORTS
SECURITY_FINDINGS
CODE_QUALITY_REPORT
ACCEPTANCE_CRITERIA_VALIDATION
FINAL_VALIDATION_REPORT
```

The selection must be non-empty and must not contain `TEST_GENERATION` output codes.

### Validation flow

```text
Source Code / Project
        +
Test Cases / Specifications
        +
Acceptance Criteria
        ↓
prepare execution
        ↓
execute applicable tests/tools
        ↓
collect results
        ↓
analyze failures
        ↓
coverage / quality / security checks
        ↓
structured reports
```

Inputs shown with `+` are included when applicable to the requested validation. Execution must use bounded, controlled tools and preserve safe command/result evidence. A report must distinguish checks that passed, failed, were skipped, were unsupported, or lacked sufficient context.

### Output expectations

- `TEST_EXECUTION_REPORT`: executed suites/cases, environment, commands/tools, outcomes, failures, and skipped work.
- `COVERAGE_REPORT`: collected coverage scope and metrics with tooling/context; never estimated and presented as measured.
- `BUG_REPORTS`: structured defects linked in standalone context to relevant tests, requirements, acceptance criteria, or source areas.
- `SECURITY_FINDINGS`: structured security issues, evidence, severity rationale, affected context, and recommendations, without exposing exploitable secrets.
- `CODE_QUALITY_REPORT`: applicable maintainability/static-quality findings and tool/method context.
- `ACCEPTANCE_CRITERIA_VALIDATION`: criterion-by-criterion result with supporting evidence or an explicit inability to validate.
- `FINAL_VALIDATION_REPORT`: consolidated conclusion that identifies scope, evidence, failures, limitations, warnings, and readiness assessment.

## 4. Cross-Mode Validation and Normalization

Before engine execution, Agent 4 must:

1. require exactly one allowed `run_mode`;
2. apply only that mode's required-input rules;
3. require a non-empty selection from only that mode's output codes;
4. enforce conditional context needed for meaningful generation/validation;
5. normalize the input into the corresponding Agent 4 engine context; and
6. preserve the serializable state and mode in `input_snapshot`.

UI and API layers must not merge the two output vocabularies. A run cannot switch mode after its snapshot is recorded.

## 5. Results and Error Categories

Agent 4 returns mode-specific structured output in the common `AgentRunResult.outputs`. Applicable error categories include:

```text
INPUT_VALIDATION_FAILED
MODEL_EXECUTION_FAILED
STRUCTURED_OUTPUT_INVALID
TOOL_EXECUTION_FAILED
BUILD_FAILED
TEST_EXECUTION_FAILED
INTERNAL_ERROR
```

Failed tests are domain results and may contribute to reports/bug findings; `TEST_EXECUTION_FAILED` is used when the requested test execution itself cannot complete as required. Concrete terminal-status policy for test failures versus execution failure is an S1/S2 decision and must remain honest and consistent.

## 6. Security and Tool Boundary

Source/project handling, dependency resolution, builds, test execution, scanners, and quality tools require controlled workspaces, sanitized commands, resource/time limits, and secret-safe logs. Tool choice, retry count, coverage thresholds, severity vocabulary, supported stacks, and environment provisioning are not frozen in S0.

## 7. Isolation and Reuse

Both modes are capabilities of the same reusable Agent 4 engine/component, with mode-specific validation and execution paths. The standalone manual-input adapter and future integrated Shared Knowledge Base adapter feed that reusable component.

Standalone Agent 4 does not require Agents 1–3 to have run, create H3 or H5 Approval, write automatically to integrated test/result/finding/traceability collections, or advance the Central SDLC Orchestrator.
