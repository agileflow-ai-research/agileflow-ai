# Agent 3 — Implementation & Git Automation Agent

**Project:** AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile
SDLC Automation

**Mode:** Standalone Agent Mode

- **Status date:** 2026-10-20
- **Branch audited:** `feature/agent-implementation`
- **Milestone:** DOC-R1 documentation baseline after REFACTOR-R1
- **Scope:** current standalone Agent 3 implementation only

**Purpose:** Summarize the current implemented Agent 3 architecture, workflow,
technical pipeline, HITL controls, APIs, UI, testing evidence, limitations, and
future work.

## 1. Purpose and status vocabulary

This document is the source of truth for what Agent 3 — Implementation and Git
Automation Agent — does **today**. It complements the normative
[Agent 3 Implementation Contract](AGENT_3_IMPLEMENTATION_CONTRACT.md), which also
describes the intended end state.

- **Implemented:** available in the current frontend and backend and covered by
  automated tests and/or the completed UAT flow.
- **Partially implemented:** a usable slice exists, but the capability implied
  by the workflow or contract is incomplete.
- **Future:** not implemented. A visible roadmap node is not a backend capability.

The present milestone ends after a human approves an immutable AgentRun snapshot
that is ready for a future generator. Agent 3 does **not** yet generate source
code, build it, execute it, correct it, or deliver it to Git.

## 2. Executive summary

Agent 3 currently provides a human-in-the-loop preparation pipeline for turning
manually supplied project sources into an approved, traceable implementation
handoff. It accepts text, supported documents, and images; extracts and chunks
supported textual documents; applies rule-based and local zero-shot
classification; requires human verification; derives deterministic canonical
artifacts; optionally proposes grounded semantic additions with local Qwen;
consolidates reviewed sources into a trusted project specification; detects a
deliberately narrow set of conflicts; evaluates implementation readiness;
supports explicit continuation through warnings; optionally creates and binds a
new GitHub repository; and records final approval as an immutable AgentRun.

```text
Sources -> extraction -> chunking -> classification -> human verification
        -> canonical + semantic review -> project consolidation/conflict review
        -> trusted specification -> readiness/warning approval -> final approval
        -> immutable READY_FOR_GENERATION AgentRun
```

Everything after `READY_FOR_GENERATION` is future work.

### Agent 3 responsibility

In simple terms, Agent 3 receives software specifications, determines whether
enough trustworthy implementation information exists, obtains the required human
decisions, and prepares an immutable approved implementation run. Future phases
will use that approved run to generate, execute, correct, and deliver software.

Technically, Agent 3 converts heterogeneous, project-scoped sources into a
fingerprint-bound evidence graph. Deterministic services and local model
providers propose classifications and structured artifacts; human gates decide
uncertain or consequential facts; consolidation creates the trusted project
specification; readiness binds that specification to the selected outputs and
supported stack; and final approval copies the complete current evidence into an
immutable AgentRun snapshot.

## 3. Contract versus current implementation

The [contract](AGENT_3_IMPLEMENTATION_CONTRACT.md) defines the target Agent 3
outcome as a runnable implementation with honest build and execution evidence,
a bounded correction loop, and eventual Git delivery. The current implementation
delivers the preparation and approval foundation for that target, not the target
itself.

| Contract or planning concept | Current implementation |
| --- | --- |
| Generate selected implementation outputs | Selection is captured and approved; no files are generated. |
| Mandatory `BUILD_RESULT`, `EXECUTION_RESULT`, and `EXECUTION_LOGS` for executable output | Future; there is no build or execution engine. |
| Bounded correction loop | Future. |
| Git commit/push/delivery | Future; repository setup is implemented only. |
| `POST .../{agent_project_id}/run` in the shared planning contract | The current API uses `POST .../{agent_project_id}/runs`; see the API inventory. |
| Shared AgentRun result containing generated artifacts | The current AgentRun is an immutable approval snapshot with operational status `QUEUED` and Agent 3 snapshot status `READY_FOR_GENERATION`. No worker consumes it. |

The older shared architecture document still contains historical “reserved for
future implementation” wording for Agent 3. The code and this status document
supersede that historical implementation-status statement; the shared documents
remain useful for cross-agent architectural intent.

## 4. Workflow status matrix

The canvas has exactly nine fixed nodes and eight fixed directed edges.

