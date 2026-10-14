# Standalone Agent Architecture

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Purpose and Two Supported Modes

AgileFlow AI ultimately supports two complementary usage modes. Progress Presentation 1 temporarily prioritizes Standalone Agent Mode so each reusable specialist can be developed and validated independently. This priority does not remove, replace, or redesign the integrated workflow.

### Integrated Multi-Agent Project Mode

The final coordinated research workflow remains:

```text
User
  → Project
  → Agent 1
  → H1
  → Agent 2
  → H2
  → Agent 4 pre-code
  → H3
  → Agent 3
  → H4
  → Agent 4 validation
  → H5
  → Completed
```

The Central SDLC Orchestrator controls this sequence. The Shared Knowledge Base, traceability, human approval gates, correction loops, and workflow events remain part of the integrated architecture.

### Standalone Agent Mode

The independent journey is:

```text
User
  → choose individual agent
  → create standalone agent project
  → provide manual inputs
  → select desired outputs
  → run selected agent
  → review/export results
  → modify inputs/run again
```

The four standalone choices are:

1. Agent 1 — Requirement Gathering and Analysis Agent
2. Agent 2 — Project Management and Design Agent
3. Agent 3 — Implementation and Git Automation Agent
4. Agent 4 — Testing, Validation and Security Agent

Each agent accepts its own manual inputs and does not require a previous agent to have run. For example, Agent 2 accepts user-supplied requirements or an SRS; it does not require Agent 1 execution.

## 2. Frozen Common Execution Model

```text
User Input
    ↓
Standalone Agent Project
    ↓
Agent-Specific Input Validation
    ↓
Normalized Agent Input Context
    ↓
Reusable Agent Engine
    ↓
AI Model / Rules / Tools
    ↓
Selected Output Generation
    ↓
Structured Result Validation
    ↓
Agent Run Result
    ↓
Results Workspace / Run History
```

Every standalone agent must:

- accept the required manual inputs defined by its contract;
- require the user to choose desired outputs;
- validate inputs and conditional requirements;
- normalize supplied data into a stable, agent-specific internal context;
- call the reusable specialist engine;
- persist planned standalone project/run information;
- validate and return structured results;
- support repeated runs without overwriting history; and
- expose warnings and errors in the common result envelope.

## 3. Layer Separation

The conceptual call direction is:

```text
Route
  → Standalone Project/Run Service
  → Agent Service
  → Agent Engine
  → Provider/Tool abstraction
```

- **Route:** authentication, request parsing, transport validation, status mapping, and response serialization.
- **Standalone Project/Run Service:** ownership enforcement, project lookup, run creation, lifecycle timestamps/status, snapshot and manifest persistence, and history retrieval.
- **Agent Service:** agent-specific validation, normalization, selected-output coordination, and result validation.
- **Agent Engine:** specialist reasoning and generation behavior that is reusable in either mode.
- **Provider/Tool abstraction:** model invocation and controlled tool execution.

Route/controller code must not contain AI reasoning and must not directly call a model vendor.

## 4. One Reusable Engine per Specialist

Each specialist agent has one reusable core engine. Separate `StandaloneAgent1` and `IntegratedAgent1` implementations, or equivalent duplicates for Agents 2–4, are prohibited.

```text
Standalone Manual Input Adapter
              ↓
       Common Agent Input
              ↓
        Reusable Agent Engine
```

Later integration uses:

```text
Integrated SKB Input Adapter
              ↓
       Common Agent Input
              ↓
        Same Agent Engine
```

Adapters handle source-specific retrieval and normalization. The engine owns the specialist behavior. This preserves independent validation now and coordinated reuse later.

## 5. Standalone and Integrated Isolation

Standalone mode must not:

- require global Project workflow stages;
- invoke H1–H5 automatically;
- create human `Approval` records automatically;
- advance or otherwise call the Central SDLC Orchestrator automatically;
- write outputs automatically to an integrated Project's Shared Knowledge Base;
- require previous specialist-agent execution; or
- represent standalone status as an integrated workflow stage.

Standalone `AgentProject` data, `AgentRun` data, identifiers, and history remain isolated from integrated `Project` data. Optional reviewed import/export between the modes may be designed later; v1.0 defines no automatic bridge.

## 6. Authentication and Ownership

Standalone mode reuses the existing authentication system. It must not introduce a second identity or authentication design.

Every standalone project and run carries `owner_user_id`. Authenticated users may create, list, read, update, or execute only their own standalone projects and may read only their own runs. A run must match both the owning user and its parent project.

## 7. Planned Common Storage

Two shared collections were planned by S0 and are implemented by S1:

- `agent_projects`
- `agent_runs`

There is one common project collection and one common run collection, not separate collections per specialist agent. Their semantics are frozen in [COMMON_AGENT_PROJECT_CONTRACT.md](COMMON_AGENT_PROJECT_CONTRACT.md). S1 implements shared persistence without a third standalone collection. Indexes, large-artifact persistence, upload storage, and retention remain later decisions.

These collections are the standalone workspace boundary. They do not replace or rename the integrated Project or Shared Knowledge Base collections.

## 8. Common Project, Run, and Result Types

The four exact `AgentType` values are:

```text
REQUIREMENTS
DESIGN_PLANNING
IMPLEMENTATION
TESTING_VALIDATION
```

Standalone project statuses are `ACTIVE` and `ARCHIVED`. Run statuses are `QUEUED`, `RUNNING`, `COMPLETED`, and `FAILED`. Run modes are `DEFAULT`, `TEST_GENERATION`, and `VALIDATION`; Agents 1–3 use `DEFAULT`, while Agent 4 uses one of its two explicit modes.

