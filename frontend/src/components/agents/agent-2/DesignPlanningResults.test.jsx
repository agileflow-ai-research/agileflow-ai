import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAgentProjectRun } from '../../../services/agentProjectService.js'
import DesignPlanningResults from './DesignPlanningResults.jsx'
import { deriveCorrectionAttempts } from './results/correctionAttempts.js'
import RunDetail from '../RunDetail.jsx'

vi.mock('../../../services/agentProjectService.js', () => ({ getAgentProjectRun: vi.fn() }))

const jiraPlan = {
  epics: [{ id: 'EPIC-001', title: 'Booking', outcome: 'Guests can book', priority: 'HIGH', source_refs: ['SPEC-001'] }],
  stories: [
    {
      id: 'STORY-001',
      epic_id: 'EPIC-001',
      feature_id: 'FEATURE-001',
      actor: 'guest',
      goal: 'book',
      benefit: 'reserve',
      acceptance_criteria: ['Confirmed'],
      priority: 'HIGH',
      estimate_points: 5,
      source_refs: ['SPEC-001'],
    },
  ],
  tasks: [
    {
      id: 'TASK-001',
      epic_id: 'EPIC-001',
      feature_id: 'FEATURE-001',
      story_id: 'STORY-001',
      title: 'Build API',
      description: 'Implement booking API',
      required_skills: ['API'],
      estimate_points: 3,
      depends_on: [],
      source_refs: ['SPEC-001'],
    },
  ],
  sprints: [
    {
      id: 'SPRINT-001',
      name: 'Sprint 1',
      duration_days: 10,
      capacity_points: 20,
      planned_points: 3,
      utilization_percent: 15,
      item_refs: ['TASK-001'],
      dependency_notes: [],
      planning_warnings: ['Estimate only'],
      estimate_basis: 'Estimated capacity formula',
    },
  ],
  assignments: [
    {
      task_id: 'TASK-001',
      team_slot: 'Alice',
      role: 'Backend Developer',
      rationale: 'API skill match',
      sprint_id: 'SPRINT-001',
      matching_reasons: ['Matched API'],
      role_match: true,
      skill_matches: ['API'],
      workload_points_before: 0,
      confidence_score: 100,
    },
  ],
  priorities: [{ item_id: 'STORY-001', priority: 'HIGH' }],
  synchronization: 'NOT_PERFORMED',
}