| # | Node and status | Input | Automated action | Human action | Output |
| ---: | --- | --- | --- | --- | --- |
| 1 | **Project & Sources — IMPLEMENTED** | Project identity; manual text; supported documents/images | Validate, identify, hash, and persist project-scoped sources | Supply specifications, remove unwanted sources, select desired outputs | Prepared, traceable project input set and output selection |
| 2 | **Input Analysis — IMPLEMENTED** | Current project source set | Extract/normalize, chunk, run rules and DeBERTa, combine evidence, report preparation state | Observe progress; no classification decision is made in this node | Analysis candidates and evidence ready for verification |
| 3 | **Specification Verification — IMPLEMENTED** | Analysis candidates and source evidence | Build review queues, canonical artifacts, grounded semantic proposals, consolidation, and deterministic conflicts | Accept/relabel/exclude/add labels; review semantic proposals; resolve conflicts | Trusted source artifacts and `TrustedProjectSpecification` |
| 4 | **Implementation Readiness — IMPLEMENTED** | Current trusted specification and selected outputs | Apply trusted readiness policy and supported-stack rules | Approve stack adaptation where offered; explicitly continue through warnings | Current trusted readiness and any valid continuation decision |
| 5 | **Delivery Setup — IMPLEMENTED FOR SETUP ONLY** | Readiness-approved project and optional GitHub choice | Validate GitHub App installation; create/bind one new empty repository; expose safe metadata | Connect GitHub and create a repository, or skip delivery setup | Safe delivery destination snapshot or explicit skipped choice |
| 6 | **Generate Implementation — PARTIALLY IMPLEMENTED** | Trusted specification, readiness, output selection, delivery choice | Validate current fingerprints and build immutable run snapshot | Give final implementation approval | `READY_FOR_GENERATION` AgentRun; no generated code |
| 7 | **Build & Execute — FUTURE** | Future generated workspace | None today | None today | No current output |
| 8 | **Correction & Validation — FUTURE** | Future build/runtime/test evidence | None today | None today | No current output |
| 9 | **Delivery — FUTURE** | Future verified implementation and delivery destination | None today | None today | No branch, commit, push, PR, or archive |

## 5. Inputs and selected outputs

### 5.1 Input types

The API models three input source types:

| Type | Current behavior |
| --- | --- |
| `TEXT` | Manual project source, normalized into traceable preparation input |
| `DOCUMENT` | Server-validated and extracted from `.pdf`, `.docx`, `.txt`, `.md`, `.json`, `.yaml`, or `.yml` |
| `IMAGE` | Accepted as `.png`, `.jpg`, `.jpeg`, or `.webp`, but analysis is pending and it cannot count as understood context |

Documents are limited to 10 MiB and images to 5 MiB. Uploads are streamed in
64 KiB chunks. Image understanding and OCR are not implemented.

### 5.2 Selectable output codes

The accepted `selected_outputs` values are exactly:

- `PROJECT_STRUCTURE`
- `FRONTEND_CODE`
- `BACKEND_CODE`
- `DATABASE_IMPLEMENTATION`
- `API_IMPLEMENTATION`
- `CONFIGURATION_FILES`
- `CONTAINER_CONFIGURATION`
- `GIT_SUMMARY`

These values are selected before implementation readiness and final approval.
They define the approved future-generation request; they do not mean the
corresponding output has already been generated.

## 6. Document extraction

Extraction is format-aware and preserves source provenance:

- PDF extraction preserves page references and is limited to 500 pages.
- DOCX extraction preserves headings, paragraphs, and table structure; ZIP
  safety limits include at most 10,000 entries and 50 MiB uncompressed content.
- Markdown preserves heading and fenced-code structure.
- Plain text preserves line-oriented provenance.
- JSON and YAML preserve structured paths.
- Extracted content is capped at 2,000,000 characters.

There is no OCR. A scanned or raster-only PDF with no extractable text fails
honestly rather than being presented as understood. Extraction results are
persisted as sidecars and can be retried through the existing `force` query
mechanism without changing source identity.

The manual procedure is recorded in
[Agent 3 Document Extraction UAT](AGENT_3_DOCUMENT_EXTRACTION_UAT.md). The
completed Agent 3 UAT validated the implemented extraction and review flow.

## 7. Chunking

Chunking is deterministic and section-aware. Version 1 targets 350 lexical
tokens, caps a chunk at 500, prefers a minimum of 80, and overlaps by 60 tokens.
At most 2,000 chunks are produced per document.

Chunk boundaries understand PDF pages, DOCX headings/tables, Markdown headings
and code fences, plain-text lines, and JSON/YAML structured paths. Stable `CHK`
identities incorporate source/upload identity, source digest, chunking version,
ordinal, text digest, and provenance. Reprocessing identical content preserves
traceability instead of manufacturing unrelated review identities.

## 8. Classification taxonomy and model

Both classifiers use this 13-label taxonomy:

1. `FUNCTIONAL_REQUIREMENTS`
2. `NON_FUNCTIONAL_REQUIREMENTS`
3. `USER_STORIES`
4. `ACCEPTANCE_CRITERIA`
5. `SYSTEM_ARCHITECTURE`
6. `DATABASE_SCHEMA`
7. `API_SPECIFICATION`
8. `UI_FLOW`
9. `TECHNOLOGY_STACK`
10. `TECHNICAL_CONSTRAINTS`
11. `IMPLEMENTATION_TASKS`
12. `TEST_CASES`
13. `OTHER_CONTEXT`

