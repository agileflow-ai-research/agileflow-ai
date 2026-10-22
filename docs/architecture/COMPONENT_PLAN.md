# AgileFlow AI Component Plan

Project ID: **J26-SE-358**

This map translates the approved architecture into implementation ownership and boundaries. Backend package paths are based on the current repository. All frontend areas are planned because the frontend is not initialized.

## Whole-System Rules

- There are exactly four intelligent research agents.
- Testing, Validation and Security appears in pre-code and post-code phases but remains one agent.
- The Central SDLC Orchestrator controls global state and H1-H5; individual agents do not.
- MongoDB is the Shared Knowledge Base; reports/traceability are shared functionality.
- JWT authentication and Project ownership are shared platform concerns, not a fifth agent. Every project-scoped component must authorize through the owning Project.
- Every accepted artifact preserves the Requirement → Design → Backlog → Test → Code → Bug/Security Finding → Validation → Report/Correction chain.
- Planned routes use `/api/v1`; listed responsibilities don't imply implementation.

## 1. Requirement Gathering and Analysis Agent

| Attribute | Contract |
|---|---|
| Official name | Requirement Gathering and Analysis Agent |
| Owner | N A Illangasinghe — IT23391536 |
| Branch | `feature/agent-requirements` |
| Backend area | Integrated artifact/H1/SKB domain: `backend/app/modules/requirements/`; standalone Agent 1 intelligence: `backend/app/modules/agents/requirements/` |
| Frontend area | Planned `frontend/src/pages/requirements/` and requirement service/components using shared UI |
| Primary inputs | Project/client idea; text, document/link/audio/video metadata; interview responses; clarification and human feedback |
| Responsibilities | Structure SRS/FR/NFR, requirements, stories, acceptance criteria; detect ambiguity/missing/conflicting/duplicate information; preserve source references; prepare H1 package |
| Outputs | Complete versioned H1 snapshot containing Requirement, UserStory, AcceptanceCriteria, QualityFinding, Persona, and SrsDocument artifacts; `REQ`, `US`, and `AC` identifiers; traceability links; H1 readiness |
| Approval gate | H1 — Requirement Approval |
| Collections used | `projects`, `client_inputs`, `requirements`, `traceability_links`; approval/events are coordinated through shared Orchestrator functionality |
| IDs consumed | `PRJ-###`, source/input references where defined |
| IDs produced | `REQ-###`, `US-###`, `AC-###`, relevant `TRACE-###` |
| Dependencies | Project foundation, shared schemas/IDs, Shared Knowledge Base, Orchestrator, H1 UI/API, common response/error utilities |
| Must not do | Generate design/code/final validation; advance global workflow; rename common fields; own another agent's module |
| Current status | ClientInput request/response validation and APIs are implemented. SKB-1 defines Agent 1 contracts; SKB-2 implements typed/versioned snapshot persistence; SKB-3 implements persisted pairwise traceability; SKB-4 implements H1 publication/readiness; and SKB-5 implements internal exact approved-H1 and structured typed retrieval. Processing/intelligence, public artifact/publication APIs, correction flows, Agent 2-4 SKB adapters, and UI remain planned |

Agent 1 publishes future H1 output in this order: generate and validate the complete snapshot; persist every artifact document for the package version; persist immutable pairwise traceability links; mark package artifacts `WAITING_FOR_APPROVAL`; append one final `ARTIFACT_GENERATED` readiness event; then return control to the Orchestrator. The readiness event must never precede artifact persistence. This sequence does not let Agent 1 mutate the global workflow stage.

## 2. Project Management and Design Agent

| Attribute | Contract |
|---|---|
| Official name | Project Management and Design Agent |
| Owner | Kulunu Kasthuri Arachchi — IT23375628 |
| Branch | `feature/agent-design-planning` |
| Backend area | Standalone implementation: `backend/app/modules/agents/design_planning/`; integrated Agent 2 artifact persistence remains planned |
| Frontend area | Planned `frontend/src/pages/design/` and design service/components using shared UI |
| Primary inputs | H1-approved requirements, stories, acceptance criteria, quality/context information |
| Responsibilities | Produce backlog/sprint planning, UML, API, DB, UI-flow and wireframe artifacts; Jira-ready/mock items; requirement-to-design mappings; prepare H2 package |
| Outputs | Design artifacts, backlog items, sprint plan, API/DB/UI plans, traceability mappings, H2 readiness |
| Approval gate | H2 — Design and Planning Approval |
| Collections used | `projects`, `requirements`, `design_artifacts`, `backlog_items`, `traceability_links`, and correction references from `bug_reports`/`security_findings` where routed |
| IDs consumed | `PRJ-###`, `REQ-###`, `US-###`, `AC-###` |
| IDs produced | `DES-###`, `API-###`, `DB-###`, `TASK-###`, relevant `TRACE-###` |
| Dependencies | H1 approval, requirement artifacts, shared schemas, Orchestrator, Shared Knowledge Base, shared UI/services |
| Must not do | Extract requirements, generate implementation, execute tests, decide global transitions, create alternate schemas/routes |
| Current status | Standalone Agent 2 is implemented under the semantic specialist package. Integrated design-artifact persistence, H2 publication, and SKB adapter remain planned |