describe('DesignPlanningResults · S2-06 Results Overview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:test-plan')
    URL.revokeObjectURL = vi.fn()
  })

  it('renders S2-06 Results Overview with title, subtitle, and green COMPLETED status badge matching PNG', () => {
    render(
      <DesignPlanningResults
        title="Agent 2 Results"
        subtitle="Generated design and planning artifacts"
        status="COMPLETED"
        outputs={{
          SYSTEM_ARCHITECTURE: { components: [{ id: 'CMP-001', name: 'Core' }] },
          EPICS: [{ id: 'EPIC-001', title: 'Booking' }],
        }}
      />,
    )

    expect(screen.getByRole('heading', { level: 2, name: 'Agent 2 Results' })).toBeInTheDocument()
    expect(screen.getByText('Generated design and planning artifacts')).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('BookEase')).toBeInTheDocument()
    expect(screen.getByText('Standalone Agent 2')).toBeInTheDocument()
    expect(screen.getByText('Human reviewer')).toBeInTheDocument()
  })

  it('derives summary metrics dynamically from the real response without fabricated correction count', () => {
    const outputs = {
      SYSTEM_ARCHITECTURE: { components: [{ id: 'CMP-001', name: 'Core', source_refs: ['SPEC-001'] }] },
      DATABASE_SCHEMA: { entities: [{ id: 'ENT-001', name: 'User', source_refs: ['SPEC-001'] }] },
      EPICS: [{ id: 'EPIC-001', title: 'Booking', source_refs: ['SPEC-001'] }],
    }

    render(
      <DesignPlanningResults
        status="COMPLETED"
        result={{ run_id: 'RUN-101', status: 'COMPLETED', outputs, warnings: [], errors: [] }}
        outputs={outputs}
      />,
    )

    const metrics = screen.getByLabelText('Summary metrics')
    // Outputs generated dynamically counts 3
    expect(metrics).toHaveTextContent('Outputs generated')
    expect(metrics).toHaveTextContent('3')

    // Validation passed
    expect(metrics).toHaveTextContent('Validation')
    expect(metrics).toHaveTextContent('Passed')

    // Correction attempts is neutral "Not available" because the legacy mock does not provide it
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('Not available')

    // Traceability is Available because source_refs exist
    expect(metrics).toHaveTextContent('Traceability')
    expect(metrics).toHaveTextContent('Available')
  })

  it('displays "0" correction attempts for a newly completed clean run with correction_attempts = 0', () => {
    const outputs = {
      SYSTEM_ARCHITECTURE: { components: [{ id: 'CMP-001', name: 'Core', source_refs: ['SPEC-001'] }] },
    }

    render(
      <DesignPlanningResults
        status="COMPLETED"
        result={{
          run_id: 'RUN-102',
          status: 'COMPLETED',
          outputs,
          correction_attempts: 0,
          warnings: [],
          errors: [],
        }}
        outputs={outputs}
      />,
    )

    const metrics = screen.getByLabelText('Summary metrics')
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('0')
    expect(metrics).not.toHaveTextContent('Not available')
  })

  it('displays actual correction count for newly completed corrected run with correction_attempts = 1 and 2', () => {
    const outputs = {
      SYSTEM_ARCHITECTURE: { components: [{ id: 'CMP-001', name: 'Core', source_refs: ['SPEC-001'] }] },
    }

    const { rerender } = render(
      <DesignPlanningResults
        status="COMPLETED"
        result={{
          run_id: 'RUN-103',
          status: 'COMPLETED',
          outputs,
          correction_attempts: 1,
          warnings: [
            {
              code: 'OUTPUT_CORRECTED',
              message: 'Generated output passed validation after a bounded correction attempt',
              details: { correction_attempts: 1 },
            },
          ],
          errors: [],
        }}
        outputs={outputs}
      />,
    )

    let metrics = screen.getByLabelText('Summary metrics')
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('1')

    rerender(
      <DesignPlanningResults
        status="COMPLETED"
        result={{
          run_id: 'RUN-103B',
          status: 'COMPLETED',
          outputs,
          correction_attempts: 2,
          warnings: [
            {
              code: 'OUTPUT_CORRECTED',
              message: 'Generated output passed validation after a bounded correction attempt',
              details: { correction_attempts: 2 },
            },
          ],
          errors: [],
        }}
        outputs={outputs}
      />,
    )

    metrics = screen.getByLabelText('Summary metrics')
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('2')
  })

  it('derives correction count from OUTPUT_CORRECTED warning for historical runs without direct correction_attempts', () => {
    const outputs = {
      SYSTEM_ARCHITECTURE: { components: [{ id: 'CMP-001', name: 'Core', source_refs: ['SPEC-001'] }] },
    }

    render(
      <DesignPlanningResults
        title="Persisted design and planning outputs"
        status="COMPLETED"
        isHistorical
        outputs={outputs}
        warnings={[
          {
            code: 'OUTPUT_CORRECTED',
            message: 'Generated output passed validation after a bounded correction attempt',
            details: { correction_attempts: 1 },
          },
        ]}
        errors={[]}
      />,
    )

    const metrics = screen.getByLabelText('Summary metrics')
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('1')
  })

  it('displays 0 correction attempts for historical clean completed run without warnings', () => {
    const outputs = {
      SYSTEM_ARCHITECTURE: { components: [{ id: 'CMP-001', name: 'Core', source_refs: ['SPEC-001'] }] },
    }

    render(
      <DesignPlanningResults
        title="Persisted design and planning outputs"
        status="COMPLETED"
        isHistorical
        outputs={outputs}
        warnings={[]}
        errors={[]}
      />,
    )

    const metrics = screen.getByLabelText('Summary metrics')
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('0')
  })

  it('summarizes only returned outputs in Result Package Cards and does not show unreturned artifacts', () => {
    const outputs = {
      SYSTEM_ARCHITECTURE: {
        components: [
          { id: 'CMP-001', name: 'Auth' },
          { id: 'CMP-002', name: 'Booking' },
          { id: 'CMP-003', name: 'Payment' },
          { id: 'CMP-004', name: 'Notification' },
        ],
      },
      EPICS: [
        { id: 'EPIC-001', title: 'Identity' },
        { id: 'EPIC-002', title: 'Reservations' },
        { id: 'EPIC-003', title: 'Billing' },
      ],
      FEATURES: new Array(6).fill({ id: 'FEAT' }),
      USER_STORIES: new Array(11).fill({ id: 'STORY' }),
    }

    render(
      <DesignPlanningResults
        status="COMPLETED"
        outputs={outputs}
      />,
    )

    // Design package card
    expect(screen.getByRole('heading', { name: 'Design package' })).toBeInTheDocument()
    expect(screen.getByText('Architecture and technical specifications')).toBeInTheDocument()
    expect(screen.getByText(/System architecture · 4 components/)).toBeInTheDocument()

    // Unselected design outputs are NOT shown
    expect(screen.queryByText(/UML diagrams/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Database schema/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Wireframes/)).not.toBeInTheDocument()

    // Planning package card
    expect(screen.getByRole('heading', { name: 'Planning package' })).toBeInTheDocument()
    expect(screen.getByText('Agile hierarchy and delivery plan')).toBeInTheDocument()
    expect(screen.getByText(/3 epics · 6 features · 11 stories/)).toBeInTheDocument()

    // Unselected planning outputs are NOT shown
    expect(screen.queryByText(/Sprint plan/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Task assignments/)).not.toBeInTheDocument()
  })

  it('renders validation evidence and dynamically derived traceability chain without fabrication', () => {
    const outputs = {
      API_SPECIFICATION: {
        operations: [
          {
            id: 'API-POST-BOOKING',
            source_refs: ['SPEC-002'],
            component_refs: ['CMP-BOOKING'],
            entity_refs: ['ENTITY-BOOKING'],
          },
        ],
      },
      EPICS: [{ id: 'EPIC-02', source_refs: ['SPEC-002'] }],
      USER_STORIES: [{ id: 'STORY-06', epic_id: 'EPIC-02' }],
      TASKS: [{ id: 'TASK-14', story_id: 'STORY-06', epic_id: 'EPIC-02' }],
    }

    render(
      <DesignPlanningResults
        status="COMPLETED"
        outputs={outputs}
        warnings={[]}
        errors={[]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Validation & traceability evidence' })).toBeInTheDocument()
    expect(screen.getByText('Structural validation passed')).toBeInTheDocument()
    expect(screen.getByText('Cross-artifact references valid')).toBeInTheDocument()

    // Dynamic chain derived from real objects
    expect(
      screen.getByText('Example trace: SPEC-002 → CMP-BOOKING → ENTITY-BOOKING → API-POST-BOOKING → EPIC-02 → STORY-06 → TASK-14'),
    ).toBeInTheDocument()
  })

  it('renders neutral traceability message when references exist but a full chain cannot be formed', () => {
    const outputs = {
      SYSTEM_ARCHITECTURE: {
        components: [{ id: 'CMP-001', name: 'Gateway', source_refs: ['SPEC-001'] }],
      },
    }

    render(
      <DesignPlanningResults
        status="COMPLETED"
        outputs={outputs}
      />,
    )

    expect(
      screen.getByText('Traceability references are available within generated artifacts.'),
    ).toBeInTheDocument()
  })

  it('renders warnings and errors truthfully', () => {
    render(
      <DesignPlanningResults
        status="FAILED"
        outputs={{}}
        warnings={['Planning warning: over-allocated capacity']}
        errors={['VALIDATION_ERROR: Missing required entity relationship']}
      />,
    )

    expect(screen.getByText('FAILED')).toBeInTheDocument()
    expect(screen.getByText('Validation')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText(/Planning warning: over-allocated capacity/)).toBeInTheDocument()
    expect(screen.getByText(/VALIDATION_ERROR: Missing required entity relationship/)).toBeInTheDocument()
  })

  it('renders actions, handles Start another run, Open run history, and marks deferred actions disabled', async () => {
    const user = userEvent.setup()
    const onStartAnotherRun = vi.fn()
    const onOpenRunHistory = vi.fn()

    render(
      <DesignPlanningResults
        status="COMPLETED"
        outputs={{ JIRA_PLAN: jiraPlan }}
        onStartAnotherRun={onStartAnotherRun}
        onOpenRunHistory={onOpenRunHistory}
      />,
    )

    // S2-07 and S2-08 actions are now enabled
    const viewDesignBtn = screen.getByRole('button', { name: 'View design artifacts' })
    expect(viewDesignBtn).toBeEnabled()

    const viewPlanningBtn = screen.getByRole('button', { name: 'View planning hierarchy' })
    expect(viewPlanningBtn).toBeEnabled()

    // Open run history is enabled and callable
    const openHistoryBtn = screen.getByRole('button', { name: 'Open run history' })
    await user.click(openHistoryBtn)
    expect(onOpenRunHistory).toHaveBeenCalledOnce()

    // Start another run is enabled and callable
    const startAnotherBtn = screen.getByRole('button', { name: 'Start another run' })
    await user.click(startAnotherBtn)
    expect(onStartAnotherRun).toHaveBeenCalledOnce()

    // Download Jira plan is present and functional
    const downloadBtn = screen.getByRole('button', { name: 'Download Jira-compatible JSON' })
    expect(downloadBtn).toBeInTheDocument()
  })

  it('renders structured design and planning fields in detail mode', () => {
    render(
      <DesignPlanningResults
        mode="detail"
        outputs={{
          API_SPECIFICATION: {
            base_path: '/api/v1',
            operations: [
              {
                id: 'API-001',
                method: 'POST',
                path: '/bookings',
                summary: 'Create booking',
                request: 'Booking payload',
                response: 'Created booking',
                errors: ['409 conflict'],
                authentication: 'Bearer',
                source_refs: ['SPEC-001'],
                component_refs: ['COMP-001'],
                entity_refs: ['ENTITY-001'],
              },
            ],
            assumptions: [],
          },
          SPRINT_PLAN: jiraPlan.sprints,
          TASK_ASSIGNMENT: jiraPlan.assignments,
        }}
      />,
    )
    expect(screen.getByText('POST /bookings')).toBeInTheDocument()
    expect(screen.getByText('COMP-001')).toBeInTheDocument()
    expect(screen.getByText('Estimated capacity')).toBeInTheDocument()
    expect(screen.getByText('15%')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('100/100')).toBeInTheDocument()
  })

  it('downloads the already-generated Jira plan as JSON without synchronization in detail mode', async () => {
    const user = userEvent.setup()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<DesignPlanningResults mode="detail" outputs={{ JIRA_PLAN: jiraPlan }} />)
    await user.click(screen.getByRole('button', { name: 'Download Jira-compatible JSON' }))
    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
    expect(click).toHaveBeenCalledOnce()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-plan')
    expect(screen.getByText(/Synchronization:/)).toHaveTextContent('Not performed')
    click.mockRestore()
  })

  it('renders persisted Agent 2 results with 0 corrections for clean historical runs and does not make extra API requests', async () => {
    getAgentProjectRun.mockResolvedValueOnce({
      data: {
        run_id: 'RUN-020',
        agent_type: 'DESIGN_PLANNING',
        run_mode: 'DEFAULT',
        status: 'COMPLETED',
        selected_outputs: ['JIRA_PLAN'],
        created_at: '2026-10-14T10:00:00Z',
        started_at: '2026-10-14T10:00:01Z',
        completed_at: '2026-10-14T10:00:02Z',
        warnings: [],
        errors: [],
        output_manifest: { JIRA_PLAN: jiraPlan },
      },
    })
    render(<RunDetail agentProjectId="AGP-002" runId="RUN-020" />)
    expect(await screen.findByRole('heading', { name: 'Persisted design and planning outputs' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download Jira-compatible JSON' })).toBeInTheDocument()
    expect(screen.getAllByText('Booking').length).toBeGreaterThan(0)

    const metrics = screen.getByLabelText('Summary metrics')
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('0')
    // Verification: getAgentProjectRun called once only (no extra API calls)
    expect(getAgentProjectRun).toHaveBeenCalledTimes(1)
  })

  it('renders persisted Agent 2 results with derived count for corrected historical runs', async () => {
    getAgentProjectRun.mockResolvedValueOnce({
      data: {
        run_id: 'RUN-021',
        agent_type: 'DESIGN_PLANNING',
        run_mode: 'DEFAULT',
        status: 'COMPLETED',
        selected_outputs: ['JIRA_PLAN'],
        created_at: '2026-10-14T10:00:00Z',
        started_at: '2026-10-14T10:00:01Z',
        completed_at: '2026-10-14T10:00:02Z',
        warnings: [
          {
            code: 'OUTPUT_CORRECTED',
            message: 'Generated output passed validation after a bounded correction attempt',
            details: { correction_attempts: 1 },
          },
        ],
        errors: [],
        output_manifest: { JIRA_PLAN: jiraPlan },
      },
    })
    render(<RunDetail agentProjectId="AGP-002" runId="RUN-021" />)
    expect(await screen.findByRole('heading', { name: 'Persisted design and planning outputs' })).toBeInTheDocument()

    const metrics = screen.getByLabelText('Summary metrics')
    expect(metrics).toHaveTextContent('Correction attempts')
    expect(metrics).toHaveTextContent('1')
    expect(getAgentProjectRun).toHaveBeenCalledTimes(1)
  })

  describe('deriveCorrectionAttempts helper', () => {
    it('uses explicit null/undefined check so 0 is preserved and not treated as falsy', () => {
      expect(deriveCorrectionAttempts({ result: { correction_attempts: 0 } })).toBe('0')
      expect(deriveCorrectionAttempts({ result: { correction_attempts: 1 } })).toBe('1')
      expect(deriveCorrectionAttempts({ result: { correction_attempts: 2 } })).toBe('2')
      expect(deriveCorrectionAttempts({ run: { correction_attempts: 0 } })).toBe('0')
      expect(deriveCorrectionAttempts({ correction_attempts: 0 })).toBe('0')
    })

    it('falls back to OUTPUT_CORRECTED warning details when top-level field is absent', () => {
      expect(
        deriveCorrectionAttempts({
          warnings: [
            { code: 'OUTPUT_CORRECTED', details: { correction_attempts: 1 } },
          ],
        }),
      ).toBe('1')
    })

    it('falls back to "0" for historical clean completed runs without warnings', () => {
      expect(
        deriveCorrectionAttempts({
          isHistorical: true,
          status: 'COMPLETED',
          warnings: [],
          errors: [],
        }),
      ).toBe('0')
    })

    it('returns "Not available" when run has errors or is not completed and no correction count exists', () => {
      expect(
        deriveCorrectionAttempts({
          isHistorical: true,
          status: 'FAILED',
          errors: ['Some error'],
        }),
      ).toBe('Not available')
    })
  })

  describe('S2-07 Design Artifacts View', () => {
    const designOutputs = {
      SYSTEM_ARCHITECTURE: {
        style: 'Modular web application',
        components: [
          {
            id: 'CMP-WEB',
            name: 'React Web Application',
            responsibility: 'Provides client-facing UI and state',
            dependencies: ['API Gateway'],
            source_refs: ['SPEC-001'],
          },
        ],
        boundaries: ['Browser sandbox', 'DMZ'],
        interactions: ['HTTPS/JSON over REST'],
        constraints: ['Node 20+ runtime'],
        assumptions: ['Modern evergreen browsers'],
      },
      DATABASE_SCHEMA: {
        technology: 'PostgreSQL',
        entities: [
          {
            id: 'ENTITY-USER',
            name: 'User',
            fields: [
              { name: 'id', data_type: 'UUID', required: true, constraints: ['PRIMARY KEY'] },
              { name: 'email', data_type: 'VARCHAR(255)', required: true, constraints: ['UNIQUE'] },
            ],
            relationships: [
              { target_entity_id: 'ENTITY-002', relationship_type: 'ONE_TO_MANY', description: 'User bookings' },
            ],
            source_refs: ['SPEC-001'],
          },
        ],
        assumptions: ['ACID compliance required'],
      },
      API_SPECIFICATION: {
        base_path: '/api',
        operations: [
          {
            id: 'API-001',
            method: 'POST',
            path: '/api/auth/register',
            summary: 'Register new user account',
            request: '{"email": "string"}',
            response: '{"id": "string"}',
            errors: ['400 Bad Request'],
            authentication: 'None',
            source_refs: ['SPEC-001'],
            component_refs: ['CMP-AUTH'],
            entity_refs: ['ENTITY-USER'],
          },
          {
            id: 'API-002',
            method: 'GET',
            path: '/api/services',
            summary: 'List available services',
            request: null,
            response: '[{"id": "string"}]',
            errors: [],
            authentication: 'None',
            source_refs: ['SPEC-002'],
            component_refs: ['CMP-API'],
            entity_refs: ['ENTITY-SERVICE'],
          },
          {
            id: 'API-003',
            method: 'POST',
            path: '/api/bookings',
            summary: 'Create booking',
            request: '{"serviceId": "string"}',
            response: '{"bookingId": "string"}',
            errors: ['409 Conflict'],
            authentication: 'Bearer',
            source_refs: ['SPEC-003'],
            component_refs: ['CMP-BOOKING'],
            entity_refs: ['ENTITY-BOOKING'],
          },
        ],
        assumptions: ['RESTful semantics'],
      },
      UML_DIAGRAMS: {
        diagrams: [
          {
            id: 'UML-001',
            title: 'System Component Flow',
            diagram_type: 'COMPONENT_DIAGRAM',
            notation: 'MERMAID',
            source: 'flowchart LR  WEB[React Web App] --> API[FastAPI]  API --> AUTH[Auth Module]  API --> BOOK[Booking Module]  BOOK --> DB[(MongoDB)]',
            source_refs: ['SPEC-001'],
          },
        ],
        assumptions: ['Mermaid syntax'],
      },
      WIREFRAMES: {
        fidelity: 'STRUCTURED_LOW_FIDELITY',
        screens: [
          {
            id: 'WF-001',
            name: 'Dashboard Screen',
            purpose: 'Displays overview metrics and navigation shortcuts',
            regions: ['Sidebar', 'Header', 'Main Content'],
            interactions: ['Click to expand card'],
            components: ['MetricCard', 'NavMenu'],
            source_refs: ['SPEC-001'],
          },
        ],
        assumptions: ['Responsive layout'],
      },
      UI_FLOW: {
        flows: [
          {
            id: 'FLOW-001',
            actor: 'Registered User',
            goal: 'Complete reservation checkout',
            steps: ['Select item', 'Review booking', 'Submit payment', 'View confirmation'],
            alternate_paths: ['Cancel checkout', 'Payment failure retry'],
            source_refs: ['SPEC-001'],
            screen_refs: ['WF-001', 'WF-002'],
          },
        ],
      },
    }

    it('navigates from S2-06 to S2-07 via "View design artifacts" without extra API requests', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={designOutputs}
        />,
      )

      expect(screen.getByRole('heading', { level: 2, name: 'Agent 2 Results' })).toBeInTheDocument()
      const viewDesignBtn = screen.getByRole('button', { name: 'View design artifacts' })
      await user.click(viewDesignBtn)

      // S2-07 rendered
      expect(screen.getByRole('heading', { level: 2, name: 'Generated Design Artifacts' })).toBeInTheDocument()
      expect(screen.getByText('Structured architecture, UML, database and API specifications')).toBeInTheDocument()
      expect(screen.getByText('Validated')).toBeInTheDocument()
      expect(screen.getByText('BookEase')).toBeInTheDocument()
      expect(screen.getByText('Standalone Agent 2')).toBeInTheDocument()
      expect(screen.getByText('Human reviewer')).toBeInTheDocument()

      // Verification: 0 API requests
      expect(getAgentProjectRun).not.toHaveBeenCalled()
    })

    it('navigates back to S2-06 from S2-07 and preserves the run result state', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={designOutputs}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View design artifacts' }))
      expect(screen.getByRole('heading', { level: 2, name: 'Generated Design Artifacts' })).toBeInTheDocument()

      // Click Back to Results Overview
      const backButtons = screen.getAllByRole('button', { name: 'Back to Results Overview' })
      await user.click(backButtons[0])

      // Returns to S2-06
      expect(screen.getByRole('heading', { level: 2, name: 'Agent 2 Results' })).toBeInTheDocument()
      expect(screen.getByText('Generated design and planning artifacts')).toBeInTheDocument()
    })

    it('renders real architecture, database, API, UML, wireframes, and UI flows with authentic traceability refs matching PNG', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={designOutputs}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View design artifacts' }))

      // System Architecture
      expect(screen.getByRole('heading', { level: 3, name: 'System architecture' })).toBeInTheDocument()
      expect(screen.getByText(/ARCH-001 · Modular web application/)).toBeInTheDocument()
      expect(screen.getByText(/CMP-WEB · React Web Application/)).toBeInTheDocument()
      expect(screen.getByText('Provides client-facing UI and state')).toBeInTheDocument()
      expect(screen.getByText('API Gateway')).toBeInTheDocument()
      expect(screen.getAllByText('SPEC-001').length).toBeGreaterThan(0)
      expect(screen.getByText(/Browser sandbox, DMZ/)).toBeInTheDocument()
      expect(screen.getByText(/Node 20\+ runtime/)).toBeInTheDocument()

      // Database schema
      expect(screen.getByRole('heading', { level: 3, name: 'Database schema' })).toBeInTheDocument()
      expect(screen.getByText(/1 traceable entity/)).toBeInTheDocument()
      expect(screen.getByText('ENTITY-USER')).toBeInTheDocument()
      expect(screen.getByText('(User)')).toBeInTheDocument()
      expect(screen.getByText(/UUID/)).toBeInTheDocument()
      expect(screen.getByText(/PRIMARY KEY/)).toBeInTheDocument()
      expect(screen.getByText(/ONE_TO_MANY → ENTITY-002/)).toBeInTheDocument()

      // API specification table
      expect(screen.getByRole('heading', { level: 3, name: 'API specification' })).toBeInTheDocument()
      expect(screen.getByText(/Operations reference architecture components and database entities/)).toBeInTheDocument()
      expect(screen.getByText('/api/auth/register')).toBeInTheDocument()
      expect(screen.getByText('Register new user account')).toBeInTheDocument()
      expect(screen.getByText('CMP-AUTH / ENTITY-USER')).toBeInTheDocument()
      expect(screen.getByText('/api/services')).toBeInTheDocument()
      expect(screen.getByText('CMP-API / ENTITY-SERVICE')).toBeInTheDocument()
      expect(screen.getByText('SPEC-002')).toBeInTheDocument()
      expect(screen.getByText('/api/bookings')).toBeInTheDocument()
      expect(screen.getByText('CMP-BOOKING / ENTITY-BOOKING')).toBeInTheDocument()
      expect(screen.getByText('SPEC-003')).toBeInTheDocument()

      // UML diagram source
      expect(screen.getByRole('heading', { level: 3, name: 'UML diagram source' })).toBeInTheDocument()
      expect(screen.getByText(/Authoritative structured source — no fake rendered image/)).toBeInTheDocument()
      expect(screen.getByText(/flowchart LR WEB\[React Web App\] --> API\[FastAPI\]/)).toBeInTheDocument()

      // Wireframes
      expect(screen.getByRole('heading', { level: 3, name: 'Wireframes' })).toBeInTheDocument()
      expect(screen.getByText('Dashboard Screen')).toBeInTheDocument()
      expect(screen.getByText('WF-001')).toBeInTheDocument()
      expect(screen.getByText(/Displays overview metrics/)).toBeInTheDocument()
      expect(screen.getByText(/Sidebar, Header, Main Content/)).toBeInTheDocument()
      expect(screen.getByText(/MetricCard, NavMenu/)).toBeInTheDocument()

      // UI Flow
      expect(screen.getByRole('heading', { level: 3, name: 'UI flow' })).toBeInTheDocument()
      expect(screen.getByText(/Registered User/)).toBeInTheDocument()
      expect(screen.getByText(/Complete reservation checkout/)).toBeInTheDocument()
      expect(screen.getByText('FLOW-001')).toBeInTheDocument()
      expect(screen.getByText('Select item')).toBeInTheDocument()
      expect(screen.getByText(/WF-001, WF-002/)).toBeInTheDocument()
      expect(screen.getByText(/Cancel checkout, Payment failure retry/)).toBeInTheDocument()
    })

    it('renders only selected design outputs and omits unreturned sections for partial design packages', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={{
            DATABASE_SCHEMA: designOutputs.DATABASE_SCHEMA,
          }}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View design artifacts' }))

      // Only Database schema is shown
      expect(screen.getByRole('heading', { level: 3, name: 'Database schema' })).toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'System architecture' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'API specification' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'UML diagram source' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'Wireframes' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'UI flow' })).not.toBeInTheDocument()
    })

    it('displays truthful empty state when no design artifacts were returned', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={{
            EPICS: [{ id: 'EPIC-001', title: 'Agile Epic' }],
          }}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View design artifacts' }))

      expect(screen.getByText('No design artifacts were generated for this run.')).toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'System architecture' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'Database schema' })).not.toBeInTheDocument()
    })

    it('opens S2-07 and navigates back in historical RunDetail view without extra API calls', async () => {
      const user = userEvent.setup()
      getAgentProjectRun.mockResolvedValueOnce({
        data: {
          run_id: 'RUN-HIST-007',
          agent_type: 'DESIGN_PLANNING',
          run_mode: 'DEFAULT',
          status: 'COMPLETED',
          selected_outputs: ['SYSTEM_ARCHITECTURE', 'DATABASE_SCHEMA'],
          created_at: '2026-10-14T10:00:00Z',
          started_at: '2026-10-14T10:00:01Z',
          completed_at: '2026-10-14T10:00:02Z',
          warnings: [],
          errors: [],
          output_manifest: designOutputs,
        },
      })

      render(<RunDetail agentProjectId="AGP-002" runId="RUN-HIST-007" />)
      expect(await screen.findByRole('heading', { name: 'Persisted design and planning outputs' })).toBeInTheDocument()

      // Initial call to getAgentProjectRun
      expect(getAgentProjectRun).toHaveBeenCalledTimes(1)

      // Open S2-07
      const viewDesignBtn = screen.getByRole('button', { name: 'View design artifacts' })
      await user.click(viewDesignBtn)

      expect(screen.getByRole('heading', { level: 2, name: 'Generated Design Artifacts' })).toBeInTheDocument()
      expect(screen.getByText(/ARCH-001 · Modular web application/)).toBeInTheDocument()

      // Still only 1 call to getAgentProjectRun
      expect(getAgentProjectRun).toHaveBeenCalledTimes(1)

      // Back to Overview
      const backButtons = screen.getAllByRole('button', { name: 'Back to Results Overview' })
      await user.click(backButtons[0])

      expect(screen.getByRole('heading', { name: 'Persisted design and planning outputs' })).toBeInTheDocument()
      expect(getAgentProjectRun).toHaveBeenCalledTimes(1)
    })
  })

  describe('S2-08 Planning Hierarchy View', () => {
    const planningOutputs = {
      EPICS: [
        {
          id: 'EPIC-02',
          title: 'Booking Management',
          outcome: 'Customers can book, modify, and view reservations.',
          priority: 'HIGH',
          source_refs: ['SPEC-003'],
        },
      ],
      FEATURES: [
        {
          id: 'FEATURE-04',
          epic_id: 'EPIC-02',
          title: 'Create Booking',
          description: 'Capture booking details and confirm reservations',
          source_refs: ['SPEC-003'],
        },
      ],
      USER_STORIES: [
        {
          id: 'STORY-06',
          epic_id: 'EPIC-02',
          feature_id: 'FEATURE-04',
          actor: 'Customer',
          goal: 'books an available slot',
          benefit: 'reserves an appointment',
          acceptance_criteria: [
            'Booking slot is locked during checkout',
            'Confirmation email is dispatched upon payment',
          ],
          priority: 'HIGH',
          estimate_points: 5,
          source_refs: ['SPEC-003'],
        },
      ],
      TASKS: [
        {
          id: 'TASK-13',
          epic_id: 'EPIC-02',
          feature_id: 'FEATURE-04',
          story_id: 'STORY-06',
          title: 'Create booking persistence model',
          description: 'Define schema and migrations',
          required_skills: ['Database', 'Python'],
          estimate_points: 3,
          depends_on: [],
          source_refs: ['SPEC-003'],
        },
        {
          id: 'TASK-14',
          epic_id: 'EPIC-02',
          feature_id: 'FEATURE-04',
          story_id: 'STORY-06',
          title: 'Implement POST /api/bookings',
          description: 'FastAPI route with validation',
          required_skills: ['FastAPI'],
          estimate_points: 5,
          depends_on: ['TASK-13'],
          source_refs: ['SPEC-003'],
        },
        {
          id: 'TASK-15',
          epic_id: 'EPIC-02',
          feature_id: 'FEATURE-04',
          story_id: 'STORY-06',
          title: 'Connect booking form to API',
          description: 'Frontend integration and error handling',
          required_skills: ['React'],
          estimate_points: 3,
          depends_on: ['TASK-14'],
          source_refs: ['SPEC-003'],
        },
      ],
      PRODUCT_BACKLOG: [
        {
          item_id: 'EPIC-02',
          item_type: 'EPIC',
          title: 'Booking Management',
          priority: 'HIGH',
          parent_id: null,
          source_refs: ['SPEC-003'],
        },
        {
          item_id: 'FEATURE-04',
          item_type: 'FEATURE',
          title: 'Create Booking',
          priority: 'HIGH',
          parent_id: 'EPIC-02',
          source_refs: ['SPEC-003'],
        },
        {
          item_id: 'STORY-06',
          item_type: 'STORY',
          title: 'Customer books an available slot',
          priority: 'HIGH',
          parent_id: 'FEATURE-04',
          source_refs: ['SPEC-003'],
        },
      ],
    }

    it('navigates from S2-06 to S2-08 via "View planning hierarchy" without extra API requests', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={planningOutputs}
        />,
      )

      expect(screen.getByRole('heading', { level: 2, name: 'Agent 2 Results' })).toBeInTheDocument()
      const viewPlanningBtn = screen.getByRole('button', { name: 'View planning hierarchy' })
      await user.click(viewPlanningBtn)

      // S2-08 rendered
      expect(screen.getByRole('heading', { level: 2, name: 'Agile Planning Hierarchy' })).toBeInTheDocument()
      expect(
        screen.getByText('Epic → Feature → User Story → Task with stable IDs and source references'),
      ).toBeInTheDocument()
      expect(screen.getByText('Hierarchy valid')).toBeInTheDocument()
      expect(screen.getByText('BookEase')).toBeInTheDocument()
      expect(screen.getByText('Standalone Agent 2')).toBeInTheDocument()
      expect(screen.getByText('Human reviewer')).toBeInTheDocument()

      // Verification: 0 extra API requests
      expect(getAgentProjectRun).not.toHaveBeenCalled()
    })

    it('navigates back to S2-06 from S2-08 and preserves the run result state', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={planningOutputs}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View planning hierarchy' }))
      expect(screen.getByRole('heading', { level: 2, name: 'Agile Planning Hierarchy' })).toBeInTheDocument()

      // Click Back to Results Overview
      const backButtons = screen.getAllByRole('button', { name: 'Back to Results Overview' })
      await user.click(backButtons[0])

      // Returns to S2-06
      expect(screen.getByRole('heading', { level: 2, name: 'Agent 2 Results' })).toBeInTheDocument()
      expect(screen.getByText('Generated design and planning artifacts')).toBeInTheDocument()
    })

    it('renders Epic → Feature → User Story → Task tree with real IDs, acceptance criteria, dependencies, and deterministic checks', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={planningOutputs}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View planning hierarchy' }))

      // Main hierarchy card
      expect(screen.getByRole('heading', { level: 3, name: 'Product backlog hierarchy' })).toBeInTheDocument()

      // Epic
      expect(screen.getByText('EPIC-02 · Booking Management')).toBeInTheDocument()
      expect(screen.getAllByText('SPEC-003').length).toBeGreaterThan(0)
      expect(screen.getAllByText('High').length).toBeGreaterThan(0)
      expect(screen.getByText('Customers can book, modify, and view reservations.')).toBeInTheDocument()

      // Feature
      expect(screen.getByText('FEATURE-04 · Create Booking')).toBeInTheDocument()
      expect(screen.getByText('Capture booking details and confirm reservations')).toBeInTheDocument()

      // Story
      expect(screen.getByText(/STORY-06 · Customer · books an available slot/)).toBeInTheDocument()
      expect(screen.getByText(/5 workload units/)).toBeInTheDocument()
      expect(screen.getByText('Booking slot is locked during checkout')).toBeInTheDocument()
      expect(screen.getByText('Confirmation email is dispatched upon payment')).toBeInTheDocument()

      // Tasks and dependencies
      expect(screen.getAllByText('TASK-13').length).toBe(2) // 1 in task title, 1 in TASK-14 dependency
      expect(screen.getByText(/Create booking persistence model/)).toBeInTheDocument()
      expect(screen.getAllByText('TASK-14').length).toBe(2) // 1 in task title, 1 in TASK-15 dependency
      expect(screen.getByText(/Implement POST \/api\/bookings/)).toBeInTheDocument()
      expect(screen.getByText('TASK-15')).toBeInTheDocument()

      // Product backlog table
      expect(screen.getByRole('heading', { level: 3, name: 'Product backlog' })).toBeInTheDocument()
      expect(screen.getByText('3 prioritized backlog items')).toBeInTheDocument()

      // Deterministic planning checks
      expect(screen.getByRole('heading', { level: 3, name: 'Deterministic planning checks' })).toBeInTheDocument()
      expect(screen.getByText('Features reference valid epics')).toBeInTheDocument()
      expect(screen.getByText('Stories reference valid features')).toBeInTheDocument()
      expect(screen.getByText('Tasks reference valid stories')).toBeInTheDocument()
      expect(screen.getByText('Task dependencies reference valid tasks')).toBeInTheDocument()
      expect(screen.getByText('Duplicate planning IDs rejected')).toBeInTheDocument()
    })

    it('renders partial planning package (e.g., USER_STORIES + TASKS only) without requiring Epics/Features', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={{
            USER_STORIES: planningOutputs.USER_STORIES,
            TASKS: planningOutputs.TASKS,
          }}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View planning hierarchy' }))

      // Renders stories as roots
      expect(screen.getByRole('heading', { level: 2, name: 'Agile Planning Hierarchy' })).toBeInTheDocument()
      expect(screen.getByText(/STORY-06 · Customer · books an available slot/)).toBeInTheDocument()
      expect(screen.getAllByText('TASK-13').length).toBe(2)
      expect(screen.getAllByText('TASK-14').length).toBe(2)

      // Epics and features are omitted
      expect(screen.queryByText('EPIC-02 · Booking Management')).not.toBeInTheDocument()
      expect(screen.queryByText('FEATURE-04 · Create Booking')).not.toBeInTheDocument()
    })

    it('places unlinked items in unlinked items section without fabricating parent relationships', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={{
            EPICS: planningOutputs.EPICS,
            FEATURES: [
              {
                id: 'FEATURE-ORPHAN',
                epic_id: 'EPIC-NONEXISTENT',
                title: 'Orphan Feature',
                description: 'No matching epic parent',
                source_refs: ['SPEC-003'],
              },
            ],
            USER_STORIES: [
              {
                id: 'STORY-ORPHAN',
                epic_id: 'EPIC-NONEXISTENT',
                feature_id: 'FEATURE-NONEXISTENT',
                actor: 'User',
                goal: 'orphan goal',
                benefit: 'orphan benefit',
                acceptance_criteria: ['Criterion'],
                priority: 'LOW',
                estimate_points: 1,
                source_refs: ['SPEC-003'],
              },
            ],
            TASKS: [
              {
                id: 'TASK-ORPHAN',
                epic_id: 'EPIC-NONEXISTENT',
                feature_id: 'FEATURE-NONEXISTENT',
                story_id: 'STORY-NONEXISTENT',
                title: 'Orphan Task',
                description: 'No matching story parent',
                required_skills: [],
                estimate_points: 1,
                depends_on: [],
                source_refs: ['SPEC-003'],
              },
            ],
          }}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View planning hierarchy' }))

      expect(screen.getByRole('heading', { level: 3, name: 'Unlinked items' })).toBeInTheDocument()
      expect(screen.getByText(/FEATURE-ORPHAN/)).toBeInTheDocument()
      expect(screen.getByText(/STORY-ORPHAN/)).toBeInTheDocument()
      expect(screen.getByText(/TASK-ORPHAN/)).toBeInTheDocument()
    })

    it('displays truthful empty state when no planning hierarchy outputs were returned', async () => {
      const user = userEvent.setup()
      render(
        <DesignPlanningResults
          status="COMPLETED"
          outputs={{
            SYSTEM_ARCHITECTURE: { components: [] },
          }}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'View planning hierarchy' }))

      expect(screen.getByText('No planning hierarchy artifacts were generated for this run.')).toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'Product backlog hierarchy' })).not.toBeInTheDocument()
    })

    it('navigates to S2-08 and back in historical RunDetail view without extra API requests', async () => {
      const user = userEvent.setup()
      getAgentProjectRun.mockResolvedValueOnce({
        data: {
          run_id: 'RUN-HIST-008',
          agent_type: 'DESIGN_PLANNING',
          run_mode: 'DEFAULT',
          status: 'COMPLETED',
          selected_outputs: ['EPICS', 'FEATURES', 'USER_STORIES', 'TASKS'],
          created_at: '2026-10-14T10:00:00Z',
          started_at: '2026-10-14T10:00:01Z',
          completed_at: '2026-10-14T10:00:02Z',
          warnings: [],
          errors: [],
          output_manifest: planningOutputs,
        },
      })

      render(<RunDetail agentProjectId="AGP-002" runId="RUN-HIST-008" />)
      expect(await screen.findByRole('heading', { name: 'Persisted design and planning outputs' })).toBeInTheDocument()
      expect(getAgentProjectRun).toHaveBeenCalledTimes(1)

      // Open S2-08
      const viewPlanningBtn = screen.getByRole('button', { name: 'View planning hierarchy' })
      await user.click(viewPlanningBtn)

      expect(screen.getByRole('heading', { level: 2, name: 'Agile Planning Hierarchy' })).toBeInTheDocument()
      expect(screen.getByText('EPIC-02 · Booking Management')).toBeInTheDocument()
      expect(getAgentProjectRun).toHaveBeenCalledTimes(1)

      // Back to Overview
      const backButtons = screen.getAllByRole('button', { name: 'Back to Results Overview' })
      await user.click(backButtons[0])

      expect(screen.getByRole('heading', { name: 'Persisted design and planning outputs' })).toBeInTheDocument()
      expect(getAgentProjectRun).toHaveBeenCalledTimes(1)
    })
  })
})