The rule detector uses deterministic catalogs and produces inspectable evidence.
The local zero-shot model is exactly
`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, pinned to revision
`6f5cf0a2b59cabb106aca4c287eed12e357e90eb`. It runs through Transformers and is
CPU-capable; no external inference API is required.

The zero-shot classifier scores labels independently. Its policy uses strong
(`0.80`), moderate (`0.60`), and weak/display (`0.50`) thresholds, a top-label
margin of `0.08`, and an explosion guard when four or more labels reach the
moderate threshold. At most four labels are displayed.

This model is experimental and not calibrated as a source of truth. UAT observed
overclassification/label explosion on some inputs. The hybrid policy deliberately
routes ambiguity to a human rather than treating confidence as verified meaning.

The project-wide automated preparation path is:

```text
source -> extraction/normalization -> chunking -> rule classifier
       -> DeBERTa zero-shot classifier -> conservative hybrid decision
```

Hybrid evidence states are `RULE_AND_MODEL`, `RULE_ONLY`, `MODEL_ONLY`,
`RULE_MODEL_DISAGREEMENT`, and `INSUFFICIENT_EVIDENCE`. Decision states are
`AUTO_CANDIDATE`, `REVIEW_REQUIRED`, and `REJECTED`. Human truth is authoritative.

## 9. Human verification workflow

Classification review actions are exactly `ACCEPT`, `RELABEL`, `EXCLUDE`, and
`ADD_LABEL`. Chunk review progresses through `UNREVIEWED`, `IN_REVIEW`, and
`VERIFIED`; document review progresses through `NOT_STARTED`, `IN_PROGRESS`, and
`COMPLETE`. Optional reviewer notes are limited to 500 characters.

Review decisions are persisted and bind to stable chunk/source evidence. The UI
provides a guided review queue, progress summaries, source context, classification
evidence, and explicit next-step barriers. Transient card/modal selection is
presentation state; the authoritative human decision is backend state.

The guided flow exposes **Review Now**, focuses one source, shows completed and
remaining progress, offers **Review Next Source**, and continues automatically
only after the backend confirms completion. Required verification is a hard
barrier: downstream trusted-artifact work cannot use an unverified candidate.

Preparation project statuses are `NOT_STARTED`, `RUNNING`, `WAITING_FOR_HUMAN`,
`ANALYSIS_READY`, `PARTIAL_FAILURE`, and `FAILED`. Per-source statuses are
`QUEUED`, `EXTRACTING`, `CHUNKING`, `CLASSIFYING_RULES`, `CLASSIFYING_MODEL`,
`BUILDING_HYBRID`, `WAITING_FOR_HUMAN`, `READY`, `FAILED`, and `SKIPPED`.

Preparation stages are `TEXT_NORMALIZATION`, `EXTRACTION`, `CHUNKING`,
`RULE_CLASSIFICATION`, `MODEL_CLASSIFICATION`, `HYBRID`, and `HUMAN_REVIEW`.
For workflow progression, both `ANALYSIS_READY` and `WAITING_FOR_HUMAN` mean the
automated Input Analysis work is complete; the HITL gate belongs to the following
review interaction rather than being hidden in canvas logic.

## 10. Canonical artifacts

Canonical extraction deterministically maps verified evidence into typed
artifacts for requirements, user stories, acceptance criteria, architecture,
database schema, API specification, UI flow, technology stack, constraints,
implementation tasks, tests, and other context.

Artifact status is `COMPLETE`, `PARTIAL`, or `UNRESOLVED`. Each artifact retains
source/chunk provenance. Deterministic construction remains separate from
semantic enrichment so a model cannot silently rewrite the reviewed baseline.

## 11. Semantic extraction and review

Semantic enrichment uses exactly `Qwen/Qwen3-1.7B`, pinned to revision
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`. It runs through a provider adapter
on CPU or CUDA with `enable_thinking=False`; hidden reasoning is neither requested
nor stored.

Only `PARTIAL` or `UNRESOLVED` canonical artifacts are candidates. `COMPLETE`
artifacts are `SKIPPED_COMPLETE`; `OTHER_CONTEXT` is skipped where the workflow
does not apply. Prompts are source-grounded and request one strict JSON object.
The adapter permits at most two attempts, with a 4,096-token input limit and a
2,048-token output limit.

Semantic output is a proposal, never automatically trusted. Review actions are
`APPROVE_ADDITION`, `REJECT_ADDITION`, `KEEP_DETERMINISTIC`, and
`ACCEPT_SEMANTIC_OVERRIDE`. Final trusted field origins are `DETERMINISTIC`,
`SEMANTIC_HUMAN_APPROVED`, and `SEMANTIC_HUMAN_OVERRIDE`. Preview data may call a
candidate `DETERMINISTIC` or `SEMANTIC`, but only a human promotes semantic data.

Specification statuses are `NOT_STARTED`, `WAITING_FOR_ARTIFACT_REVIEW`,
`PREPARING_SPECIFICATION`, `WAITING_FOR_SEMANTIC_REVIEW`, `SPECIFICATION_READY`,
`PARTIAL_FAILURE`, and `FAILED`.

### Trusted source artifact layers

The system keeps three representations separate:

1. the deterministic canonical baseline;
2. a semantic merged preview with exact evidence; and
3. the final human-approved trusted source artifact.

This separation makes model influence visible, preserves the reproducible
baseline, supports audit/research comparison, retains source traceability, and
allows digests to reject decisions made against stale data.

## 12. Project consolidation and conflict review

Consolidation combines trusted per-source artifacts through exact deduplication,
supporting-source aggregation, and conflict detection while retaining evidence
and source identities. Its statuses are `NOT_STARTED`,
`CONSOLIDATING`, `WAITING_FOR_HUMAN`, `READY`, `PARTIAL_FAILURE`, `FAILED`, and
`STALE`.

Conflict detection is intentionally narrow and explainable. It finds:

- `TECHNOLOGY_SELECTION` conflicts for `TECHNOLOGY_STACK` database or API-style
  categories;
- `EXPLICIT_ID_MISMATCH` when API specifications, functional requirements, or
  non-functional requirements share an explicit ID but disagree; and
- `DATABASE_FIELD_TYPE` when the same entity and field have different types.

It is not a general semantic contradiction detector. Human actions are
`SELECT_CANDIDATE`, `KEEP_BOTH`, `MARK_NOT_CONFLICTING`, and
`EXCLUDE_CANDIDATE`. A reviewer cannot introduce an arbitrary replacement fact;
decisions operate only on candidates known to the server. The trusted project
specification is digest-bound to its reviewed inputs and decisions. Only a
current `READY` specification may proceed to trusted readiness.

## 13. Readiness and stack adaptation

Trusted readiness status is `READY`, `READY_WITH_WARNINGS`, or `NOT_READY`.
Policy and schema version 1 normalize the trusted specification, apply
deterministic rules, and produce a stable readiness fingerprint.

Readiness consumes only the current trusted project specification. Raw sources,
unverified labels, and unapproved semantic suggestions cannot satisfy a rule.

| Layer | Supported PP1 choice |
| --- | --- |
| Frontend | React + Vite |
| Styling | Plain CSS |
| Backend | Node.js + Express.js |
| Database | MySQL |
| Language | JavaScript |
| API style | REST |

For unsupported choices, the implementation-plan decision can be
`ADAPT_TO_SUPPORTED_STACK`. This does not mutate the trusted specification; it
records how a future generator must interpret it.

A `READY_WITH_WARNINGS` result remains a warning result. Explicit continuation
is stored separately and binds project/specification identities and digests,
selected-output digest, policy version, readiness fingerprint, and warning set.
A stale or mismatched continuation cannot unlock approval.

## 14. Delivery setup and GitHub boundary

GitHub integration uses a GitHub App, not personal access tokens. It supports a
personal GitHub user account, validates the installation, and can create and bind
exactly one **new** repository per project. Selecting an existing repository is
not implemented. New repositories use `auto_init=false` and are empty.

GitHub App JWTs and installation tokens are ephemeral and not stored. Persisted
and API-visible data is safe allow-listed metadata. Delivery setup may be skipped,
and GitHub is not a prerequisite for final AgentRun approval.

There is no branch creation, file write, commit, push, pull request, release, or
archive delivery. See
[Agent 3 GitHub Repository Setup](AGENT_3_GITHUB_REPOSITORY_SETUP.md).

## 15. AgentRun handoff and approval boundary

Final approval creates an immutable shared AgentRun snapshot containing:

- project-specification identity, source-set digest, decision digest, and the
  complete trusted project specification;
- readiness identity, policy version, status, fingerprint, and the complete
  trusted readiness snapshot;
- selected outputs and their stable digest;
- implementation stack and optional stack-adaptation decision;
- reviewer approval and warning-continuation binding when required;
- a safe delivery snapshot; and
- traceability root references.

Approval is idempotent for the same bound evidence. The Agent 3 snapshot status
is `READY_FOR_GENERATION`. The shared operational AgentRun status remains
`QUEUED`; no generator worker consumes it. Create, list, and get are supported.
Update, delete, execute, retry, and result endpoints are not.

Copying complete validated snapshots is essential: live sources, reviews,
specifications, readiness, or repository setup can change later, but the
historical approval must remain reproducible and auditable.

### Human-in-the-loop gates

| Stage | Why a human is needed | Decision | Downstream effect |
| --- | --- | --- | --- |
| Classification review | Rules/model evidence can be ambiguous or excessive | `ACCEPT`, `RELABEL`, `EXCLUDE`, `ADD_LABEL` | Establishes trusted chunk labels; required review blocks trusted artifacts |
| Semantic review | Qwen proposals may add or alter meaning | Approve/reject addition, keep deterministic, or accept override | Determines final trusted source fields |
| Cross-source conflict review | Server-known sources disagree | Select candidate, keep both, mark non-conflict, or exclude candidate | Allows trusted project specification completion |
| Readiness warning continuation | A warning requires informed risk acceptance | **Continue With Warnings** | Preserves raw `READY_WITH_WARNINGS` and unlocks downstream only while the binding is current |
| Delivery choice | Repository setup is optional and user-owned | Connect/create repository or skip | Captures safe destination state; does not deliver code |
| Final implementation approval | The complete handoff is consequential | Explicit approval with an idempotency key | Creates one immutable AgentRun snapshot |

