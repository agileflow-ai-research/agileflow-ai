# Agent 4 — Testing, Validation and Security Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Agent type: `TESTING_VALIDATION`

Run modes: `TEST_GENERATION`, `VALIDATION`
Contract version: **v1.1 — revision of v1.0 (frozen for Progress Presentation 1)**

### Revision note (v1.1)

v1.0 was frozen for Progress Presentation 1. v1.1 keeps that freeze's meaning for the parts that matter to other members and to the shared foundation:

- The selectable output vocabularies of **both** modes are preserved exactly. No code is added, renamed, or removed. `TEST_CASE_PLAN` is deliberately not a selectable code.
- The two-mode boundary and the rule that Agent 4 never uses `DEFAULT` are unchanged.
- The Mode B (`VALIDATION`) contract text is preserved, with only the wording changes noted in §3.
- The v1.0 Mode A flow (normalized input → one direct LLM call → generated tests) is **superseded**. It is replaced by the staged pipeline in §2, which requires an approved Test Case Plan before detailed generation.
- Shared contracts (common project/run, UI/API, Agent 1, Agent 2) are unchanged.

## 1. Standalone Purpose and Mode Separation

Agent 4 — Testing, Validation and Security Agent is one research agent with two explicit standalone modes:

1. `TEST_GENERATION`
2. `VALIDATION`

They must not be combined into one ambiguous screen, input form, selection list, or process. A user chooses the mode before supplying mode-specific inputs and outputs. A single Agent 4 project may retain runs from either mode, with every run recording its own `run_mode`.

Agent 4 must not use `DEFAULT`.

`TEST_GENERATION` is **pre-code capable**: it can run from upstream requirement and design artifacts without any implementation existing. `VALIDATION` assumes an existing implementation to validate.

## 2. Mode A — `TEST_GENERATION`

### 2.1 Purpose

Generate test specifications from requirement and design context, through a staged pipeline that ends in a human-approved Test Case Plan. Where sufficient technical context exists, executable test code may also be produced. The result must distinguish a test specification from test code, and neither may be presented as executed.

### 2.2 Input source rule (standalone mode)

Agent 4 Mode A receives artifacts that are **equivalent to outputs that would normally come from upstream agents**. In standalone mode they are **manually supplied**. Wording in the UI, API documentation, and results must not imply that Agent 1 or Agent 2 actually executed for that input. Use phrases such as:

- "Normally supplied by Agent 1"
- "Normally supplied by Agent 2"
- "Manually supplied in standalone mode"

Mode A **must not require Agent 3 implementation output**. Pre-code test generation is a supported workflow (tests-first / TDD-like). Agent 3 source or implementation information is **optional additional context** and only affects executability (§2.20), never whether a specification can be generated.

### 2.3 Required inputs

```text
project_name
```

At least one **usable primary functional source** is required from:

```text
FUNCTIONAL_REQUIREMENTS   (normally supplied by Agent 1)
USER_STORIES              (normally supplied by Agent 1 or Agent 2)
ACCEPTANCE_CRITERIA       (normally supplied by Agent 1)
SRS                       (normally supplied by Agent 1)
```

"Usable" means the source contains content that can be normalized. A declared field without content does not satisfy this rule.

### 2.4 Upstream vocabulary: Agent 1 (actual contract codes)

Source: [AGENT_1_REQUIREMENTS_CONTRACT.md §4–5](AGENT_1_REQUIREMENTS_CONTRACT.md). Agent 4 consumes these as manually supplied artifacts, normally produced by Agent 1.

| Agent 1 code | Role for Agent 4 | Required / optional | Contribution to Mode A | Readiness effect |
|---|---|---|---|---|
| `FUNCTIONAL_REQUIREMENTS` | Primary functional source | At least one primary source | Behavior scenarios; FR identities for traceability | Satisfies functional-context rule |
| `USER_STORIES` | Primary functional source | At least one primary source | Actor/goal context for E2E and acceptance tests; US identities | Satisfies functional-context rule |
| `ACCEPTANCE_CRITERIA` | Primary functional source | At least one primary source; strongly recommended | Highest-value input: each AC yields at least one plan item; AC identities | Missing AC produces a warning |
| `SRS` | Primary functional source (container) | At least one primary source | Source for FR/NFR sections when individual lists are not supplied; sections are mapped to FR/NFR IDs | Satisfies functional-context rule |
| `NON_FUNCTIONAL_REQUIREMENTS` | Optional quality context | Optional | Performance, security, and reliability targets; measurable thresholds | Missing NFR produces an info finding for non-functional test types |
| `PERSONAS` | Optional role context | Optional | Roles for authorization and access scenarios. Only roles are used; personal profile data is not | Minor |
| `QUALITY_FINDINGS` | Optional readiness signal | Optional | Categories `AMBIGUITY`, `MISSING_INFORMATION`, `CONFLICT`, `DUPLICATE`, `INCONSISTENCY` inform readiness warnings and plan `missing_context`. They are not test content | Warning per relevant finding |
| `CLARIFICATION_QUESTIONS` | Optional readiness signal | Optional | Open questions appear as `clarification_needed` on affected plan items and as readiness warnings | Warning while unresolved |

