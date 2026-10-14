# Agent 3 — Implementation and Git Automation Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Agent type: `IMPLEMENTATION`

Run mode: `DEFAULT`
Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Standalone Purpose and Core Requirement

Agent 3 — Implementation and Git Automation Agent generates a software implementation from manually supplied specifications and verifies that generated code can build/run.

**Agent 3 must aim to produce runnable code. Pure code-text generation is not sufficient as its final behavior.** A result must honestly distinguish generated files from verified build/execution behavior and retain failure evidence when verification does not succeed.

## 2. Required Inputs

```text
project_name
feature_or_application_description
requirements_or_functional_specification
preferred_technology_stack
```

Each required input must contain enough usable information to scope implementation. The preferred stack is a constraint; inability to support or execute it must be reported rather than silently replaced.

## 3. Optional Inputs

```text
system_architecture
api_specification
database_schema
wireframes_or_ui_specification
user_stories
acceptance_criteria
test_cases
existing_source_code
repository_information
environment_constraints
additional_instructions
```

Existing source/repository inputs require safe workspace handling. Concrete upload, checkout, filesystem sandbox, command allowlist, secret scanning, and size policies belong to implementation planning.

## 4. Selectable Output Codes

The allowed Agent 3 `selected_outputs` values are exactly:

```text
PROJECT_STRUCTURE
FRONTEND_CODE
BACKEND_CODE
DATABASE_IMPLEMENTATION
API_IMPLEMENTATION
CONFIGURATION_FILES
CONTAINER_CONFIGURATION
GIT_SUMMARY
```

The selection must be non-empty. A selection should be coherent with the described feature/application and preferred technology stack. The agent must not claim an unselected code area was generated unless it was technically required and clearly identified.

## 5. Output Expectations

| Output code | Structured expectation |
|---|---|
| `PROJECT_STRUCTURE` | Directory/module plan or generated structure with purpose and relevant entry points. |
| `FRONTEND_CODE` | Generated or modified frontend source artifacts consistent with the supplied specifications. |
| `BACKEND_CODE` | Generated or modified backend source artifacts consistent with the supplied specifications. |
| `DATABASE_IMPLEMENTATION` | Database definitions/access implementation appropriate to the selected stack and supplied schema. |
| `API_IMPLEMENTATION` | API routes/handlers/services and contracts implemented to the justified scope. |
| `CONFIGURATION_FILES` | Required build/runtime/application configuration, using safe placeholders rather than credentials. |
| `CONTAINER_CONFIGURATION` | Container-related configuration when selected and supported. |
| `GIT_SUMMARY` | A structured summary of supported local/generated repository actions, affected files, and version-control intent/evidence. |

Generated code must be made available through referenced artifacts/workspace rather than requiring every file body to be duplicated inside `agent_runs`. It should eventually be exportable as a project archive/workspace.

## 6. Mandatory Execution Evidence

Whenever executable source code is generated, Agent 3 must return all of:

```text
BUILD_RESULT
EXECUTION_RESULT
EXECUTION_LOGS
```

These are mandatory execution-evidence result keys, not optional `selected_outputs` codes.

- `BUILD_RESULT` states whether dependency resolution/build/compile steps were attempted and their outcome, with the applicable command/tool and safe diagnostics.
- `EXECUTION_RESULT` states whether the generated application or relevant executable portion started/ran as expected, or why execution was not possible.
- `EXECUTION_LOGS` provides bounded, sanitized logs/references sufficient to review build and run behavior and correction attempts.

A failed build or run must not be hidden. The run may end `FAILED` with `BUILD_FAILED`, `TOOL_EXECUTION_FAILED`, or another applicable error, while preserving safe evidence. Exact criteria for a completed run with limited/skipped evidence must be frozen during implementation and must not mislabel unverified code as runnable.

## 7. Expected Generation and Correction Loop

```text
Generate
  → write files
  → resolve/install dependencies
  → build
  → run
  → detect error
  → analyze
  → correct
  → rebuild/re-run
```

Execution occurs only in an approved controlled workspace with validated commands and resource/security limits. Correction behavior must be bounded. Exact retry count, timeouts, command policy, network access, resource quotas, and escalation behavior belong to implementation planning; unlimited autonomous retries are prohibited.

The evidence must distinguish each attempted build/run/correction sufficiently to understand the final result without overwriting relevant failure history.

## 8. Git Automation Boundary

Standalone Agent 3 may eventually support:

- repository initialization;
- branch creation;
- commits; and
- pull-request preparation.

For Progress Presentation 1, remote GitHub integration is not a blocker for runnable-code generation. `GIT_SUMMARY` may initially describe local/generated repository actions. It must not claim a remote push, pull request, or commit occurred unless that action was explicitly authorized and verified.

Concrete Git permissions, user confirmation, branch naming, commit policy, remote authentication, provider integration, and rollback are later implementation decisions. The S0 documentation task performs no Git write operation.

## 9. Validation and Normalization

Before engine execution, Agent 3 must:

1. require all four required inputs;
2. validate the exact Agent 3 selection codes;
3. validate the requested scope against the preferred stack and available environment;
4. normalize specifications, designs, existing code references, tests, and constraints into an Agent 3 input context;
5. create a safe serializable `input_snapshot` without credentials or arbitrary binaries; and
6. define the execution evidence required by the selected code outputs.

## 10. Results and Error Categories

Agent 3 returns selected outputs plus mandatory execution evidence in the common `AgentRunResult.outputs`. Applicable error categories include:

```text
INPUT_VALIDATION_FAILED
MODEL_EXECUTION_FAILED
STRUCTURED_OUTPUT_INVALID
TOOL_EXECUTION_FAILED
BUILD_FAILED
TEST_EXECUTION_FAILED
INTERNAL_ERROR
```

`TEST_EXECUTION_FAILED` applies only when Agent 3 runs relevant supplied/generated checks as part of its verification; it does not transfer Agent 4 ownership.

## 11. Isolation and Engine Reuse

The standalone manual-input adapter and future integrated Shared Knowledge Base adapter normalize to the same Agent 3 engine. Standalone Agent 3 does not require Agents 1, 2, or 4 to have run; create H4 Approval; advance the Orchestrator; or automatically write results to the integrated Shared Knowledge Base.