A required gate is a hard workflow barrier. No dependent stage may execute until
the server validates the decision against current identities, evidence, and
fingerprints.

### Automation versus human responsibility

| Automated by Agent 3 | Human controlled |
| --- | --- |
| File validation, extraction, normalization, and chunking | Supplying/removing sources and choosing outputs |
| Rule and zero-shot classification evidence | Uncertain classification truth |
| Conservative hybrid decisions and review queues | Semantic additions and overrides |
| Deterministic canonical extraction | Cross-source conflict resolution |
| Grounded local semantic fallback | Stack adaptation and warning continuation |
| Exact deduplication, aggregation, and conflict candidates | Delivery setup choice |
| Readiness evaluation and fingerprint construction | Final implementation approval |

### Raw subsystem state versus effective workflow state

Raw subsystem state reports what a service has persisted. Effective workflow
state additionally applies upstream gates and is what the UI uses to present a
node as blocked, available, active, or complete. For example, GitHub may already
be configured in raw delivery state, but Delivery Setup remains effectively
blocked while readiness warning approval is unresolved. Likewise, moving a
canvas node changes neither raw state nor effective workflow order.

This distinction prevents a later subsystem from bypassing a current upstream
human decision.

## 16. API inventory

All routes are under `/api/v1/agents/implementation`.

### GitHub setup

- `GET /github/install-callback`
- `GET /github/oauth-callback`
- `POST /{agent_project_id}/github/connect`
- `GET /{agent_project_id}/github/connection`
- `GET /{agent_project_id}/github/repository`
- `POST /{agent_project_id}/github/repository`

### Inputs, extraction, and classification

- `POST /{agent_project_id}/input-files`
- `DELETE /{agent_project_id}/input-files/{upload_id}`
- `POST /{agent_project_id}/input-files/{upload_id}/extract`
- `GET /{agent_project_id}/input-files/{upload_id}/extraction`
- `POST|GET /{agent_project_id}/input-files/{upload_id}/chunks`
- `POST|GET /{agent_project_id}/input-files/{upload_id}/rule-detections`
- `POST|GET /{agent_project_id}/input-files/{upload_id}/zero-shot-detections`
- `POST|GET /{agent_project_id}/input-files/{upload_id}/hybrid-detections`
- `GET /{agent_project_id}/input-files/{upload_id}/human-reviews`
- `PUT /{agent_project_id}/input-files/{upload_id}/human-reviews/{chunk_id}`

### Artifacts and semantic review

- `POST|GET /{agent_project_id}/input-files/{upload_id}/canonical-artifacts`
- `POST|GET /{agent_project_id}/input-files/{upload_id}/semantic-artifacts`
- `GET /{agent_project_id}/input-files/{upload_id}/semantic-reviews`
- `PUT /{agent_project_id}/input-files/{upload_id}/semantic-reviews/{decision_id}`
- `GET /{agent_project_id}/input-files/{upload_id}/trusted-artifacts`

### Preparation, specification, consolidation, and readiness

- `POST /{agent_project_id}/preparation/start`
- `GET /{agent_project_id}/preparation/status`
- `POST /{agent_project_id}/specification/start`
- `GET /{agent_project_id}/specification/status`
- `POST /{agent_project_id}/project-specification/start`
- `GET /{agent_project_id}/project-specification/status`
- `GET /{agent_project_id}/project-specification`
- `GET /{agent_project_id}/project-specification/conflicts`
- `PUT /{agent_project_id}/project-specification/conflicts/{conflict_id}`
- `POST /{agent_project_id}/readiness/evaluate` (legacy-compatible)
- `POST /{agent_project_id}/trusted-readiness/evaluate`
- `GET /{agent_project_id}/trusted-readiness`
- `POST /{agent_project_id}/trusted-readiness/continue`

`/specification/*` coordinates per-source specification preparation;
`/project-specification/*` coordinates cross-source consolidation.

### AgentRun

- `POST /{agent_project_id}/runs`
- `GET /{agent_project_id}/runs`
- `GET /{agent_project_id}/runs/{run_id}`

## 17. Persistence and sidecar formats

The pipeline uses JSON sidecars under the Agent 3 project boundary. Shared
infrastructure provides path containment, safe Pydantic loading, stable
canonical-JSON SHA-256 digests, and atomic writes through same-directory `.part`
files followed by replacement. Domain modules define fingerprint payloads.

`infrastructure/sidecar.py` owns containment, safe sidecar model loading, and
atomic JSON persistence. `infrastructure/digests.py` owns the deterministic
canonical-JSON hashing primitive. Readiness, specification, review, and run
domains deliberately retain their own fingerprint-payload construction so a
generic helper cannot erase domain meaning.

Per-upload names are:

- `{upload_id}.metadata.json` and stored original `{upload_id}{extension}`
- `{upload_id}.extracted.json`
- `{upload_id}.chunks.json`
- `{upload_id}.rule-detections.json`
- `{upload_id}.zero-shot-detections.json`
- `{upload_id}.hybrid-detections.json`
- `{upload_id}.human-reviews.json`
- `{upload_id}.canonical-artifacts.json`
- `{upload_id}.semantic-artifacts.json`
- `{upload_id}.semantic-reviews.json`
- `{upload_id}.trusted-artifacts.json`

Project-level names are `preparation.json`, `specification.json`,
`project-consolidation.json`, `trusted-project-specification.json`,
`implementation-readiness.json`, and
`implementation-readiness-continuation.json`.

AgentRuns use the shared MongoDB `agent_runs` collection. GitHub connections and
repository bindings use dedicated MongoDB persistence. No migration is required.

## 18. Security and integrity guarantees

- Upload IDs are server-generated UUID identities with the `A3UP-` prefix.
- Normalized filenames are bounded and extension allow-listed.
- PDF, PNG, JPEG, WEBP, and DOCX signatures/structure are validated.
- Text rejects NUL content and requires UTF-8; JSON is parsed.
- Stored content has a SHA-256 identity and is rechecked before processing.
- File paths must remain inside the owning Agent 3 project directory.
- Project ownership is checked at the API boundary.
- Source, artifact, decision, specification, readiness, continuation, and run
  fingerprints prevent stale decision reuse.
- Atomic sidecar writes clean up failed temporary writes.
- GitHub tokens, local paths, stack traces, and model internals are not exposed.
- Authenticated owner/reviewer identity is taken from the server-side request
  context rather than accepted as an arbitrary storage identity.
- No generated program, dependency installer, shell command, or arbitrary code
  is executed at the current milestone.
- Human decisions remain required at the applicable classification, semantic,
  conflict, warning-continuation, and final-approval boundaries.

### Traceability chain

```text
Source -> Chunk -> Rule/model evidence -> Human classification
       -> Canonical artifact -> Semantic evidence/review
       -> Trusted source artifact -> TrustedProjectSpecification
       -> Trusted readiness/continuation -> AgentRun
```

Stable identities, provenance references, canonical digests, and immutable
snapshots connect each step. This is the current Agent 3 contribution to
end-to-end AgileFlow traceability; it establishes the roots a future generator
must carry into files, build evidence, and delivery metadata.

### Local AI models

| Purpose | Model and pinned revision | Execution | Role | Trust level |
| --- | --- | --- | --- | --- |
| Chunk classification | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` at `6f5cf0a2b59cabb106aca4c287eed12e357e90eb` | Local Hugging Face/Transformers; CPU-capable | Produces a 13-label score vector for hybrid evidence | Advisory; never final truth |
| Grounded semantic fallback | `Qwen/Qwen3-1.7B` at `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` | Local Transformers on CPU/CUDA; strict JSON; `enable_thinking=False` | Proposes evidence-backed completion of partial/unresolved artifacts | Proposal; deterministic baseline remains authoritative until HITL approval |

Neither model is allowed to directly establish trusted project truth.

### Research-Relevant Contributions

Candidate research contributions embodied by the current implementation include:

- hybrid deterministic, zero-shot, and HITL artifact understanding;
- separate deterministic, semantic-preview, and human-trusted representations;
- evidence-grounded local semantic fallback without external inference;
- hard, fingerprint-bound human gates inside an automated preparation pipeline;
- auditable cross-source consolidation into a trusted specification;
- immutable approved implementation snapshots; and
- a pause/resume workflow and traceability design from source evidence toward
  future generated code.

These are candidate contributions for evaluation, not claims of world-first
novelty. React, FastAPI, MongoDB, and GitHub App integration are enabling
engineering rather than research novelty.

## 19. Frontend architecture after REFACTOR-R1

Feature root: `frontend/src/features/agents/implementation/`.

```text
implementation/
|-- pages/          page entry, overview, visible modal/navigation ownership
|-- canvas/         graph, positions, arrange/reset, drag, floating edges
|-- workflow/       node definitions, effective state, gates, progression
|-- panels/         node-specific interactions and modal shell
|-- components/     analysis/canonical/review/readiness presentation
|   `-- common/     repeated workflow semantics
|-- hooks/          focused GitHub delivery-setup coordination
|-- services/       all Agent 3 HTTP calls
|-- constants/      stable workflow and domain values
|-- utils/          presentation, source, workspace, navigation helpers
|-- nodes/          reusable workflow node renderer
`-- ImplementationWorkspace.jsx
```

`ImplementationProjectPage` owns page entry, Project Overview, visible modal
state, and navigation. `ImplementationWorkspace` coordinates authoritative data
and child wiring. Canvas modules own graph mechanics; workflow modules own gates
and presentation derivation. Panels own node interactions; services own HTTP.

State ownership distinguishes `activeWorkflowNodeId`, `visibleModalNodeId`, and
canvas positions. Modal origin and transition consumption are explicit, so an
automatic transition cannot replace a modal the user is reviewing.

Reusable presentation includes `WorkflowNodeModal`, `WorkflowNode`,
`HumanDecisionCallout`, `WorkflowNextStepNotice`, `WorkflowBarrier`,
`ArtifactGroup`, `ResearchDetails`, and `SourceSummary`. Workflow and geometry
derivations are pure and independently testable.

## 20. Canvas and modal behavior

Users cannot add, delete, reconnect, or reorder business stages. Nodes are
individually draggable, the canvas pans/zooms, and floating edges stay elastically
attached. Auto Arrange and Reset Layout use the same deterministic operation.

Positions are presentation-only and session-local; layout persistence is not
implemented. Dragging does not alter workflow truth, and canvas code does not own
workflow gates.

Existing projects enter through Project Overview and explicitly open the canvas.
New projects enter through Project & Sources onboarding. An open modal remains
pinned when backend state advances; navigation is explicit. Dialog semantics,
focus restoration, Escape, keyboard controls, ARIA labels, and reduced-motion
behavior are preserved.

Project Overview is presentation-only, not a workflow gate:

```text
Existing project -> Project Overview -> View Canvas -> user chooses a node
New project      -> Project & Sources onboarding
```

## 21. Backend architecture after REFACTOR-R1

Feature root: `backend/app/modules/agents/implementation/`.

```text
implementation/
|-- api/             thin routes, ownership dependencies, error translation
|-- contracts/       public enums and request/response schemas
|-- inputs/
|   |-- upload/      validation, identity, streaming persistence
|   `-- extraction/  format extraction and contracts
|-- preparation/
|   |-- orchestration/       execution/status/storage
|   |-- chunking/            deterministic section-aware chunks
|   |-- classification/      rule_based/ and zero_shot/ providers
|   |-- hybrid/              conservative evidence policy
|   |-- human_review/        authoritative classification decisions
|   |-- canonical/           deterministic typed artifacts
|   |-- semantic_extraction/ grounded Qwen provider and merge policy
|   |-- specification/       per-source trusted workflow
|   |-- consolidation/       cross-source merge and conflict review
|   `-- readiness/           legacy and trusted policy/storage
|-- github/          GitHub App auth, connection, repository setup
|-- runs/            immutable approval snapshots
`-- infrastructure/ shared storage, sidecar, and digest primitives
```