### 2.5 Upstream vocabulary: Agent 2 (actual contract codes)

Source: [AGENT_2_DESIGN_PLANNING_CONTRACT.md §6](AGENT_2_DESIGN_PLANNING_CONTRACT.md). Agent 4 consumes these as manually supplied artifacts, normally produced by Agent 2.

| Agent 2 code | Role for Agent 4 | Required / optional | Contribution to Mode A | Readiness effect |
|---|---|---|---|---|
| `SYSTEM_ARCHITECTURE` | Design context | Optional | Component boundaries and interactions → integration test scope | Minor |
| `UML_DIAGRAMS` | Design context | Optional | Interaction and structure relationships → integration and interface tests. Textual diagram source is usable; image-only diagrams are `PENDING_ANALYSIS` | Minor |
| `DATABASE_SCHEMA` | Design context | Optional; **required** when persistence or uniqueness tests are requested | Entities, keys, uniqueness and integrity constraints → persistence and integrity tests | Yes: `DATABASE_CONTEXT_MISSING` when persistence testing applies |
| `API_SPECIFICATION` | Design context | Optional; **required** when API tests are requested | Endpoints, inputs, outputs, status codes, auth assumptions → API test plan items. JSON or YAML preferred | Yes: `API_CONTEXT_MISSING` when API tests are requested |
| `WIREFRAMES` | Design context | Optional | Screen structure for UI test planning. Usually `IMAGE` → `PENDING_ANALYSIS` in standalone PP1 | Warning: visual context pending |
| `UI_FLOW` | Design context | Optional; **required** when E2E tests are requested | Navigation and task flows → E2E test plan items | Yes: `UI_FLOW_CONTEXT_MISSING` when E2E tests are requested |
| `USER_STORIES` | Primary functional source | Same group as Agent 1 `USER_STORIES` | Same as §2.4. The origin agent is recorded because the code name is shared | As §2.4 |
| `FEATURES` | Grouping context | Optional | Provides `feature_ref` grouping for plan items | Minor |

**Not used by Mode A in PP1.** These Agent 2 codes do not contribute to test planning and have no readiness effect. If supplied, they are accepted only as optional text context and are not interpreted as test sources:

```text
PRODUCT_BACKLOG
EPICS
TASKS
SPRINT_PLAN
TASK_ASSIGNMENT
JIRA_PLAN
```

Sprint, capacity, and assignment artifacts do not affect test generation and must not be required.

### 2.6 Optional context

| Context | Normally supplied by | Effect |
|---|---|---|
| Implementation or existing source code | Agent 3 output or manual upload | Required only for `EXECUTABLE_POSSIBLE` feasibility. Never required for specifications |
| Technology stack (`technology_stack`) | Agent 2 `preferred_technology_stack` input, or user | Required for `EXECUTABLE_POSSIBLE` feasibility. Not an Agent 2 output code |
| Technical constraints | Agent 2 technical inputs | Context for test data and environment assumptions |

### 2.7 Compatibility aliases

v1.0 used generic input names. They are accepted **only as input aliases at the boundary**. They are normalized to the official vocabulary before any persistence or output, and they never appear in new outputs.

| Legacy input name (v1.0) | Official Agent 4 mapping |
|---|---|
| `requirements` | `FUNCTIONAL_REQUIREMENTS` |
| `user_stories` | `USER_STORIES` |
| `acceptance_criteria` | `ACCEPTANCE_CRITERIA` |
| `SRS` | `SRS` |
| `system_architecture` | `SYSTEM_ARCHITECTURE` |
| `api_specification` | `API_SPECIFICATION` |
| `database_schema` | `DATABASE_SCHEMA` |
| `ui_specification` | Ambiguous. The submitter must declare `UI_FLOW` or `WIREFRAMES` |
| `existing_source_code` | Optional implementation context (§2.6) |
| `technology_stack` | Agent 4 context key (§2.6) |

### 2.8 Source types

Source type is recorded separately from artifact type.

| Source type | Mode A PP1 status | Accepted formats | Behavior |
|---|---|---|---|
| `TEXT` | MUST | Manual text entry | Normalized directly with provenance |
| `DOCUMENT` | MUST (extraction integration) | `PDF`, `DOCX`, `TXT`, `MD`, `JSON`, `YAML` | Extracted through the shared extraction dependency (§7.1), then normalized |
| `IMAGE` | MUST as accepted and preserved only | Image upload | Accepted, provenance preserved, `analysis_status = PENDING_ANALYSIS`. **Semantic understanding is not implemented.** An image contributes no understood testing context |