Projects use `AGP-###`. Runs use `RUN-###`.

The common result envelope is:

```text
run_id
agent_project_id
agent_type
run_mode
status
selected_outputs
started_at
completed_at
outputs
warnings
errors
```

`outputs` is agent-specific. The stable envelope enables shared processing, history, result, error, and export UI.

## 9. Mandatory Output Selection

Every standalone run explicitly records `selected_outputs`, and the user is not forced to request every supported artifact. Each agent contract freezes its allowed output codes.

An engine may still produce evidence that is technically mandatory for safe or honest execution. In particular, whenever Agent 3 generates executable source code it must return `BUILD_RESULT`, `EXECUTION_RESULT`, and `EXECUTION_LOGS`; these are mandatory evidence, not selectable generation codes.

## 10. Model and Tool Abstraction

S0 does not select or freeze an AI vendor:

```text
Agent Service
  → Agent Engine
  → ModelProvider interface
  → Selected model/provider
```

Agents may later use hosted LLMs, open-source/local models, code-focused models, speech-to-text models, deterministic rules, or controlled tools. Provider choice, credentials, fallback policy, prompts, and concrete interfaces are implementation decisions. Agent routes must never directly call OpenAI, Claude, Gemini, or another provider.

## 11. Common Error Principles

The shared error category vocabulary is:

```text
INPUT_VALIDATION_FAILED
MODEL_EXECUTION_FAILED
STRUCTURED_OUTPUT_INVALID
TOOL_EXECUTION_FAILED
BUILD_FAILED
TEST_EXECUTION_FAILED
INTERNAL_ERROR
```

Not every category applies to every agent or mode. Errors must be represented in `AgentRunResult.errors`, with safe diagnostic context, instead of existing only in server logs. Recoverable concerns that do not make the run fail belong in `warnings`. Secrets, credentials, and private raw content must not be exposed in either.

## 12. Export Direction

All agents should eventually support viewing, copying, and downloading/exporting results. Depending on artifact type, formats may include JSON, Markdown, PDF, or ZIP. S0 does not freeze a format for every output or its persistence implementation. Agent 3 runnable source should eventually be exportable as a project archive/workspace.

## 13. Research Boundary

### Normal software engineering foundation

- agent-project CRUD;
- authentication and owner isolation;
- forms and API routes;
- run lifecycle/history;
- storage and artifact references;
- results viewers; and
- download/export mechanics.

### Research-relevant work

- intelligent SDLC artifact generation;
- validated structured AI outputs;
- requirement quality engineering;
- design generation and planning intelligence;
- executable-code generation and bounded correction;
- automated test generation and validation;
- human interaction and clarification;
- later multi-agent coordination; and
- end-to-end traceability.

Standalone mode is useful product functionality and an experimental vehicle, but is not itself the principal research novelty.

## 14. Shared Foundation and Parallel Ownership

Agent members must not independently recreate authentication, agent-project management, run lifecycle/history, the common result envelope, common statuses, the output-selector shell, or the common frontend processing/results shell. Those are shared standalone-foundation responsibilities.

After S0 and common S1/S2 foundations:

| Member branch | Specialist ownership |
|---|---|
| `feature/agent-requirements` | Agent 1 inputs, normalization, engine, model/tool interaction, outputs, tests, and agent-specific UI content |
| `feature/agent-design-planning` | Agent 2 inputs, normalization, engine, model/tool interaction, outputs, tests, and agent-specific UI content |
| `feature/agent-implementation` | Agent 3 inputs, normalization, engine, model/tool interaction, outputs, tests, and agent-specific UI content |
| `feature/agent-testing-validation` | Agent 4 inputs, normalization, engine, model/tool interaction, outputs, tests, and agent-specific UI content for both modes |

Members consume the shared foundation and do not redefine it. Changes to a frozen shared or cross-member contract require team agreement.

The implemented specialist source layout is feature-oriented:

| Responsibility | Backend | Frontend |
|---|---|---|
| Shared project/run lifecycle | `backend/app/modules/standalone/` | shared project service and generic components under `frontend/src/services/` and `frontend/src/components/agents/` |
| Standalone Agent 1 | `backend/app/modules/agents/requirements/` | `frontend/src/features/agents/requirements/` |
| Standalone Agent 2 | `backend/app/modules/agents/design_planning/` | `frontend/src/features/agents/designPlanning/` |
| Standalone Agent 4 | `backend/app/modules/agents/testing_validation/` | `frontend/src/features/agents/testingValidation/` |

`backend/app/modules/requirements/` remains the integrated requirement artifact,
H1 publication, and Shared Knowledge Base domain; it is not the standalone Agent 1
engine. `backend/app/modules/agents/implementation/` is reserved for future Agent 3
work and is intentionally absent. The dependency direction is specialist packages to
the shared standalone foundation, never the reverse.

## 15. Progress Presentation 1 Target — October 23

The intended milestone is:

- shared platform foundation: implemented;
- standalone foundation: implemented;
- Agent 1: working standalone MVP;
- Agent 2: working standalone MVP;
- Agent 3: reserved for future implementation; no backend or frontend specialist package exists;
- Agent 4 `TEST_GENERATION`: working standalone MVP;
- Agent 4 `VALIDATION`: working standalone MVP; and
- full integrated multi-agent workflow: shared infrastructure established, with full specialist integration continuing after Progress Presentation 1.

The milestone must not be described as completion of the full integrated workflow.

## 16. S0 Scope

This document freezes architecture only. It creates no backend or frontend implementation, collection, schema, route, dependency, model integration, RAG behavior, Orchestrator change, Shared Knowledge Base behavior change, or integrated-workflow change.