Dependency direction is API -> application/domain service ->
storage/provider/infrastructure. Routes validate/authorize, invoke services,
translate known errors, and return typed contracts. Storage owns location,
loading, malformed-data handling, and atomic persistence; it does not make HITL
decisions. Transformers details stay behind model provider boundaries.

## 22. Verification baseline

| Check | Result |
| --- | --- |
| Agent 3 frontend focused suite | **13 files, 189 tests passed** |
| Full frontend suite | **46 files, 393 tests passed** |
| Frontend ESLint | **Passed** |
| Vite production build | **Passed**; existing large-chunk advisory is non-fatal |
| Agent 3 backend suite | **363 tests passed** |
| Full backend suite | **918 passed, 1 skipped** |
| `pip check` | **Passed** |
| Python `compileall` | **Passed** |
| OpenAPI regression | **57 paths, 70 operations, 308 schemas** |
| Canonical OpenAPI SHA-256 | `935975a82076fadd1fae0bd706e0e41da160d34d6e504746637bdc727f4ce48d` |
| Manual UAT | **Passed for the implemented Agent 3 boundary** |

Tests cover uploads, extraction, preparation, classification, human review,
canonical/semantic workflows, consolidation, readiness, warning continuation,
GitHub setup, AgentRun snapshots, frontend gates, modal/navigation behavior,
canvas geometry, and API/service integration. They do not claim future engines.

## 23. Known limitations and technical debt

- Zero-shot classification can overclassify and produce label explosion; human
  review is the mitigation, not a claim that the model is calibrated.
- OCR and image understanding are not implemented.
- Conflict detection covers explicit cases, not general contradictions.
- Semantic quality depends on source clarity and still requires human review.
- Local DeBERTa/Qwen inference can have material latency on CPU-only machines.
- The implementation stack is a fixed PP1 stack, not a generator matrix.
- Canvas positions and transient review navigation are not persisted.
- `ImplementationWorkspace` remains substantial and should be watched as future
  work arrives.
- GitHub cannot select an existing repository or perform delivery.
- Some shared documents describe the end state or retain historical wording;
  this document is the current status authority.
- The Vite build reports the existing large-chunk advisory.

## 24. Future milestones

All work in this section is **future**, not partially running behind the current
UI.

### GEN-R1 — Implementation Generation

Approved AgentRun -> isolated run workspace -> generation plan -> selected
artifact generation -> safe proposed/validated paths -> file writes -> manifest
and traceability. Project archive/workspace export also remains future.

### EXEC-R1 — Build & Execution

Dependency installation -> build -> execution -> honest `BUILD_RESULT`,
`EXECUTION_RESULT`, and `EXECUTION_LOGS` evidence.

