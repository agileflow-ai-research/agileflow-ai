# AgileFlow AI Frontend Guide

Project ID: **J26-SE-358**  
Primary authorities: **File 09 — Frontend Implementation and Centralized Theme Guide** and **File 10 — Reusable Component and UI Integration Plan**

## Current Status

The repository's `frontend/` directory currently contains only `.gitkeep`. React, Vite, Tailwind CSS, routes, services, theme files, and components are **planned and not implemented**. Paths below are the approved implementation target, not a statement of current availability.

## Stack and Design Principle

- React with Vite
- Tailwind CSS backed by centralized CSS variables/theme values
- React Router for planned application routing
- One Fetch or Axios wrapper through a shared API client
- React state first; optional global state only later where justified
- Controlled forms or React Hook Form as source-supported options

Build one reusable dark SaaS design system first, then shared layout, then pages, then API integration. Do not build agent pages as independent themes.

## Intended Structure

```text
frontend/src/
├── app/                 App and route configuration
├── assets/
├── components/
│   ├── layout/
│   ├── ui/
│   ├── forms/
│   ├── data-display/
│   ├── workflow/
│   ├── agents/
│   └── reports/
├── pages/
│   ├── dashboard/
│   ├── projects/
│   ├── requirements/
│   ├── design/
│   ├── testing/
│   ├── implementation/
│   ├── orchestrator/
│   └── reports/
├── services/
├── styles/
├── constants/
├── hooks/
├── utils/
└── mock-data/
```

Do not create parallel folders such as `ui2`, `finalUI`, `new-components`, `agentScreens`, or `temp-pages`.

## Central Theme

These are the exact File 09 tokens:

| Token | Value | Use |
|---|---|---|
| `bg-main` | `#0B0714` | Application background |
| `bg-sidebar` | `#120A24` | Sidebar/navigation |
| `bg-card` | `#1A102F` | Primary cards/panels |
| `bg-card-soft` | `#21153A` | Nested/secondary surfaces |
| `border-soft` | `#342454` | Borders and dividers |
| `primary-purple` | `#7C3AED` | Primary actions/active state |
| `accent-violet` | `#A855F7` | Highlights/focus/selected stage |
| `accent-blue` | `#38BDF8` | Informational state and links |
| `text-primary` | `#F8FAFC` | Headings/important labels |
| `text-secondary` | `#CBD5E1` | Descriptions/body support |
| `text-muted` | `#94A3B8` | Metadata/disabled content |
| `success` | `#22C55E` | Approved/passed/completed |
| `warning` | `#F59E0B` | Pending/waiting/attention |
| `error` | `#EF4444` | Failed/rejected/security error |

Store them centrally in `styles/tokens.css` and map them into Tailwind/shared classes or a central theme object. Never repeat arbitrary page colors.

### Status presentation

| Status | Color token |
|---|---|
| `PENDING` | `text-muted` / `border-soft` |
| `IN_PROGRESS` | `accent-blue` |
| `WAITING_FOR_APPROVAL` | `warning` |
| `APPROVED` | `success` |
| `REJECTED` | `error` |
| `FAILED` | `error` |
| `COMPLETED` | `success` |

Use a text label/icon as well as color. `REQUEST_CHANGES` and `RETRYING` are shared status values, but File 09 does not define their exact color mapping; obtain UI approval before adding mappings. `ON_HOLD` and `HUMAN_REVIEW_REQUIRED` are workflow runtime controls, not generic artifact-status additions.

## Typography, Spacing, and Shape

- Page title: 28–32px, weight 700.
- Section heading: 20–24px, weight 600/700.
- Card title: 16–18px, weight 600.
- Body: 14–16px, weight 400/500.
- Helper text: 12–13px, weight 400.
- Use the 8px-oriented spacing set: 4, 8, 12, 16, 24, 32, 48.
- Page padding: 24px desktop and 16px tablet/mobile.
- Card padding: 20px or 24px.
- Buttons: minimum 40px high; important actions 44px.
- Radius: 12px cards, 10px buttons, 8px inputs/badges.
- Use subtle shadows; avoid decorative/glowing excess.

