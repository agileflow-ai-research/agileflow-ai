# AgileFlow AI Component Plan

Project ID: **J26-SE-358**

This map translates the approved architecture into implementation ownership and boundaries. Backend package paths are based on the current repository. All frontend areas are planned because the frontend is not initialized.

## Whole-System Rules

- There are exactly four intelligent research agents.
- Testing, Validation and Security appears in pre-code and post-code phases but remains one agent.
- The Central SDLC Orchestrator controls global state and H1-H5; individual agents do not.
- MongoDB is the Shared Knowledge Base; reports/traceability are shared functionality.
- Every accepted artifact preserves the Requirement → Design → Backlog → Test → Code → Bug/Security Finding → Validation → Report/Correction chain.
- Planned routes use `/api/v1`; listed responsibilities do not imply implementation.

## 1. Requirement Gathering and Analysis Agent

| Attribute | Contract |
|---|---|
| Official name | Requirement Gathering and Analysis Agent |
| Owner | N A Illangasinghe — IT23391536 |
| Branch | `feature/agent-requirements` |
| Backend area | `backend/app/modules/requirements/` (package placeholder exists) |
| Frontend area | Planned `frontend/src/pages/requirements/` and requirement service/components using shared UI |
| Primary inputs | Project/client idea; text, document/link/audio/video metadata; interview responses; clarification and human feedback |
| Responsibilities | Structure SRS/FR/NFR, requirements, stories, acceptance criteria; detect ambiguity/missing/conflicting/duplicate information; preserve source references; prepare H1 package |
| Outputs | Requirement package, quality findings, `REQ`, `US`, and `AC` identifiers, H1 readiness |
| Approval gate | H1 — Requirement Approval |
| Collections used | `projects`, `client_inputs`, `requirements`, `traceability_links`; approval/events are coordinated through shared Orchestrator functionality |
| IDs consumed | `PRJ-###`, source/input references where defined |
| IDs produced | `REQ-###`, `US-###`, `AC-###`, relevant `TRACE-###` |
| Dependencies | Project foundation, shared schemas/IDs, Shared Knowledge Base, Orchestrator, H1 UI/API, common response/error utilities |
| Must not do | Generate design/code/final validation; advance global workflow; rename common fields; own another agent's module |
| Current status | Module placeholder only; no agent logic, routes, schemas, repository, service, persistence, or UI implemented |

## 2. Project Management and Design Agent

| Attribute | Contract |
|---|---|
| Official name | Project Management and Design Agent |
| Owner | Kulunu Kasthuri Arachchi — IT23375628 |
| Branch | `feature/agent-design-planning` |
| Backend area | `backend/app/modules/design/` (package placeholder exists) |
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
| Current status | Module placeholder only; no design logic, routes, schemas, repository, service, Jira integration, persistence, or UI implemented |

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
| Backend area | `backend/app/modules/testing/` (package placeholder exists) |
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
| Current status | Module placeholder only; no pre/post-code logic, execution, scanners, routes, schemas, persistence, or UI implemented |

## 5. Central SDLC Orchestrator

| Attribute | Contract |
|---|---|
| Official name | Central SDLC Orchestrator |
| Owner | Shared/group-level; foundation/group leader coordinates integration |
| Branch | `feature/orchestrator` |
| Backend area | `backend/app/modules/orchestrator/` plus coordinated approvals/project/shared utilities (placeholder packages exist) |
| Frontend area | Planned `frontend/src/pages/orchestrator/` and shared workflow/approval components |
| Primary inputs | Current project stage, persisted artifacts, H1-H5 decisions, failures, retry state, traceability state |
| Responsibilities | Enforce one active stage, prerequisite checks, handovers, approvals, failure routing, bounded retries, workflow events, runtime holds/human review, final completion rules |
| Outputs | Updated project stage/runtime status, approvals, workflow events, route/correction assignments, retry/escalation state |
| Approval gate | Coordinates all H1-H5; does not own artifact acceptance itself |
| Collections used | `projects`, `approvals`, `workflow_events`, `traceability_links`, and all artifact/evidence collections for prerequisite verification |
| IDs consumed | All project/artifact/traceability IDs |
| IDs produced | `EVT-###`; approval identifier format needs final schema approval; relevant `TRACE-###` where orchestration creates links |
| Dependencies | All four agents, Shared Knowledge Base, canonical stages/decisions, approval UI, report completion checks |
| Must not do | Perform agent domain work, skip/auto-approve gates, hide failures, exceed retry limits, overwrite approved versions, allow agent-controlled global transitions |
| Current status | Package placeholder only; no stages, gates, approvals, routing, retry logic, events, APIs, or UI implemented |