## 3. Implementation and Git Automation Agent

| Attribute | Contract |
|---|---|
| Official name | Implementation and Git Automation Agent |
| Owner | W M D D Karunarathna — IT23145320 |
| Branch | `feature/agent-implementation` |
| Backend area | `backend/app/modules/implementation/` (package placeholder exists) |
| Frontend area | Planned `frontend/src/pages/implementation/` and implementation service/components using shared UI |
| Primary inputs | H1/H2-approved requirements/designs and H3-approved test package |
| Responsibilities | Generate selected prototype modules and file metadata; simulate or later integrate Git/workspace actions; run/simulate build/runtime; record logs; perform bounded build/runtime self-fix; prepare H4 package |
| Outputs | Implementation artifacts, `CODE` metadata, file paths, Git metadata, build/runtime/self-fix logs, H4 readiness |
| Approval gate | H4 — Implementation Approval |
| Collections used | `projects`, `requirements`, `design_artifacts`, `backlog_items`, `test_cases`, `implementation_artifacts`, `execution_logs`, `traceability_links`; reads routed bug/security correction work |
| IDs consumed | `PRJ-###`, `REQ-###`, `DES-###`, `API-###`, `DB-###`, `TASK-###`, `TEST-###` |
| IDs produced | `CODE-###`, relevant `TRACE-###`; commit identifiers are metadata, not AgileFlow ID families |
| Dependencies | H3 approval, approved design/test contracts, local storage/execution strategy, Orchestrator retry/routing, Shared Knowledge Base |
| Must not do | Change requirements/design/test expectations independently; own global workflow; perform unbounded self-fix; expose credentials; claim production-ready code |
| Current status | Module placeholder only; no generator, Git automation, execution, self-fix, routes, persistence, or UI implemented |

## 4. Testing, Validation and Security Agent

| Attribute | Contract |
|---|---|
| Official name | Testing, Validation and Security Agent |
| Owner | R A K Hansika — IT23140998 |
| Branch | `feature/agent-testing-validation` |
| Backend area | Standalone implementation: `backend/app/modules/agents/testing_validation/`; integrated Agent 4 persistence/readiness adapters remain planned |
| Frontend area | Planned `frontend/src/pages/testing/` with pre-code and validation views plus one testing service area |
| Primary inputs | Pre-code: H2-approved requirements/designs. Post-code: H4-approved implementation and execution evidence |
| Responsibilities | Pre-code test/security specifications, skeleton metadata, and mappings; post-code test execution/simulation, regression, bug reports, security findings, validation evidence, correction verification |
| Outputs | `TEST` artifacts, test results, `BUG` reports, `SEC` findings, validation report, H3 and H5 readiness |
| Approval gates | H3 — Pre-Code Test Approval; H5 — Final Validation Approval |
| Collections used | `projects`, `requirements`, `design_artifacts`, `test_cases`, `implementation_artifacts`, `execution_logs`, `test_results`, `bug_reports`, `security_findings`, `traceability_links` |
| IDs consumed | `PRJ-###`, `REQ-###`, `US-###`, `AC-###`, `DES-###`, `API-###`, `DB-###`, `TASK-###`, `CODE-###` |
| IDs produced | `TEST-###`, `BUG-###`, `SEC-###`, relevant `TRACE-###` |
| Dependencies | H2/H4 approvals, approved artifacts, Orchestrator correction loops, Design/Implementation correction owners, reports/traceability |
| Must not do | Become a fifth agent, generate implementation code as its owned function, silently fix/hide findings, bypass H3/H5, advance global state |
| Current status | Standalone Agent 4 is implemented with separate test-generation and Docker-sandboxed validation modes. Integrated H3/H5 artifact persistence and readiness emission remain planned |

## 5. Central SDLC Orchestrator