## Shared Layout Components

| Component | Responsibility |
|---|---|
| `MainLayout` | Shared application shell |
| `Sidebar` | Dashboard, projects, agents, Orchestrator, traceability, reports navigation |
| `Topbar` | Project selector, workflow badge, search placeholder, notifications, profile placeholder |
| `PageContainer` | Responsive page width, padding, and spacing |
| `PageHeader` | Title, subtitle, breadcrumbs, actions |
| `SectionHeader` | Consistent section headings |

No agent page creates its own sidebar, topbar, header, or page-spacing system.

## Base UI Components

| Component | Expected use |
|---|---|
| `Button` | Primary, secondary, ghost, and danger actions; small/medium/large sizes |
| `Card` | Default, elevated, bordered, or subtle-gradient surfaces |
| `StatusBadge` | Shared workflow/artifact/test/approval statuses |
| `Modal` | Approval/rejection/clear confirmations |
| `Tabs` | Artifact group navigation |
| `AlertBox` | Info/success/warning/error feedback |
| `EmptyState` | No project/artifact/test/finding/report |
| `LoadingState` | API and generation loading |
| `ErrorState` | Failed API/unsupported action with retry where appropriate |

## Workflow Components

| Component | Responsibility |
|---|---|
| `WorkflowStepper` | Complete stage and gate sequence/current position |
| `StageStatusCard` | Stage owner, status, latest output, next action |
| `ApprovalGateCard` | H1-H5 artifact summary, comment, and valid decisions |
| `ApprovalHistory` | Reviewer, decision, comment, timestamp history |
| `NextActionPanel` | Valid next human/system action |
| `FailureRouteCard` | Issue source, route target, correction action |

Approval controls remain disabled until required artifacts exist. Show reviewer, timestamp, comment, and reviewed version. UI state must not advance independently of an accepted backend workflow response.

## Agent-Reusable Components

| Component | Responsibility |
|---|---|
| `AgentSummaryCard` | Official agent name, responsibility, counts, current status |
| `AgentInputPanel` | Source artifacts for the current phase |
| `AgentOutputPanel` | Generated artifact summaries/review actions |
| `ArtifactList` | Requirements, designs, tests, code, reports |
| `ArtifactPreview` | Selected artifact content |
| `QualityIssuePanel` | Requirement issues, bugs, security findings |
| `GenerationActionPanel` | Generate/regenerate/save/send-for-approval actions |

UI labels use official component names rather than only “Agent 1” through “Agent 4.” Pre-Code and Post-Code pages represent phases of the same Testing, Validation and Security Agent.

## Report and Data Components

| Component | Responsibility |
|---|---|
| `DataTable` | Shared rows, columns, actions, loading/empty behavior |
| `TraceabilityTable` | Requirement/design/backlog/test/code/finding/status relationships |
| `ReportCard` | Report type, generated date, status, export action |
| `MetricCard` | Project, approval, test, bug, security metrics |
| `ActivityTimeline` | Workflow event history |
| `LogViewer` | Build/runtime/test/security logs with readable scrolling |
| `ExportPanel` | Later report export controls, disabled until an artifact exists |

`ExportPanel` formats must follow the eventual API contract. File 10 mentions PDF/DOCX/CSV while File 06 mentions PDF/DOCX/JSON later; no final export-format set is approved.

## Planned Application Routes

| Page | Route | Owner |
|---|---|---|
| Dashboard | `/dashboard` | Foundation |
| Projects | `/projects` | Foundation |
| Project Workflow | `/projects/:projectId/workflow` | Foundation/Orchestrator |
| Requirement Gathering and Analysis | `/projects/:projectId/requirements` | Requirement component |
| Project Management and Design | `/projects/:projectId/design` | Design component |
| Pre-Code Test Planning | `/projects/:projectId/testing/pre-code` | Testing component |
| Implementation and Git Automation | `/projects/:projectId/implementation` | Implementation component |
| Testing, Validation and Security | `/projects/:projectId/testing/validation` | Testing component |
| Orchestrator | `/projects/:projectId/orchestrator` | Foundation/Orchestrator |
| Traceability | `/projects/:projectId/traceability` | Reports/Traceability |
| Final Reports | `/projects/:projectId/reports` | Reports/Traceability |