Agent 1 source types `AUDIO`, `VIDEO`, and `LIVE_INTERVIEW` are not Agent 4 Mode A sources.

**Current limitation (stated explicitly):** IMAGE understanding does not exist. An image is never described as analyzed. Readiness reports it with a `VISUAL_CONTEXT_PENDING` finding.

### 2.9 Contract name → Agent 4 internal artifact type

Agent 4 must not silently rename upstream artifacts. Each internal artifact type keeps its **origin**: the origin agent and the original contract code.

| Upstream contract code | Origin agent | Agent 4 internal artifact type | Known name in another agent's enum | Notes |
|---|---|---|---|---|
| `FUNCTIONAL_REQUIREMENTS` | Agent 1 | `FUNCTIONAL_REQUIREMENTS` | — | |
| `NON_FUNCTIONAL_REQUIREMENTS` | Agent 1 | `NON_FUNCTIONAL_REQUIREMENTS` | — | |
| `USER_STORIES` | Agent 1 or Agent 2 | `USER_STORIES` | Agent 3: `USER_STORIES` | Origin agent recorded because the code is shared |
| `ACCEPTANCE_CRITERIA` | Agent 1 | `ACCEPTANCE_CRITERIA` | Agent 3: `ACCEPTANCE_CRITERIA` | |
| `PERSONAS` | Agent 1 | `PERSONAS` | — | |
| `QUALITY_FINDINGS` | Agent 1 | `QUALITY_FINDINGS` | — | |
| `CLARIFICATION_QUESTIONS` | Agent 1 | `CLARIFICATION_QUESTIONS` | — | |
| `SRS` | Agent 1 | `SRS` | Agent 3: `SRS` | |
| `SYSTEM_ARCHITECTURE` | Agent 2 | `SYSTEM_ARCHITECTURE` | Agent 3: `SYSTEM_ARCHITECTURE` | |
| `UML_DIAGRAMS` | Agent 2 | `UML_DIAGRAMS` | Agent 3: `UML_DIAGRAMS` | |
| `DATABASE_SCHEMA` | Agent 2 | `DATABASE_SCHEMA` | Agent 3: `DATABASE_SCHEMA` | |
| `API_SPECIFICATION` | Agent 2 | `API_SPECIFICATION` | Agent 3: `API_SPECIFICATION` | |
| `WIREFRAMES` | Agent 2 | `WIREFRAMES` | Agent 3: **`UI_WIREFRAMES`** | Agent 3's name is not used as the Agent 4 key. Recorded as an alias only |
| `UI_FLOW` | Agent 2 | `UI_FLOW` | Agent 3: `UI_FLOW` | |
| `FEATURES` | Agent 2 | `FEATURES` | — | |
| `TASKS` (not used in PP1) | Agent 2 | `TASKS` | Agent 3: **`IMPLEMENTATION_TASKS`** | Recorded as an alias only |
| `preferred_technology_stack` (input) | Agent 2 input | `technology_stack` (context key) | Agent 3: `TECHNOLOGY_STACK` | Context key, not an artifact |

**Rule:** the internal type equals the contract code. Another agent's enum name is recorded as an alias for traceability and is never used as an Agent 4 key. Changing this mapping requires team agreement (§10).

### 2.10 Mode A staged pipeline

```text
Upstream artifacts (manually supplied in standalone mode)
    ↓
1. Input collection          (TEXT / DOCUMENT / IMAGE, source identity, mode check)
    ↓
2. Extraction                (shared extraction dependency; no duplicate extractors)
    ↓
3. Normalization             (NormalizedTestingArtifact list; the only input downstream stages consume)
    ↓
4. Testing-relevant classification   (rules first; AI for residual cases only)
    ↓
5. Traceability preparation  (upstream IDs preserved; traceability index built)
    ↓
6. Testability / readiness   (deterministic rules; READY / READY_WITH_WARNINGS / NOT_READY)
    ↓
7. TEST CASE PLAN            (first-class intermediate artifact; generated before detailed tests)
    ↓
8. HUMAN REVIEW / APPROVAL   (standalone plan review; §2.16)
    ↓
9. Detailed structured test generation   (only from APPROVED plan items)
    ↓
10. Optional executable test generation   (only when feasibility allows; still NOT_EXECUTED)
```

**Do not skip directly from normalized inputs to generated tests.** Detailed generation requires an approved Test Case Plan.

| Stage | Method | PP1 status |
|---|---|---|
| Input collection | Deterministic validation | MUST |
| Extraction | Shared infrastructure | MUST (integration) |
| Normalization | Deterministic | MUST |
| Classification | Rule-based first; AI assists residual cases | MUST (rules); AI later |
| Traceability preparation | Deterministic ID parsing and index | MUST |
| Readiness | Deterministic rules | MUST |
| Test Case Plan | Deterministic skeleton, AI-assisted enrichment, schema and reference validation | MUST |
| Human review | Human decisions, recorded | MUST |
| Detailed generation | AI-assisted structured generation, schema and reference validation | MUST |
| Executable generation | Gated generation | LATER |