| Attribute | Contract |
|---|---|
| Official name | Central SDLC Orchestrator |
| Owner | Shared/group-level; foundation/group leader coordinates integration |
| Branch | `feature/orchestrator` |
| Backend area | `backend/app/modules/orchestrator/` plus coordinated approvals/project/shared utilities |
| Frontend area | Planned `frontend/src/pages/orchestrator/` and shared workflow/approval components |
| Primary inputs | Current project stage, persisted artifacts, H1-H5 decisions, failures, retry state, traceability state |
| Responsibilities | Enforce one active stage, prerequisite checks, handovers, approvals, failure routing, bounded retries, workflow events, runtime holds/human review, final completion rules |
| Outputs | Updated project stage/runtime status, approvals, workflow events, route/correction assignments, retry/escalation state |
| Approval gate | Coordinates all H1-H5; does not own artifact acceptance itself |
| Collections used | `projects`, `approvals`, `workflow_events`, `traceability_links`, and all artifact/evidence collections for prerequisite verification |
| IDs consumed | All project/artifact/traceability IDs |
| IDs produced | `EVT-###`, approved `APP-###`, and relevant `TRACE-###` where orchestration creates links |
| Dependencies | All four agents, Shared Knowledge Base, canonical stages/decisions, approval UI, report completion checks |
| Must not do | Perform agent domain work, skip/auto-approve gates, hide failures, exceed retry limits, overwrite approved versions, allow agent-controlled global transitions |
| Current status | The centralized transition policy and stage ownership metadata, authenticated owner-scoped workflow snapshot/event-history endpoints, next-step, `PROJECT_CREATED` → `REQUIREMENTS_IN_PROGRESS`, O2 H1-H5 Approval persistence, O3 effective-APPROVE transitions, and O3.5 specialist handoff consumption/validation for all five approval-gate entries are implemented. Agent 1 now emits its H1 marker through SKB-4; Agent 2-4 marker emission, O4 REJECT/REQUEST_CHANGES routing, O6 HOLD/release behavior, failure routing, retries, escalation, correction loops, and UI remain planned |

### Orchestrator Phase Boundaries

- **O2 — implemented:** authenticate and authorize the Project owner, validate the matching H1-H5 waiting stage, append an immutable Approval, identify the newest gate decision as effective, and append exactly one `APPROVAL_DECISION` event without changing `Project.current_stage`.
- **O3 — implemented:** consume the newest/effective matching-gate `APPROVE`, verify its `next_stage` against policy, execute the canonical forward Project transition through next-step, and create exactly one `STAGE_CHANGED`.
- **O3.5 — implemented for consumption/validation:** next-step and workflow snapshot use a final project-scoped `ARTIFACT_GENERATED` readiness marker plus the approved minimum collection evidence. Only the Orchestrator enters H1-H5 waiting stages and creates the single `STAGE_CHANGED`; entry creates no Approval. SKB-4 implements idempotent Agent 1/H1 marker emission without changing the predicate; other specialist emitters remain planned.
- **O4 — planned:** implement REJECT routing and REQUEST_CHANGES correction routing.
- **O6 — planned:** persist richer `ON_HOLD` runtime state and implement authorized release/resume behavior.

These phases preserve four research agents. Project ownership remains the O2 authorization boundary; no reviewer roles, RBAC, teams, organizations, or `reviewer_user_id` are introduced.

## 6. Shared Knowledge Base

| Attribute | Contract |
|---|---|
| Official name | Shared Knowledge Base |
| Owner | Shared/foundation infrastructure |
| Branch | `feature/shared-knowledge-base` |
| Backend area | `backend/app/database/mongodb.py`, `backend/app/database/collections.py`, approved shared schemas, internal facade at `backend/app/modules/shared_knowledge/`, and collection-specific module repositories |
| Frontend area | No direct database access; planned pages consume backend services only |
| Primary inputs | Structured, versioned artifacts and workflow records from all components |
| Responsibilities | Act as an internal architectural/service layer over the existing MongoDB collections; coordinate typed, project-scoped, version-aware and approval-aware retrieval across collection-specific repositories |
| Outputs | Stored users, projects, inputs, artifacts, logs, results, findings, approvals, links, and events |
| Approval gate | Stores decisions/artifact versions; doesn't decide approvals |
| Collections used | All 17 canonical database collection constants are defined in code: 15 integrated Shared Knowledge Base collections plus isolated standalone `agent_projects` and `agent_runs` |
| IDs consumed/produced | Stores all canonical IDs; ID generation responsibility is shared utility/component-specific and not database-client logic |
| Dependencies | Environment settings, PyMongo, approved schemas/repositories, security/secret handling |
| Must not do | Become a second database, generic dynamic MongoDB repository, vector store, RAG/LLM memory, workflow authority, approval authority, final traceability-report generator, or public `/knowledge-base` API |
| Current status | Foundation implemented, including the SKB-5 internal read-only facade for Agent 1: typed/project-scoped structured reads, exact effective-Approval-authorized H1 snapshots, one-hop traceability delegation, and approved-package link intersection. Requirements and Reports/Traceability retain repository ownership. 
H2-H5 artifact adapters and public SKB APIs are not implemented |