These are client-side routes. API paths use `{project_id}` and `/api/v1`; do not confuse the route parameter conventions.

## Service and API Strategy

The data flow is:

```text
Page → custom hook/state coordinator → module service → apiClient → backend
Page → clean props → reusable visual component
```

Use one `apiClient` for the environment base URL, headers, JSON handling, and normalized errors. Module service responsibilities cover projects, workflow, requirements, design, testing, implementation, approvals, and reports. File 06 and Files 08–10 use different example filenames (`projectApi.js` versus `projectService.js`); the final naming choice is not formally resolved. Do not create both sets.

Rules:

- Pages must not directly call `fetch` or Axios.
- Small visual components must not know endpoint details.
- Do not hardcode project IDs.
- Use the canonical response envelope in [API_CONTRACT.md](../api-contracts/API_CONTRACT.md), not File 09's alternate `metadata` example.
- Show loading, empty, error, and success states.
- Normalize API errors centrally and show workflow violations clearly.

## Page Composition Expectations

- Dashboard: metrics, workflow stepper, project table, activity timeline.
- Create Project: labeled inputs, client idea, upload placeholder, safe validation/feedback.
- Project Workflow: workflow stepper, stage cards, approval gate, next action.
- Requirements: agent summary/input/output, quality issues, H1.
- Design: artifact list, backlog/data tables, tabs, traceability, H2.
- Pre-Code Testing: artifacts, test table, traceability, H3.
- Implementation: artifacts, logs, activity, H4.
- Post-Code Validation/Security: metrics, results/findings tables, logs, report, H5.
- Orchestrator: stepper, failure routing, activity, retry/status data.
- Reports: report cards, traceability table, export controls.

Every page shows title, description, current project context, and workflow state where applicable.

## Responsive and Accessibility Rules

- Maintain readable contrast on dark backgrounds.
- Use visible keyboard focus and keyboard-operable controls.
- Every input has a visible label and error area.
- Do not communicate state by color alone.
- Use explicit action labels such as “Approve,” “Request Changes,” and “Run Validation.”
- Allow tables to scroll horizontally at smaller widths.
- Keep long artifacts/logs in scrollable panels rather than breaking the page.
- Sidebar collapse may follow after MVP; desktop/tablet correctness comes first.

## Figma-to-Code Integration

The Figma handoff supplies final page/navigation flow, desktop frames, component frames, exact tokens, typography/spacing, variants, approval/workflow components, traceability tables, and loading/error/empty states.

For each screen:

1. identify repeated layout and UI patterns;
2. map Figma components to the approved React component names;
3. implement or reuse the shared component first;
4. compose the page from shared components;
5. keep API/data mapping in services/hooks;
6. update the shared component once when Figma changes.

Screenshots alone are not a complete handoff. Do not copy non-token Figma colors or rename established components without approval.

## Build Order and Quality Gate

1. Initialize Vite/React and Tailwind/central tokens.
2. Build global styles and shared layout.
3. Build high-use base/state/form components.
4. Build data, workflow, approval, agent, and report components incrementally.
5. Compose Dashboard/Projects and placeholder workflow pages.
6. Connect services after backend contracts are implemented.
7. Replace mock content one component workflow at a time.

Before a frontend PR: verify approved structure/routes/tokens, reuse, loading/error/empty states, accessibility, basic responsive behavior, service-layer API use, no hardcoded project IDs, no duplicates, and Figma consistency. Include screenshots when UI changes.

## Contract Resolution Notes

1. File 09 is authoritative for exact theme tokens; no alternate theme is introduced.
2. File 10 is authoritative for the detailed reusable component inventory.
3. File 06's API response envelope overrides File 09's `metadata` example.
4. Frontend service filename variants and final report export formats remain unresolved; select one through human approval before implementation.