### 2.11 NormalizedTestingArtifact (conceptual, not implemented)

All Mode A stages after normalization consume `NormalizedTestingArtifact` records, not raw files. The concept preserves:

- `artifact_id`: stable identifier
- `artifact_type`: internal type (§2.9)
- `source_type`: `TEXT`, `DOCUMENT`, or `IMAGE`
- `source_identity`: upload or text identifier, filename or label
- `content`: normalized text
- `structured_data`: optional parsed content (for example requirement list, AC list, or API endpoints)
- `extraction_status` and `analysis_status` (`EXTRACTED`, `PENDING_ANALYSIS`, `FAILED`)
- `warnings`
- `provenance`: heading path, page, or span where available, and original source reference
- `origin_agent`: `AGENT_1`, `AGENT_2`, or `USER`
- `origin_contract_code`: the upstream code
- `traceability_ids`: upstream REQ/FR/NFR/US/AC identifiers found in the content

Images are included with `analysis_status = PENDING_ANALYSIS` and contribute no testing content.

### 2.12 Testing-relevant classification

Classification assigns testing-relevance labels to normalized content, with evidence. It does not generate tests.

**Initial taxonomy:**

```text
FUNCTIONAL_BEHAVIOR
VALIDATION_RULE
BOUNDARY_CONSTRAINT
UNIQUENESS_OR_INTEGRITY
API_CONTRACT
UI_FLOW
AUTHENTICATION
AUTHORIZATION
SECURITY_CONSTRAINT
PERFORMANCE_TARGET
RELIABILITY
ERROR_HANDLING
ACCEPTANCE_CONDITION
NON_TESTABLE_CONTEXT
```

**Method:**
- Deterministic rules are preferred first (cue patterns such as "must", "unique", "at most", "role", "encrypt", "within", "retry", and so on), with auditable rule identifiers.
- AI may assist **ambiguous or residual** cases later. Its output must be schema-validated and marked as AI-assisted.
- Every label carries **evidence**: the rule or model identifier and the source reference that supports it. Classification evidence remains traceable to the normalized artifact and provenance.
- A label is a suggestion for planning, not a finding. Human review can override it.
- Images are not classified. Their labels are absent until analysis exists.

Classification does not implement a classifier in this step.

### 2.13 Traceability chain

Intended standalone Mode A chain:

```text
REQ / FR / NFR      (upstream, Agent 1)
    ↓
USER STORY          (upstream, Agent 1 or Agent 2)
    ↓
ACCEPTANCE CRITERION (upstream, Agent 1)
    ↓
DESIGN CONTEXT      (upstream, Agent 2: API endpoint, DB entity, UI flow step)
    ↓
TEST PLAN ITEM      (generated, TP-###)
    ↓
GENERATED TEST      (generated, TC-###)
```

**ID rules:**
- Upstream IDs are preserved **exactly** as written. They are not renumbered.
- Generated plan items use `TP-###` and generated tests use `TC-###`. Exact allocation is an implementation detail.
- If an upstream artifact has no identifiers, Agent 4 assigns local identifiers and marks each affected link as a traceability gap. It does not invent upstream IDs.
- Every plan item and generated test must cite at least one upstream identifier, or be marked untraced with a reason.

**Scope:** standalone Agent 4 **must not write integrated `TraceabilityLink` records** in this stage. `TEST_TRACEABILITY` remains local and result-level (`scope = STANDALONE_RESULT`).

The traceability result includes a coverage view: which acceptance criteria have planned tests, which have none (gap), and which generated tests cite no upstream criterion.

### 2.14 Testability / readiness stage

Readiness is a deterministic analysis that runs **before** the Test Case Plan. It reuses the proven status vocabulary:

```text
READY
READY_WITH_WARNINGS
NOT_READY
```

**Gate:** `NOT_READY` blocks plan generation and reports why. `READY_WITH_WARNINGS` allows plan generation, and the warnings are carried into the plan. `READY` allows generation without warnings.

**Readiness answers these questions:**

1. Is usable requirement context present (at least one primary functional source, §2.3)?
2. Are acceptance criteria available?
3. Are requirements measurable (numbers, units, or ranges where the requirement implies a target)?
4. Is API context available when API tests are requested?
5. Is UI flow context available when E2E tests are requested?
6. Is database context available when persistence or integrity testing applies?
7. Are security-relevant requirements identifiable (authentication, authorization, data protection)?
8. Are unresolved clarification questions or `QUALITY_FINDINGS` present?
9. Is implementation or technology context available for executable generation?
10. Is visual context pending analysis (any `IMAGE` input)?