Collection-specific repositories remain owned by `requirements`, `design`, `testing`, and `implementation`. The implemented `backend/app/modules/shared_knowledge/` facade coordinates the current Requirements, Approval, and Reports/Traceability read abstractions rather than selecting arbitrary collections dynamically. Human-facing workspaces use specialist APIs; generic public `/knowledge-base` or `/artifacts` routes are not part of the SKB foundation. Downstream agents should request an approved upstream snapshot, not the latest draft.

Structured retrieval by project, artifact type/ID, gate, status, version, producer, and traceability relationship is sufficient for the immediate foundation. RAG and semantic/vector retrieval are future enhancements only; no embeddings, chunking, vector index, vector database, or additional persistence technology is approved. The Central SDLC Orchestrator remains deterministic for stages, approvals, readiness, and completion; no LLM is required for those controls.

## Shared Authentication and Project Ownership Foundation

Steps A, B, and C implement User persistence, `USR-###`, Argon2 password hashing, public registration, JWT Bearer login and validation, `/auth/me`, reusable `get_current_user` authentication, `Project.owner_user_id`, and the shared `authorize_project_access` boundary. JWT parsing must not be duplicated in every router, and ownership checks must not be independently reimplemented by every agent.

One user may own multiple independent projects. All project-scoped components continue to use `project_id`, and access is permitted only when the authenticated `user_id` matches `project.owner_user_id`. Cross-user sharing, roles/RBAC, organizations, teams, OAuth/social login, refresh tokens, and administrator behavior are not approved. This foundation does not change the responsibilities of the four research agents or the Central SDLC Orchestrator.

## 7. Reports / Traceability

| Attribute | Contract |
|---|---|
| Official name | Reports / Traceability |
| Owner | Shared/group-level |
| Branch | `feature/reports-traceability` |
| Backend area | `backend/app/modules/reports/` contains the SKB-3 internal Agent 1 traceability repository/service; report generation remains planned |
| Frontend area | Planned `frontend/src/pages/reports/` plus traceability/report components; planned traceability route/view |
| Primary inputs | Approved artifacts, workflow events, approvals, logs, test results, bugs, security findings, traceability links |
| Responsibilities | Own authoritative immutable pairwise traceability persistence/query behavior, build the final traceability matrix, final evidence/report summaries, artifact inventory, and later approved exports |
| Outputs | Requirement-to-report matrix, final report package, export artifacts where later defined |
| Approval gate | Final package follows H5 approval; reports don't replace H5 |
| Collections used | Reads all relevant collections; appends and queries immutable `traceability_links` as approved. No canonical `reports` MongoDB collection exists |
| IDs consumed | All canonical artifact IDs and `EVT-###` |
| IDs produced | `TRACE-###`; no report ID family is formally defined |
| Dependencies | All four agents, Orchestrator, Shared Knowledge Base, local `/storage/reports`, canonical API/data contracts |
| Must not do | Invent a `reports` collection/ID, mark incomplete artifacts as validated, alter source artifacts, expose private data, bypass H5 |
| Current status | SKB-3 implements internal immutable pairwise persistence in `traceability_links`, `TRACE-###` max-scan allocation, exact-edge idempotency, same-project endpoint/type/relation validation, and typed project/incoming/outgoing/exact retrieval for Agent 1 artifacts. Public routes, version-specific views, multi-hop traversal, matrix/report generation, Agent 2-4 adapters, exports, and UI remain planned |

## Shared Approval and Traceability Ownership

Component owners prepare artifacts and readiness for their gates. Human reviewers make decisions. The Orchestrator validates and records transitions. The Shared Knowledge Base stores records. Reports/Traceability consumes the evidence. This separation prevents agents from approving their own work or controlling global progression.

For O3.5, readiness is represented without a new collection or status field: the responsible specialist appends a final `ARTIFACT_GENERATED` event carrying `handoff_ready`, source/target stages, and a positive package version. The Orchestrator additionally checks the exact same-project minimum evidence defined in the workflow contract. The Testing, Validation and Security Agent owns both H3 and H5 readiness; this does not create a fifth agent.

## Contract Resolution Notes

1. Four agents are canonical; “Pre-Code Test Planning Agent” in some general source wording is the pre-code phase of Agent 4.
2. Actual backend paths are used; no nonexistent frontend or backend files are claimed as implemented.
3. `backend/app/database/mongodb.py` is the shared client location.
4. No `reports` MongoDB collection or report ID family is invented because neither is in the canonical collection/ID list.
