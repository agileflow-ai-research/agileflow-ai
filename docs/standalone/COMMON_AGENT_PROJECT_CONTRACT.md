# Common Standalone Agent Project and Run Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Scope

This document freezes the conceptual standalone workspace and execution records shared by all four specialist agents. It plans two collections—`agent_projects` and `agent_runs`—but does not implement collections, schemas, indexes, or persistence.

No separate project or run collection is allowed per agent.

## 2. Frozen Enumerations

### `AgentType`

```text
REQUIREMENTS
DESIGN_PLANNING
IMPLEMENTATION
TESTING_VALIDATION
```

### `AgentProjectStatus`

```text
ACTIVE
ARCHIVED
```

These are standalone workspace statuses. They are unrelated to integrated Project stages and never advance the Central SDLC Orchestrator.

### `AgentRunStatus`

```text
QUEUED
RUNNING
COMPLETED
FAILED
```

### `run_mode`

```text
DEFAULT
TEST_GENERATION
VALIDATION
```

Agents 1–3 use `DEFAULT`. Agent 4 uses `TEST_GENERATION` or `VALIDATION`; Agent 4 must not use `DEFAULT`.

## 3. `AgentProject` Conceptual Schema

The planned `agent_projects` record has exactly these common fields:

| Field | Contract semantics |
|---|---|
| `agent_project_id` | Server-generated canonical standalone project identifier in `AGP-###` form. |
| `owner_user_id` | Existing-authentication user identifier that owns the workspace. Server-controlled from the authenticated identity. |
| `agent_type` | One frozen `AgentType`; immutable after creation because it determines the specialist contract. |
| `name` | Human-readable workspace/project name. |
| `description` | Optional user description of the standalone effort. |
| `domain` | Application/business domain context. Agent-specific validation may require it. |
| `status` | `ACTIVE` or `ARCHIVED`. |
| `created_at` | Server-generated creation timestamp. |
| `updated_at` | Server-maintained timestamp for current project metadata/configuration changes. |

Agent-specific current input/configuration persistence is an S1/S2 design decision. It must not alter these frozen common field names.

## 4. `AgentRun` Conceptual Schema

The planned `agent_runs` record has exactly these common fields:

| Field | Contract semantics |
|---|---|
| `run_id` | Server-generated canonical run identifier in `RUN-###` form. |
| `agent_project_id` | Parent standalone project identifier. |
| `owner_user_id` | Owning existing-authentication user identifier; must equal the parent project's owner. |
| `agent_type` | Copied execution type; must equal the parent project's `agent_type`. |
| `run_mode` | `DEFAULT`, `TEST_GENERATION`, or `VALIDATION`, subject to the agent rules above. |
| `selected_outputs` | Non-empty set/list of valid output codes for the selected agent and mode. |
| `input_snapshot` | Serializable execution input/configuration snapshot sufficient to understand the run. |
| `status` | `QUEUED`, `RUNNING`, `COMPLETED`, or `FAILED`. |
| `output_manifest` | Metadata/reference description of outputs and artifacts produced by this run. |
| `warnings` | Structured non-fatal concerns retained with the run. |
| `errors` | Structured failure information retained with the run. |
| `created_at` | Time the run record was accepted/created. |
| `started_at` | Time execution began; absent until it begins. |
| `completed_at` | Time execution reached `COMPLETED` or `FAILED`; absent before a terminal state. |

## 5. Identifier Semantics

- Standalone project IDs use `AGP-###`.
- Standalone run IDs use `RUN-###`.
- They are not aliases for integrated `PRJ-###`, workflow-event, artifact, approval, or traceability IDs.
- Generation/concurrency mechanics and numeric width growth are implementation decisions for S1/S2; implementations must preserve the canonical prefixes and uniqueness.

## 6. Ownership and Access

All operations require the existing authentication system. The authenticated user is authoritative; clients must not choose another `owner_user_id`.

For every project or run operation:

1. resolve the authenticated user;
2. verify the `AgentProject.owner_user_id` matches that user;
3. for runs, also verify the run belongs to that project and its `owner_user_id` matches; and
4. do not reveal another user's resource existence or contents through list, detail, history, execution, error, or export behavior.

No new authentication system is part of standalone mode.

## 7. Project Semantics and Isolation

An `ACTIVE` project is available for normal editing and new runs. `ARCHIVED` means it is retained but not an active workspace. Exact archive/restore and archived-execution policies remain for S1/S2, but archival must not delete or rewrite run history.

An AgentProject has exactly one `agent_type`. A project may execute only through the endpoint and contract matching that type. Agent projects are isolated from one another even when owned by the same user.

## 8. Run Lifecycle

The normal lifecycle is:

```text
QUEUED → RUNNING → COMPLETED
                 ↘ FAILED
```