**Readiness and feasibility are separate.** Readiness answers "is there enough context to plan?". Feasibility answers "what kind of test output can be honestly produced?":

```text
SPECIFICATION_ONLY      structured specification; no executable code
EXECUTABLE_POSSIBLE     executable test code is possible, subject to §2.20
```

A `READY` input can still be `SPECIFICATION_ONLY`. Readiness must never be presented as proof that tests are executable.

Each readiness finding carries a code, a severity (`ERROR`, `WARNING`, `INFO`), the affected outputs, and the source references that caused it.

### 2.15 TEST CASE PLAN (first-class intermediate artifact)

The Test Case Plan is generated **before detailed tests**. It is the main Mode A intermediate artifact. It is **not** a selectable final output code (§2.18).

**Conceptual `TestCasePlanItem`:**

| Field | Meaning |
|---|---|
| `plan_item_id` | `TP-###` |
| `feature_ref` | Feature or requirement group under test |
| `requirement_refs` | Upstream FR/NFR identifiers |
| `user_story_refs` | Upstream US identifiers |
| `acceptance_refs` | Upstream AC identifiers |
| `design_refs` | API endpoints, DB entities, or UI flow steps (Agent 2 context) |
| `test_levels` | Applicable levels (for example unit, API, integration, functional, E2E, acceptance, security, regression) |
| `test_types` | Scenario types (for example positive, negative, boundary, validation, security, concurrency) |
| `scenario` | Short description of the scenario |
| `preconditions` | Required state before the test |
| `test_data` | Expected inputs and data, with concrete values where the source gives them |
| `expected_outcome` | Observable result |
| `expected_persistence` | Required persistence effect, for example "no duplicate account created" |
| `dependencies` | Other plan items or external services |
| `mocks_or_stubs` | Test doubles required |
| `priority` | Rule-derived, human-editable |
| `risk` | Rule-derived, human-editable |
| `automation_feasibility` | `SPECIFICATION_ONLY` or `EXECUTABLE_POSSIBLE` (§2.14) |
| `missing_context` | Context the plan item needs but does not have |
| `clarification_needed` | Open questions that block or qualify the item |
| `provenance` | Normalized artifact identifier and source location |
| `review_state` | Review status (§2.16) |
| `reviewer_note` | Free-text reviewer note |

**The field list is conceptual.** Exact types and naming are implementation decisions. The important rule is below.

**Contract rule:** **detailed test generation must be based on an approved Test Case Plan.** Items that are rejected or removed are never generated.

**Example** (from the planning brief): `REQ-004 → US-008 → AC-011` yields planned items for a valid unique email, a duplicate email, a malformed email, a missing email, and a concurrent duplicate registration, with the expected persistence "no duplicate account created".

**Method:**
- Deterministic: one skeleton item per acceptance criterion (positive and negative); integrity items from database constraints; endpoint and status items from the API specification; ID and reference validation.
- AI-assisted: scenario expansion (concurrency, injection, edge cases) and rewriting of vague criteria into testable conditions. Output is schema-validated and carries provenance.
- Hybrid: deterministic skeleton, AI enrichment, deterministic validation.

### 2.16 Human review / approval point

A standalone human review point follows Test Case Plan generation.

**Supported actions:**

```text
APPROVE
REJECT
EDIT
REMOVE
ADD_SCENARIO
CHANGE_PRIORITY
REQUEST_CLARIFICATION
REQUEST_REGENERATION
```

**Rules:**
- This is **standalone plan review**. It is **not** the integrated AgileFlow H1 approval workflow.
- Standalone mode does not write integrated Approval records unless a future contract explicitly requires it.
- Each action is recorded as a reviewable decision. Earlier decisions are not overwritten.
- `REQUEST_CLARIFICATION` records the question on the affected items. Answers are later supplied as upstream input in a new run, following the immutable run rule in the common contract.
- `REQUEST_REGENERATION` is scoped to rejected or edited items. It produces a new plan revision rather than overwriting the approved one.
- Detailed generation is blocked until the plan has at least one `APPROVED` item and no unresolved `ERROR`-level readiness finding.

### 2.17 Detailed structured test generation

After an approved plan exists, Agent 4 generates structured specifications for the selected output codes (§2.18). Each generated item:

- traces to approved plan item identifiers and upstream IDs;
- cites source references that exist in the normalized input;
- uses unique generated identifiers (`TC-###`);
- carries `representation` and `execution_status` (§2.20).

Generation output is validated before it is accepted: source references, unique identifiers, the executable-requires-context rule, and traceability references that must point to generated test identifiers.

### 2.18 Final Mode A selectable output codes

The allowed `TEST_GENERATION` `selected_outputs` values are exactly:

```text
UNIT_TEST_CASES
API_TEST_CASES
INTEGRATION_TEST_CASES
FUNCTIONAL_TEST_CASES
E2E_TEST_CASES
REGRESSION_TEST_CASES
SECURITY_TEST_CASES
ACCEPTANCE_TEST_CASES
TEST_TRACEABILITY
```

The selection must be non-empty. `TEST_CASE_PLAN` is **not** in this list. It is a mandatory internal stage, not an optional final output. The approved plan and the readiness report may be shown to the user as read-only intermediate views, but they are not selectable output codes.

### 2.19 Output expectations

- Test-case outputs describe purpose, preconditions, inputs and data, steps or automated structure, expected result, and source coverage where applicable.
- Security test cases are safe validation specifications and must not introduce uncontrolled harmful execution.
- Generated executable tests must identify their target stack or framework and remain subject to controlled tool and execution policy.
- `TEST_TRACEABILITY` connects a requirement, user story, or acceptance criterion to the generated test specification within the standalone result context (§2.13).

`TEST_TRACEABILITY` does not force persistence in the integrated Project's `traceability_links` collection.

### 2.20 Specification vs executable code

**Structured test specification** (`representation = SPECIFICATION`):
- can be generated from sufficient requirement and design context;
- `executable = false`;
- `execution_status = NOT_EXECUTED`.

**Executable test code** (`representation = EXECUTABLE_CODE`):
- possible **only** when feasibility is `EXECUTABLE_POSSIBLE`, meaning sufficient technical or implementation context exists. Examples: a technology stack, an API contract, source code where needed, and a supported framework or profile;
- `executable = true`;
- **`execution_status = NOT_EXECUTED` still applies.** Actual execution belongs to `VALIDATION` mode.

**Honesty rules:**
- No output may claim that a test was executed in `TEST_GENERATION`.
- A missing stack or source must not be concealed by presenting abstract cases as executed tests. The readiness report and feasibility must say which outputs are specification-only.
- Executability does not affect whether a specification may be generated.

## 3. Mode B — `VALIDATION`

**Status note (v1.1):** Mode B remains a defined Agent 4 mode with its contract preserved below. It is **later work**, not the current rebuild priority. Nothing in this section is claimed as implemented by the Mode A rebuild. The only wording changes are the legacy input alias note and this status note.

Legacy input note: `requirements` in the Mode B input list is a legacy alias for `FUNCTIONAL_REQUIREMENTS` (§2.7).

### Purpose

Execute applicable tests/tools and validate an implementation using supplied source/project context.

### Required inputs

```text
project_name
source_code_or_project
```

### Recommended or conditionally required inputs

```text
requirements
acceptance_criteria
test_cases
technology_stack
build_command
run_command
environment_information
```

These inputs are optional only when the requested validation can be performed reliably without them. Examples:

- `ACCEPTANCE_CRITERIA_VALIDATION` requires usable `acceptance_criteria`.
- Executing user-supplied `test_cases` requires those cases and enough project/environment context.
- A build/run step requires safe known or derived commands and a supported environment.
- A coverage report requires applicable executable tests and tooling capable of collecting coverage.

The validator must reject or warn about an impossible selection rather than fabricate evidence.

### Selectable output codes

The allowed `VALIDATION` `selected_outputs` values are exactly:

```text
TEST_EXECUTION_REPORT
COVERAGE_REPORT
BUG_REPORTS
SECURITY_FINDINGS
CODE_QUALITY_REPORT
ACCEPTANCE_CRITERIA_VALIDATION
FINAL_VALIDATION_REPORT
```

The selection must be non-empty and must not contain `TEST_GENERATION` output codes.

### Validation flow

```text
Source Code / Project
        +
Test Cases / Specifications
        +
Acceptance Criteria
        ↓
prepare execution
        ↓
execute applicable tests/tools
        ↓
collect results
        ↓
analyze failures
        ↓
coverage / quality / security checks
        ↓
structured reports
```

Inputs shown with `+` are included when applicable to the requested validation. Execution must use bounded, controlled tools and preserve safe command/result evidence. A report must distinguish checks that passed, failed, were skipped, were unsupported, or lacked sufficient context.

### Output expectations

- `TEST_EXECUTION_REPORT`: executed suites/cases, environment, commands/tools, outcomes, failures, and skipped work.
- `COVERAGE_REPORT`: collected coverage scope and metrics with tooling/context; never estimated and presented as measured.
- `BUG_REPORTS`: structured defects linked in standalone context to relevant tests, requirements, acceptance criteria, or source areas.
- `SECURITY_FINDINGS`: structured security issues, evidence, severity rationale, affected context, and recommendations, without exposing exploitable secrets.
- `CODE_QUALITY_REPORT`: applicable maintainability/static-quality findings and tool/method context.
- `ACCEPTANCE_CRITERIA_VALIDATION`: criterion-by-criterion result with supporting evidence or an explicit inability to validate.
- `FINAL_VALIDATION_REPORT`: consolidated conclusion that identifies scope, evidence, failures, limitations, warnings, and readiness assessment.