## 6. Shared Knowledge Base

| Attribute | Contract |
|---|---|
| Official name | Shared Knowledge Base |
| Owner | Shared/foundation infrastructure |
| Branch | Foundation work on `feature/project-foundation`; coordinated changes with component/orchestrator/report branches |
| Backend area | `backend/app/database/mongodb.py`, `backend/app/database/collections.py`, future module repositories and approved schemas |
| Frontend area | No direct database access; planned pages consume backend services only |
| Primary inputs | Structured, versioned artifacts and workflow records from all components |
| Responsibilities | Provide one MongoDB-backed source of truth and canonical collections; support persistence and cross-component retrieval through repositories |
| Outputs | Stored projects, inputs, artifacts, logs, results, findings, approvals, links, and events |
| Approval gate | Stores decisions/artifact versions; does not decide approvals |
| Collections used | All 14 canonical collections |
| IDs consumed/produced | Stores all canonical IDs; ID generation responsibility is shared utility/component-specific and not database-client logic |
| Dependencies | Environment settings, PyMongo, approved schemas/repositories, security/secret handling |
| Must not do | Contain agent queries/business logic in the client module, create duplicate clients/collections, decide workflow, expose credentials |
| Current status | Foundation implemented: one settings-driven client, database accessor, ping/close helper, exact collection constants, unit tests. Repositories and artifact persistence are planned |

## 7. Reports / Traceability

| Attribute | Contract |
|---|---|
| Official name | Reports / Traceability |
| Owner | Shared/group-level |
| Branch | `feature/reports-traceability` |
| Backend area | `backend/app/modules/reports/` exists as placeholder; no separate traceability package currently exists |
| Frontend area | Planned `frontend/src/pages/reports/` plus traceability/report components; planned traceability route/view |
| Primary inputs | Approved artifacts, workflow events, approvals, logs, test results, bugs, security findings, traceability links |
| Responsibilities | Build traceability matrix, final evidence/report summaries, artifact inventory, and later approved exports |
| Outputs | Requirement-to-report matrix, final report package, export artifacts where later defined |
| Approval gate | Final package follows H5 approval; reports do not replace H5 |
| Collections used | Reads all relevant collections; writes/updates `traceability_links` as approved. No canonical `reports` MongoDB collection exists |
| IDs consumed | All canonical artifact IDs and `EVT-###` |
| IDs produced | `TRACE-###`; no report ID family is formally defined |
| Dependencies | All four agents, Orchestrator, Shared Knowledge Base, local `/storage/reports`, canonical API/data contracts |
| Must not do | Invent a `reports` collection/ID, mark incomplete artifacts as validated, alter source artifacts, expose private data, bypass H5 |
| Current status | Reports module package and storage directory placeholders only; no report/traceability logic, routes, schemas, persistence, export, or UI implemented |

## Shared Approval and Traceability Ownership

Component owners prepare artifacts and readiness for their gates. Human reviewers make decisions. The Orchestrator validates and records transitions. The Shared Knowledge Base stores records. Reports/Traceability consumes the evidence. This separation prevents agents from approving their own work or controlling global progression.

## Contract Resolution Notes

1. Four agents are canonical; “Pre-Code Test Planning Agent” in some general source wording is the pre-code phase of Agent 4.
2. Actual backend paths are used; no nonexistent frontend or backend files are claimed as implemented.
3. `backend/app/database/mongodb.py` is the shared client location.
4. No `reports` MongoDB collection or report ID family is invented because neither is in the canonical collection/ID list.
