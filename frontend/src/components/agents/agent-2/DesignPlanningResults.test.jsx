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

    // S2-07 & S2-08 deferred buttons are present and disabled
    const viewDesignBtn = screen.getByRole('button', { name: 'View design artifacts' })
    expect(viewDesignBtn).toBeDisabled()
    expect(viewDesignBtn).toHaveAttribute('title', 'Design artifact detail view will be available in S2-07')

    const viewPlanningBtn = screen.getByRole('button', { name: 'View planning hierarchy' })
    expect(viewPlanningBtn).toBeDisabled()
    expect(viewPlanningBtn).toHaveAttribute('title', 'Planning hierarchy view will be available in S2-08')

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
})