## 4. Cross-Mode Validation and Normalization

Before engine execution, Agent 4 must:

1. require exactly one allowed `run_mode`;
2. apply only that mode's required-input rules;
3. require a non-empty selection from only that mode's output codes;
4. enforce conditional context needed for meaningful generation or validation;
5. for `TEST_GENERATION`, normalize inputs into `NormalizedTestingArtifact` records (§2.11), run readiness (§2.14), and require an approved Test Case Plan (§2.15–2.16) before detailed generation;
6. normalize input into the corresponding Agent 4 engine context, resolving legacy aliases (§2.7); and
7. preserve the serializable state, mode, and plan or review state in `input_snapshot`.

UI and API layers must not merge the two output vocabularies. A run cannot switch mode after its snapshot is recorded.

## 5. Results and Error Categories

Agent 4 returns mode-specific structured output in the common `AgentRunResult.outputs`. Applicable error categories include:

```text
INPUT_VALIDATION_FAILED
MODEL_EXECUTION_FAILED
STRUCTURED_OUTPUT_INVALID
TOOL_EXECUTION_FAILED
BUILD_FAILED
TEST_EXECUTION_FAILED
INTERNAL_ERROR
```

Failed tests are domain results and may contribute to reports/bug findings; `TEST_EXECUTION_FAILED` is used when the requested test execution itself cannot complete as required. Concrete terminal-status policy for test failures versus execution failure is an S1/S2 decision and must remain honest and consistent.

**v1.1 addition:** no new error code is introduced for the Mode A pipeline. A generation request made without an approved Test Case Plan, or from a `NOT_READY` input, is rejected with `INPUT_VALIDATION_FAILED` and a readiness-specific message.

## 6. Security and Tool Boundary

Source/project handling, dependency resolution, builds, test execution, scanners, and quality tools require controlled workspaces, sanitized commands, resource/time limits, and secret-safe logs. Tool choice, retry count, coverage thresholds, severity vocabulary, supported stacks, and environment provisioning are not frozen in S0.

Mode A adds one boundary: uploaded documents and images are untrusted input. They pass through the shared extraction dependency (§7.1), and images are never executed, rendered, or analyzed in PP1.

## 7. Isolation and Reuse

### 7.1 Shared extraction architectural dependency

Agent 3 currently owns working upload and document extraction infrastructure, located under `backend/app/modules/agents/implementation/`. It includes PDF, DOCX, TXT/MD, and JSON/YAML extraction, and upload storage.

**Decision:**
- Agent 4 **must not** independently duplicate PDF, DOCX, TXT/MD, or JSON/YAML extraction.
- The contract does not refactor Agent 3 in this revision.
- Reuse will be handled as a **dedicated cross-agent integration step**, after team agreement. The likely target is a neutral shared package. No shared package is created by this contract revision.
- Until then, the extraction and upload integration is an **architectural dependency**, and Agent 4 Mode A extraction work is blocked on that agreement.

### Secure Validation Execution Implementation

Executable `VALIDATION` is separated from `Agent4Engine` by a `ValidationExecutor`
boundary. `Agent4Engine` selects validation actions and interprets evidence;
`SandboxedValidationExecutor` alone stages files and invokes the sandbox. Shared
`AgentProject` and `AgentRun` lifecycle behavior remains outside the executor.

**A temporary directory is not a sandbox.** Temporary workspaces provide staging and
cleanup only. Executable validation is permitted only inside the bounded Docker
runtime. There is no unrestricted host-subprocess fallback. If Docker, its daemon, or
the required local image is unavailable, requested executable validation fails with
`TOOL_EXECUTION_FAILED`. Static-analysis-only validation may return explicitly
skipped execution evidence because it executes no supplied project code.

Supported Progress Presentation 1 profiles are server controlled:

| Profile | Local image | Fixed build | Fixed test |
|---|---|---|---|
| `PYTHON_PYTEST` | `agileflow/agent4-python-pytest:1.0` | `python -m compileall -q .` | `python -m pytest -q --disable-warnings --cov=.` |
| `NODE_NPM_TEST` | `agileflow/agent4-node-test:1.0` | `npm run build --if-present` | `npm test` |

The runtime uses `--pull never`; image provisioning is an administrator-controlled
setup step. Node dependencies must already be available in the supplied workspace or
image. Runtime dependency download is deliberately unsupported.

Every container has network mode `none`, a read-only root filesystem, all Linux
capabilities dropped, `no-new-privileges`, a numeric non-root identity (the service
UID/GID on POSIX or `65532:65532` where needed),
1 CPU, 512 MiB memory, a 128-PID limit, a 64 MiB temporary filesystem, and a
30-second command timeout. The intended project workspace is the only host bind
mount. The repository root, host home directories, Docker socket, privileged mode,
and host namespaces are never mounted or enabled. Container removal is enforced after
success, failure, and timeout; unconfirmed cleanup is a safe execution failure.