### FIX-R1 — Bounded Correction

Detect build/runtime errors -> analyze evidence -> regenerate or fix -> rebuild
-> stop after a bounded number of retries.

### GIT-R1 — Git Delivery

Create an implementation branch -> commit -> push -> optionally open a pull
request. Existing-repository selection, releases, and archive delivery are also
not implemented today.

### AGENT-4-INTEGRATION

Pass generated implementation to Agent 4 -> receive test/security failures ->
return bounded correction work to Agent 3 -> retest. There is no automatic Agent
4 handoff today.

Automatic Shared Knowledge Base writes, new models/classifiers, new workflow
nodes/HITL decisions, and canvas layout persistence are likewise outside the
current implementation.

## 25. Current capability matrix

| Capability | Status | Notes |
| --- | --- | --- |
| Project sources and output selection | **COMPLETE** | Text, documents, images; images are not analyzed |
| Document extraction and chunking | **COMPLETE** | Textual supported formats; no OCR |
| Rule classification | **COMPLETE** | Deterministic evidence |
| DeBERTa zero-shot baseline | **COMPLETE** | Experimental advisory model |
| Hybrid classification | **COMPLETE** | Conservative decision policy |
| Artifact classification HITL | **COMPLETE** | Human labels become ground truth |
| Canonical extraction | **COMPLETE** | Deterministic and provenance-preserving |
| Local semantic fallback and HITL | **COMPLETE** | Qwen proposals require review |
| Project consolidation/conflict HITL | **COMPLETE** | Narrow deterministic conflict families |
| Trusted readiness/warning HITL | **COMPLETE** | Fingerprint-bound continuation |
| GitHub setup | **COMPLETE FOR SETUP** | New empty repository or skip; no delivery |
| Immutable AgentRun | **COMPLETE** | Approved `READY_FOR_GENERATION` snapshot |
| Code generation | **FUTURE** | GEN-R1 |
| Build/run evidence | **FUTURE** | EXEC-R1 |
| Self-correction | **FUTURE** | FIX-R1 |
| Git delivery | **FUTURE** | GIT-R1 |
| Agent 4 feedback | **FUTURE** | AGENT-4-INTEGRATION |

## 26. Example: QuickBook appointment booking system

1. A user creates QuickBook and supplies functional requirements, an API
   specification, a UI flow, and database notes; they select frontend, backend,
   database, and API outputs.
2. Agent 3 validates the sources, extracts the documents, creates traceable
   chunks, and combines rule and DeBERTa classification evidence.
3. The user reviews uncertain labels source by source until the backend confirms
   classification completion.
4. Deterministic canonical artifacts are created. Qwen may propose grounded
   completion of partial items, but the user accepts or rejects every semantic
   change.
5. Agent 3 consolidates trusted source artifacts. The user resolves, for example,
   a MySQL/PostgreSQL technology candidate conflict using only server-known data.
6. Readiness evaluates the trusted project specification against the selected
   outputs and PP1 stack. If the result is `READY_WITH_WARNINGS`, the user
   explicitly chooses **Continue With Warnings**.
7. The user connects a GitHub App and creates a new empty QuickBook repository,
   or skips setup.
8. Final approval creates an immutable AgentRun with the exact trusted
   specification, readiness, outputs, stack decision, approval evidence,
   traceability roots, and safe delivery metadata.

The example stops at `READY_FOR_GENERATION`; it does not claim QuickBook source
files, dependencies, a build, runtime evidence, or Git commits exist.

## 27. End-to-end workflow and human gates

```text
User
  |
  v
Project & Sources -> Input Analysis -> Specification Verification
                                          | classification review loop
                                          | semantic review loop
                                          | conflict review loop
                                          v
Implementation Readiness -----------------+
  | warning? -> Continue With Warnings ----+
  v
Delivery Setup -> Final Approval -> immutable AgentRun
     | connect/create or skip                  |
     `-----------------------------------------'

AgentRun -> [GEN-R1 future] -> [EXEC-R1 future] -> [FIX/GIT/Agent 4 future]
```

## 28. Related documentation

- [Agent 3 Implementation Contract](AGENT_3_IMPLEMENTATION_CONTRACT.md)
- [Standalone Agent Architecture](STANDALONE_AGENT_ARCHITECTURE.md)
- [Common Agent Project Contract](COMMON_AGENT_PROJECT_CONTRACT.md)
- [Standalone UI and API Contract](STANDALONE_UI_AND_API_CONTRACT.md)
- [Agent 3 Document Extraction UAT](AGENT_3_DOCUMENT_EXTRACTION_UAT.md)
- [Agent 3 GitHub Repository Setup](AGENT_3_GITHUB_REPOSITORY_SETUP.md)
- [AgentRun implementation notes](../../backend/app/modules/agents/implementation/runs/README.md)
- [Trusted readiness notes](../../backend/app/modules/agents/implementation/preparation/readiness/trusted/README.md)
- [Consolidation notes](../../backend/app/modules/agents/implementation/preparation/consolidation/README.md)