- `QUEUED`: request accepted and immutable execution snapshot recorded; work has not started.
- `RUNNING`: execution started and `started_at` is set.
- `COMPLETED`: requested processing finished, structured results passed required validation, and `completed_at` is set.
- `FAILED`: execution could not produce a valid completed result; `completed_at` and structured `errors` are set.

Cancellation, partial-success status, retry status, queue infrastructure, recovery after process interruption, and idempotency keys are intentionally not frozen in S0. Internal bounded correction attempts do not create new public status values.

## 9. Repeated Runs and Immutability

One standalone project may have many historical runs:

```text
AGP-001  BookEase Requirements
  ├─ RUN-001
  ├─ RUN-002
  └─ RUN-003
```

Each run is an immutable historical execution. Later edits to current project/input configuration and later runs must not overwrite a previous run's `input_snapshot`, selections, result references, warnings, errors, or timestamps. A user requests another run rather than mutating a terminal run.

Implementation may update lifecycle fields while a run moves from `QUEUED` to a terminal status. After terminalization, correction means creating a new run; retention/administrative policies remain an implementation concern.

## 10. Input Snapshot

`input_snapshot` contains the normalized or otherwise serializable request state required to understand how an output was generated, including the relevant agent inputs, selected mode, and execution configuration known at acceptance time.

It must:

- be stable for the historical run;
- preserve meaningful source metadata/references needed for audit and reproduction;
- avoid credentials, provider secrets, or unrelated sensitive data; and
- not require arbitrary raw binary data to be embedded in `agent_runs`.

Uploaded-file object/storage design, content hashing, extraction records, privacy retention, and binary lifecycle are later implementation decisions.

## 11. Output Manifest

`output_manifest` is the metadata/reference structure describing produced outputs. It should allow consumers to determine, as applicable:

- output code/type;
- display name and media/representation type;
- storage or artifact reference;
- production/validation state;
- size, checksum, or version metadata when adopted; and
- relationship to mandatory execution evidence.

S0 does not freeze the manifest's nested schema or require every large output body to be duplicated in one run document. Concrete artifact persistence and reference rules are finalized in S1 or the relevant agent implementation.

## 12. Warnings and Errors

`warnings` records non-fatal conditions, limitations, assumptions, skipped optional operations, and degraded but usable output. `errors` records structured failures and must use the applicable common category:

```text
INPUT_VALIDATION_FAILED
MODEL_EXECUTION_FAILED
STRUCTURED_OUTPUT_INVALID
TOOL_EXECUTION_FAILED
BUILD_FAILED
TEST_EXECUTION_FAILED
INTERNAL_ERROR
```

Not every category applies to every agent. The concrete nested warning/error item schema is open for S1/S2, but it must support safe user-facing explanation and diagnostic correlation without exposing secrets, private internals, or raw exceptions.

Errors must be returned in the common result envelope and retained with the run; server logs alone are insufficient.

## 13. Common `AgentRunResult` Envelope

Every execution/result endpoint uses this conceptual envelope:

| Field | Meaning |
|---|---|
| `run_id` | `RUN-###` execution identity. |
| `agent_project_id` | Parent `AGP-###`. |
| `agent_type` | Frozen specialist type. |
| `run_mode` | Frozen execution mode. |
| `status` | Current/terminal `AgentRunStatus`. |
| `selected_outputs` | User-requested valid output codes. |
| `started_at` | Execution start time when started. |
| `completed_at` | Terminal time when complete or failed. |
| `outputs` | Agent- and mode-specific structured results/evidence. |
| `warnings` | Structured non-fatal conditions. |
| `errors` | Structured failures. |

The envelope supports a reusable frontend processing state, run history, result shell, error handling, and download/export controls. Agent-specific contracts define the permitted selections and expectations for `outputs`.

## 14. Standalone/Integrated Separation

- `agent_projects` and `agent_runs` do not replace integrated `projects` or Shared Knowledge Base collections.
- Standalone status is not an integrated workflow stage.
- Standalone runs do not create H1–H5 Approval records.
- Standalone runs do not advance the Central SDLC Orchestrator.
- Standalone outputs do not automatically enter an integrated Project's Shared Knowledge Base or `traceability_links`.
- Standalone agents do not require upstream integrated artifacts; manual input adapters supply their context.
- A future explicit import/export workflow may map reviewed artifacts between modes, but no mapping or automatic synchronization is frozen here.

## 15. Intentionally Open Implementation Decisions

S1/S2 must decide concrete schema types/constraints, indexes, pagination, sorting, archival rules, execution idempotency, queue behavior, current-input persistence, nested manifest/error shapes, artifact/file storage, retention, export generation, provider configuration, and operational observability. Those decisions must preserve this contract's names, enums, isolation, ownership, immutability, and reusable-engine rules.