`build_command` and `run_command` remain only for exact backward-compatible selection
of fixed profiles. They are not shell strings. Arbitrary executable names,
`python -c`, `npx` packages, shell operators, added flags, and command overrides are
rejected before a run is created. New clients use `validation_profile`.

Staged paths reject empty paths, POSIX or Windows absolute paths, Windows drive paths
including drive-relative forms, `..`, symlinks/reparse points, and resolved targets
outside the workspace. File count and content size are bounded. Resolved paths are
checked beneath the workspace immediately before exclusive, no-follow creation where
supported.

The built-in Python AST security check remains a limited static analyzer. Its results
retain `ACTUAL_SCANNER_FINDING`; model observations must remain separately identified
and must never be presented as scanner evidence.

Both modes are capabilities of the same reusable Agent 4 engine/component, with mode-specific validation and execution paths. The standalone manual-input adapter and future integrated Shared Knowledge Base adapter feed that reusable component. Mode A's staged pipeline (§2.10) is implemented as stages within that component, not as a second engine.

Standalone Agent 4 does not require Agents 1–3 to have run, create H3 or H5 Approval, write automatically to integrated test/result/finding/traceability collections, or advance the Central SDLC Orchestrator.

## 8. Deprecated Mode A Flow

The v1.0 Mode A flow is **deprecated and must not be extended**:

```text
normalized input → one direct LLM call → generated tests
```

The rebuilt Mode A replaces it with:

```text
normalized testing artifacts → classification → traceability → readiness
    → Test Case Plan → human review / approval → detailed generation
```

The existing backend implementation of the old flow (`Agent4Engine._generate_tests` in `backend/app/modules/agents/testing_validation/engine.py`) is retained only as a reference for selective porting. It is replaced in later implementation steps and must not receive new features.

The following v1.0 capabilities are **preserved** and are not part of the deprecation: `run_mode` separation, the output enums, the `SPECIFICATION` / `EXECUTABLE_CODE` representation, the `NOT_EXECUTED` rule, the `TEST_TRACEABILITY` model, reference and ID validation, the Docker executor, validation profiles, and the security-evidence distinction.

## 9. Progress Presentation Scope

**Immediate development priority: Mode A `TEST_GENERATION`.** Mode B remains a defined mode with later rebuild work and is not claimed as completed.

**MUST HAVE (Progress Presentation 1, Mode A)**
- Mode chooser (Mode A and Mode B are separate; Mode B is shown as later work)
- Mode A artifact inputs: `TEXT`, `DOCUMENT`, and `IMAGE` accepted as `PENDING_ANALYSIS`
- Extraction integration (shared dependency, §7.1)
- Normalized testing artifacts with provenance
- Deterministic readiness with `READY`, `READY_WITH_WARNINGS`, `NOT_READY`
- Test Case Plan generation
- Human review of the plan (approve, reject, edit, remove, request clarification)
- Structured test specifications for the selected outputs, labeled `SPECIFICATION` and `NOT_EXECUTED`
- `TEST_TRACEABILITY` with coverage gaps

**SHOULD HAVE**
- Classification rules (§2.12) across the initial taxonomy
- Plan regeneration scoped to rejected or edited items
- Run history

**LATER**
- Image understanding
- Executable test generation (§2.20)
- Mode B `VALIDATION` rebuild (sections §3, §6, §7 are preserved for that work)
- GitHub source provider
- Coverage, security, and quality reports
- Integrated `TraceabilityLink` writes and H-gate approvals

## 10. Decisions Requiring Team Agreement

1. **Shared extraction location and timing** (§7.1). The cross-agent integration step needs agreement before Mode A extraction work begins.
2. **Internal naming** (§2.9). Confirm that Agent 4 keys equal contract codes, with other agents' names recorded as aliases.
3. **Legacy input aliases** (§2.7). Confirm the `requirements` alias and the `ui_specification` disambiguation.
4. **`domain` requirement.** Agents 1 and 2 require `domain`. Agent 4 v1.1 keeps v1.0's required input of `project_name` only. Decide whether to align.
5. **Run or resource model.** Decide whether the staged pipeline runs as `AgentRun` stages or as project-level resources. Agent 3 uses project-level resource endpoints with no run endpoint.
6. **Progress Presentation claim.** [STANDALONE_AGENT_ARCHITECTURE.md §15](STANDALONE_AGENT_ARCHITECTURE.md) lists "Agent 4 `VALIDATION`: working standalone MVP" as a PP1 target. Confirm whether the presentation claims it, given that Mode A is the current priority.
7. **Plan-level status values** (§2.15, §2.16). The minimum is draft and approved. The full state set is an implementation decision.
