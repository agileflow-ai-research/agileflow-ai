import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAgentProjectRun } from '../../../../services/agentProjectService.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'
import ValidationTraceabilityPanel from './ValidationTraceabilityPanel.jsx'

vi.mock('../../../../services/agentProjectService.js', () => ({
  getAgentProjectRun: vi.fn(),
  getAgentProjectRuns: vi.fn(),
}))

describe('ValidationTraceabilityPanel (Agent 2 Node 8)', () => {
  const mockProject = {
    agent_project_id: 'AGP-002',
    name: 'BookEase',
    agent_type: 'DESIGN_PLANNING',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    getAgentProjectRun.mockResolvedValue({ data: null })
  })

  it('renders truthful empty state with disclaimer when no run has executed and no historical runs exist', () => {
    const onNavigateMock = vi.fn()
    render(
      <ValidationTraceabilityPanel
        project={mockProject}
        runState="idle"
        runResult={null}
        runs={[]}
        onNavigate={onNavigateMock}
      />,
    )

    expect(
      screen.getByRole('heading', { level: 2, name: 'Validation, Traceability & Run History' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Evidence for human review and research evaluation'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Validation and traceability awaiting execution'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/No validation findings or traceability evidence recorded yet/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Standalone scope: no Agent 1/3/4 execution · no Orchestrator · no H2 · no integrated SKB write · no Jira Cloud sync · no RAG.',
      ),
    ).toBeInTheDocument()
    const goNode5Btn = screen.getByRole('button', { name: /Go to Node 5/i })
    expect(goNode5Btn).toBeInTheDocument()
    goNode5Btn.click()
    expect(onNavigateMock).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)
  })

  it('renders historical run list when no active session run exists but historical runs are available', async () => {
    const user = userEvent.setup()
    const onViewRunMock = vi.fn()
    const mockRuns = [
      {
        run_id: 'RUN-HIST-001',
        created_at: '2026-10-15T18:00:00Z',
        status: 'COMPLETED',
        selected_outputs: ['SYSTEM_ARCHITECTURE', 'EPICS'],
      },
    ]

    render(
      <ValidationTraceabilityPanel
        project={mockProject}
        runState="idle"
        runResult={null}
        runs={mockRuns}
        onViewRun={onViewRunMock}
      />,
    )

    expect(screen.getByText('Historical validation evidence available')).toBeInTheDocument()
    expect(screen.getByText(/Select a historical run below to inspect its persisted validation findings/i)).toBeInTheDocument()

    const table = screen.getByLabelText('Historical Agent 2 runs table')
    expect(table).toBeInTheDocument()
    expect(within(table).getByText('RUN-HIST-001')).toBeInTheDocument()

    const openBtn = within(table).getByRole('button', { name: 'Open run RUN-HIST-001' })
    await user.click(openBtn)
    expect(onViewRunMock).toHaveBeenCalledWith('RUN-HIST-001')
  })

  it('renders clean completed run with 0 corrections, Evidence available badge, and scope disclaimer', () => {
    const cleanResult = {
      run_id: 'RUN-010',
      status: 'COMPLETED',
      correction_attempts: 0,
      warnings: [],
      errors: [],
      outputs: {
        EPICS: [{ id: 'EPIC-001', title: 'Booking', source_refs: ['SPEC-003'] }],
      },
    }

    render(
      <ValidationTraceabilityPanel
        project={mockProject}
        runState="completed"
        runResult={cleanResult}
        runs={[]}
      />,
    )

    expect(
      screen.getByRole('heading', { level: 2, name: 'Validation, Traceability & Run History' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Evidence available')).toBeInTheDocument()
    expect(screen.getByText('Run completed after Agent 2 validation')).toBeInTheDocument()
    expect(screen.getByText(/Correction attempts:\s*0/)).toBeInTheDocument()
    expect(screen.getByText('No validation findings recorded. Clean execution passed.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Standalone scope: no Agent 1/3/4 execution · no Orchestrator · no H2 · no integrated SKB write · no Jira Cloud sync · no RAG.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Human reviewer can inspect validation and traceability evidence.'),
    ).toBeInTheDocument()
  })

  it('renders corrected run with bounded repair warning and real correction attempts count', () => {
    const correctedResult = {
      run_id: 'RUN-011',
      status: 'COMPLETED',
      correction_attempts: 2,
      warnings: [
        {
          code: 'OUTPUT_CORRECTED',
          message: 'Output schema auto-repaired by bounded repair logic',
          details: { correction_attempts: 2 },
        },
      ],
      errors: [],
      outputs: {
        EPICS: [{ id: 'EPIC-001', title: 'Booking', source_refs: ['SPEC-003'] }],
      },
    }

    render(
      <ValidationTraceabilityPanel
        project={mockProject}
        runState="completed"
        runResult={correctedResult}
        runs={[]}
      />,
    )

    expect(screen.getByText('Initial validation: findings detected')).toBeInTheDocument()
    expect(screen.getByText(/Correction attempts:\s*2/)).toBeInTheDocument()
    expect(screen.getByText(/Automatic correction applied bounded repair to align generated schema/)).toBeInTheDocument()
    expect(screen.getByText(/OUTPUT_CORRECTED:\s*Output schema auto-repaired/)).toBeInTheDocument()
  })

  it('renders failed run with errors and does not claim validation passed', () => {
    const failedResult = {
      run_id: 'RUN-012',
      status: 'FAILED',
      errors: [{ code: 'VALIDATION_FAILED', message: 'Inconsistent component reference' }],
      warnings: [],
      outputs: {},
    }

    render(
      <ValidationTraceabilityPanel
        project={mockProject}
        runState="failed"
        runResult={failedResult}
        runError="Inconsistent component reference"
        runs={[]}
      />,
    )

    expect(
      screen.getByText('Run failed validation/execution. Review persisted findings.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Run completed after Agent 2 validation')).not.toBeInTheDocument()
    expect(screen.getByText(/VALIDATION_FAILED:\s*Inconsistent component reference/)).toBeInTheDocument()
  })

  it('renders real traceability references and does not invent fake links when none exist', () => {
    const outputsWithoutRefs = {
      SYSTEM_ARCHITECTURE: { overview: 'Microservices architecture' },
    }

    render(
      <ValidationTraceabilityPanel
        project={mockProject}
        runState="completed"
        runResult={{
          run_id: 'RUN-013',
          status: 'COMPLETED',
          outputs: outputsWithoutRefs,
        }}
        runs={[]}
      />,
    )

    expect(screen.getByText('No explicit traceability chain returned for this run.')).toBeInTheDocument()
  })

  it('reopens historical run and displays persisted manifest without regenerating outputs', async () => {
    const user = userEvent.setup()
    const onViewRunMock = vi.fn()
    const mockRuns = [
      {
        run_id: 'RUN-HIST-042',
        created_at: '2026-10-15T12:00:00Z',
        status: 'COMPLETED',
        correction_attempts: 1,
        selected_outputs: ['EPICS'],
        output_manifest: {
          EPICS: [{ id: 'EPIC-042', title: 'Persisted Historical Epic', source_refs: ['SPEC-001'] }],
        },
      },
    ]

    render(
      <ValidationTraceabilityPanel
        project={mockProject}
        runState="idle"
        runResult={null}
        runs={mockRuns}
        onViewRun={onViewRunMock}
      />,
    )

    const openBtn = screen.getByRole('button', { name: 'Open run RUN-HIST-042' })
    await user.click(openBtn)

    expect(onViewRunMock).toHaveBeenCalledWith('RUN-HIST-042')
    expect(
      screen.getByText(/persisted outputs only; no regeneration/i),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/SPEC-001/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/EPIC-042/).length).toBeGreaterThanOrEqual(1)

    // Reopen action does not call extra generation API
    expect(getAgentProjectRun).not.toHaveBeenCalled()

    // Can return to the previous view
    const backBtn = screen.getByRole('button', { name: '← Back to current view' })
    await user.click(backBtn)
    expect(
      screen.queryByText(/persisted outputs only; no regeneration/i),
    ).not.toBeInTheDocument()
  })
})
