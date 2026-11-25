# Agent 3 GEN-R1.2 — Deterministic Generation Planner

**Status:** Implemented on `feature/agent3-gen-r1.1`  
**Scope:** Pure internal backend planning; no public API or persistence

## Responsibilities and boundaries

GEN-R1.2 consumes only the validated `ApprovedGenerationContext` produced by
GEN-R1.1. It does not read live project forms, preparation sidecars, uploads,
GitHub state, or another AgentRun. The planner returns an immutable in-memory
`GenerationPlan` and never updates the approved run.

The plan identifies expected files, their responsibilities, authorized output
codes, existing PSI evidence, file dependencies, deterministic generation
order, non-file deliverables, coverage, findings, source identity, and plan
identity. Every planned file remains `NOT_STARTED`; a plan never claims that a
file exists.

## Deterministic algorithm

Policy version `GEN-R1.2-1` performs these steps:

1. Validate the frozen PP1 effective stack and approved output set.
2. Select structural catalog entries only for approved outputs.
3. Derive REST resource modules only from trusted API `path` values.
4. Derive frontend page modules only from explicitly named trusted UI flows.
5. Attach trusted database entity PSI references to the shared SQL schema plan.
6. Resolve path dependencies to stable file identities.
7. Validate paths, namespace uniqueness, references, and the dependency graph.
8. Produce a stable topological order using canonical path order to break ties.
9. Calculate honest coverage/findings and stable source/plan fingerprints.
10. Revalidate the complete result before returning it.

The algorithm uses no timestamp, randomness, filesystem enumeration, model
output, or mutable project state.

## Selected-output file catalog

| Approved output | Planned representation |
| --- | --- |
| `PROJECT_STRUCTURE` | `README.md` |
| `FRONTEND_CODE` | Vite package/HTML, React entry/application, plain CSS, and evidence-backed named UI-flow pages |
| `BACKEND_CODE` | Node package, Express application, and evidence-backed REST resource routes where available |
| `DATABASE_IMPLEMENTATION` | `database/schema.sql`, bound to verified database entity PSI items |
| `API_IMPLEMENTATION` | Essential Node/Express scaffolding plus evidence-backed REST resource routes |
| `CONFIGURATION_FILES` | `.gitignore` and credential-free `.env.example` contract |
| `CONTAINER_CONFIGURATION` | `docker-compose.yml`; selected implementation targets become dependencies only when present |
| `GIT_SUMMARY` | Non-file future report/delivery artifact; no invented source file |

One file is emitted once when it supports multiple approved outputs. Essential
scaffolding carries only the output codes actually approved; planning an API
does not silently approve the independent `BACKEND_CODE` deliverable.

## Stack and naming policy

The catalog supports only the approved PP1 effective stack: React + Vite,
plain CSS, Node.js + Express.js, MySQL, JavaScript, and REST. Existing stack
adaptation evidence remains bound through the source-snapshot fingerprint. The
planner neither changes the requested stack nor creates another adaptation
policy.

Domain names are normalized from explicit trusted fields. API paths skip
literal `api`, version, and parameter segments before selecting a resource.
Named UI flows become bounded lowercase hyphenated page names. If a trusted
value cannot produce a safe canonical path, planning fails; it is never replaced
with an invented business name.

## Dependencies and path security

Dependencies use planned file IDs. Validation rejects missing/self references,
cycles, duplicate IDs, exact and case-insensitive path collisions, and
file/directory namespace collisions. Stable Kahn topological ordering sorts
independent files by canonical relative path.

All planned paths pass the GEN-R1.1 validator. Absolute, drive, UNC, traversal,
backslash, alternate-stream, reserved-name, control-character, non-canonical,
and escaping representations remain prohibited. GEN-R1.2 creates no directory
or file. A future writer must revalidate containment, symlinks/reparse points,
limits, and exclusive creation immediately before writing.

## Traceability, coverage, and validation

Domain files reference existing `PSI-*` identities only. Structural files are
explicitly marked `STRUCTURAL` and do not pretend to implement a functional
requirement. Because the complete trusted specification remains in the approved
context, every PSI retains its source/chunk/artifact provenance.

Coverage records approved and represented outputs, referenced and unmapped PSI
items, structural/domain file identities, blockers, and warnings. Unmapped PSI
items are reported rather than treated as implemented. Missing mandatory API or
database detail blocks a plan. Missing optional named UI-flow or backend-domain
detail produces a warning and no fabricated domain file.

Plan and file IDs are deterministic SHA-256-derived server identities. The
source fingerprint binds the run, specification/source/decision digests,
readiness, selected outputs, approval, effective stack, and adaptation evidence.
The plan fingerprint binds normalized planning content. A changed input or
policy version changes the relevant identities and fingerprints.

## QuickBook example

For approved QuickBook frontend, backend, database, API, configuration,
container, structure, and Git-summary outputs—with verified `/api/bookings`, a
`bookings` entity, and a named `Booking Flow`—the plan includes structural
entries plus:

- `backend/src/routes/bookings.routes.js`, supported by the API PSI items;
- `database/schema.sql`, supported by the database PSI item;
- `frontend/src/pages/booking-flow-page.jsx`, supported by the UI-flow PSI; and
- a non-file `GIT_SUMMARY` deliverable.

The example does not infer additional endpoints, tables, fields, screens, or
business behavior.

## Future integration boundary

GEN-R1.3 may select and integrate a generation provider that accepts only a
validated non-blocked plan plus its approved context. Model output must remain
constrained to planned paths and responsibilities. A later writer should own
workspace persistence and must not treat the in-memory plan as proof that files
were generated, built, tested, or delivered.

**GEN-R1.2 does not generate application code.** It performs no model loading or
inference, file write, dependency installation, execution, correction, GitHub
operation, Git operation, AgentRun transition, or Agent 4 handoff.
