# AgileFlow AI Task Assignment and Branch Ownership

Project ID: **J26-SE-358**

This document records official implementation ownership. Ownership prevents duplicate work; it does not permit changing shared contracts without coordination.

## Team Ownership

### N A Illangasinghe — IT23391536

- **Official component:** Requirement Gathering and Analysis Agent
- **Branch:** `feature/agent-requirements`
- **Owned scope:** client-input handling; requirement processing; SRS summary; functional/non-functional requirements; user stories; acceptance criteria; ambiguity, conflict, duplicate, and missing-information findings; requirement traceability; H1 readiness and component UI/API work.
- **Shared dependencies:** Project and input records; Shared Knowledge Base; canonical schemas and IDs; Orchestrator stage/gate state; common response/error utilities; shared frontend layout/components/services.
- **Coordinate before modifying:** design, implementation, testing, Orchestrator, shared database/core/schema files, routes, layout/theme, API/data/workflow contracts.

### Kulunu Kasthuri Arachchi — IT23375628

- **Official component:** Project Management and Design Agent
- **Branch:** `feature/agent-design-planning`
- **Owned scope:** backlog and sprint planning; UML, API, database, UI-flow, and wireframe artifacts; Jira-ready/mock items; requirement-to-design mappings; H2 readiness and component UI/API work.
- **Shared dependencies:** approved H1 outputs; Shared Knowledge Base; canonical design/backlog schemas and IDs; Orchestrator; shared UI and service layers.
- **Coordinate before modifying:** requirement extraction, implementation generation, test execution, Orchestrator, shared database/core/schema files, routes, layout/theme, contracts.

### W M D D Karunarathna — IT23145320

- **Official component:** Implementation and Git Automation Agent
- **Branch:** `feature/agent-implementation`
- **Owned scope:** selected prototype structure/modules; implementation artifact metadata; Git/workspace simulation or approved integration; build/runtime execution logs; bounded self-fix behavior; requirement/design/test-to-code mappings; H4 readiness and component UI/API work.
- **Shared dependencies:** approved H1-H3 artifacts; Shared Knowledge Base; test specifications; Orchestrator retries and routing; shared execution/traceability contracts.
- **Coordinate before modifying:** requirement/design generation, testing/validation ownership, global workflow decisions, shared database/core/schema files, routes, layout/theme, contracts.

### R A K Hansika — IT23140998

- **Official component:** Testing, Validation and Security Agent
- **Branch:** `feature/agent-testing-validation`
- **Owned scope:** both pre-code test planning and post-code testing/validation/security; test specifications and skeleton metadata; security test cases; requirement-to-test mappings; test results; bugs; security findings; regression/validation evidence; H3/H5 readiness and component UI/API work.
- **Shared dependencies:** approved requirements/designs/implementation; Shared Knowledge Base; Orchestrator correction loops; implementation fixes; report/traceability functionality.
- **Coordinate before modifying:** implementation generation logic, design/backlog generation, requirement processing, Orchestrator global transitions, shared database/core/schema files, routes, layout/theme, contracts.

Pre-code and post-code work are two phases of this one research component, not separate agents.

## Shared Ownership

| Shared area | Ownership and coordination |
|---|---|
| Central SDLC Orchestrator | All members contribute; foundation/group leader controls shared workflow integration on `feature/orchestrator` |
| Shared Knowledge Base | Foundation/shared responsibility; database infrastructure and collection contracts require shared review |
| Traceability and reports | Shared responsibility coordinated on `feature/reports-traceability` |
| Final integration | All members through reviewed PRs into `develop` |
| Project foundation | Foundation team on `feature/project-foundation` |
| UI foundation | UI design/foundation team on `feature/ui-design-system` |

Individual agents do not own global transitions, shared contracts, or another component's domain logic.

## Branch Map

| Branch | Responsibility |
|---|---|
| `main` | Stable milestone/final version only |
| `develop` | Reviewed, runnable integration branch |
| `feature/project-foundation` | Repository, backend/database foundation, shared documentation and contracts |
| `feature/ui-design-system` | Central theme, layout, reusable components, Figma handoff |
| `feature/agent-requirements` | Requirement Gathering and Analysis Agent |
| `feature/agent-design-planning` | Project Management and Design Agent |
| `feature/agent-implementation` | Implementation and Git Automation Agent |
| `feature/agent-testing-validation` | Testing, Validation and Security Agent |
| `feature/orchestrator` | Stage control, H1-H5, routing, bounded retries, workflow events |
| `feature/reports-traceability` | Final reports, exports, and traceability matrix |

## Integration Rules

1. No direct development or push to `main`.
2. After initial setup, changes enter `develop` through pull requests.
3. Each member works in the assigned feature branch and owned areas.
4. Update the feature branch from `develop` before opening a PR.
5. At least one other member reviews each PR; shared contract/workflow/layout changes require group-leader review.
6. Integrate one handoff at a time in the approved order: Requirements → H1 → Design → H2 → Pre-Code Testing → H3 → Implementation → H4 → Post-Code Validation/Security → H5 → Reports/Traceability.
7. Store agent outputs through the Shared Knowledge Base using approved schemas and IDs.
8. Every gate decision and major transition must produce a workflow event when that functionality is implemented.
9. Update API/data/workflow documentation in the same PR as an approved contract change.
10. Keep incomplete work on feature branches and keep `develop` runnable.

## Protected Shared Areas

Changes require the responsible foundation/shared owner and affected component review:

- root governance documents and `docs/` implementation contracts;
- `backend/app/main.py`, `backend/app/core/`, `backend/app/database/`, `backend/app/common/`, and shared schemas;
- Orchestrator stage/status definitions and approval transitions;
- frontend routes, shared layout, centralized theme, shared API client, and common/workflow components;
- dependency and environment-example files.

The canonical database connection file is `backend/app/database/mongodb.py`. Older `connection.py` references in general planning material are not the repository contract.

## Pull Request Minimums

Each PR states its purpose, changed files, API/schema/workflow impacts, tests, UI screenshots where applicable, known issues, and AI-generated portions. It must not include unrelated files or another member's work without coordination.

**Team principle:** Incomplete feature branch is acceptable. Broken develop branch is not acceptable.
