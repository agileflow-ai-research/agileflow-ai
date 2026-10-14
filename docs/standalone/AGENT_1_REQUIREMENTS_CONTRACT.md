# Agent 1 — Requirement Gathering and Analysis Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Agent type: `REQUIREMENTS`

Run mode: `DEFAULT`
Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Standalone Purpose

Agent 1 — Requirement Gathering and Analysis Agent lets a user manually supply requirement-source information and select the requirement-engineering artifacts to generate. It validates and normalizes those sources before using the one reusable Agent 1 engine.

It does not require an integrated Project or invoke H1 in standalone mode.

## 2. Basic and Context Inputs

### Required basic inputs

```text
project_name
domain
```

At least one requirement source is also required.

### Requirement source types

```text
TEXT
DOCUMENT
AUDIO
VIDEO
LIVE_INTERVIEW
```

One run may conceptually include one or more supported sources. Agent-specific validation must confirm that at least one source is usable, not merely declared.

### Optional contextual inputs

```text
background_context
business_goals
known_constraints
existing_requirements
additional_notes
```

Normalization must preserve useful provenance/source references while avoiding arbitrary binary embedding in `agent_runs`.

## 3. Progress Presentation 1 Input Priority

| Source | Priority/claim boundary |
|---|---|
| `TEXT` | **MUST WORK** |
| `DOCUMENT` | **SHOULD WORK if feasible** |
| `AUDIO` | **SECONDARY** |
| `VIDEO` | **SECONDARY** |
| `LIVE_INTERVIEW` | **LATER PHASE** |

Implementations and presentations must not claim unsupported multimodal capabilities are complete. A listed contract source type expresses the intended interface boundary, not proof that its ingestion pipeline has been implemented.

## 4. Selectable Output Codes

The allowed Agent 1 `selected_outputs` values are exactly:

```text
FUNCTIONAL_REQUIREMENTS
NON_FUNCTIONAL_REQUIREMENTS
USER_STORIES
ACCEPTANCE_CRITERIA
PERSONAS
QUALITY_FINDINGS
CLARIFICATION_QUESTIONS
SRS
```

The selection must be non-empty. Agent 1 must not silently rename these codes in API, persistence, engine, or UI layers.

## 5. Output Expectations

| Output code | Structured expectation |
|---|---|
| `FUNCTIONAL_REQUIREMENTS` | A structured list of system behaviors/capabilities with stable identities or references suitable for later traceability. |
| `NON_FUNCTIONAL_REQUIREMENTS` | Structured quality attributes, constraints, and measurable targets where supported by the input. |
| `USER_STORIES` | Stories structured around actor, goal, and benefit. |
| `ACCEPTANCE_CRITERIA` | Testable criteria linked in the standalone result context to relevant stories or requirements. |
| `PERSONAS` | Personas oriented around role, goals, pain points, and context; they must not invent sensitive real-person profiles. |
| `QUALITY_FINDINGS` | Structured requirement-quality issues with affected context and a useful explanation or suggested clarification. |
| `CLARIFICATION_QUESTIONS` | Questions that require human response before or after refinement, linked to the uncertainty that caused them where possible. |
| `SRS` | A structured Software Requirements Specification generated from the available validated requirement context. |

`QUALITY_FINDINGS` includes exactly these finding categories:

```text
AMBIGUITY
MISSING_INFORMATION
CONFLICT
DUPLICATE
INCONSISTENCY
```

Selecting `SRS` does not justify inventing missing facts. Assumptions, unresolved issues, and clarification needs must remain visible through outputs or warnings.

## 6. Validation and Normalization

Before engine execution, Agent 1 must:

1. require `project_name` and `domain`;
2. require at least one usable source;
3. reject unsupported/unavailable source processing honestly rather than pretending it succeeded;
4. validate that every selected output code is from the exact Agent 1 list;
5. normalize text and extracted source content into an Agent 1 input context with provenance; and
6. preserve the serializable execution state in `input_snapshot`.

Concrete source size, type, extraction, upload, privacy, and malware-scanning limits belong to implementation planning.

## 7. Intended Human Clarification Loop

The future standalone refinement pattern is:

```text
input
  → analyze
  → detect uncertainty
  → produce clarification questions
  → user responds
  → run/refinement
  → generate revised outputs
```

Each refinement is represented by another immutable `RUN-###`; it does not overwrite the prior run. Exact conversational/session representation is open for S1/S2.

Standalone clarification and review do not require or create integrated H1 Approval. Importing an approved standalone package into an integrated Project is a future optional workflow.

## 8. Results and Errors

Agent 1 returns its selected structured outputs inside the common `AgentRunResult.outputs`. Applicable error categories include `INPUT_VALIDATION_FAILED`, `MODEL_EXECUTION_FAILED`, `STRUCTURED_OUTPUT_INVALID`, `TOOL_EXECUTION_FAILED`, and `INTERNAL_ERROR`. Limitations or unresolved ambiguity that still permits useful output belongs in `warnings`.

## 9. Isolation and Reuse

The standalone manual-input adapter and future integrated Shared Knowledge Base adapter both normalize to the common Agent 1 engine input. There must not be separate standalone and integrated reasoning implementations. Standalone execution neither writes to the integrated Shared Knowledge Base nor advances the Orchestrator or H1.
