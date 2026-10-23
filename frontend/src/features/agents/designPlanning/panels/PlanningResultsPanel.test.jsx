import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import PlanningResultsPanel from './PlanningResultsPanel.jsx'

describe('PlanningResultsPanel', () => {
  const mockProject = {
    id: 'proj-123',
    name: 'BookEase',
  }

  const mockRun014 = {
    run_id: 'RUN-014',
    status: 'COMPLETED',
    selected_outputs: [
      'PRODUCT_BACKLOG',
      'EPICS',
      'FEATURES',
      'USER_STORIES',
      'TASKS',
      'SPRINT_PLAN',
      'JIRA_PLAN',
    ],
    output_manifest: {
      PRODUCT_BACKLOG: { items: [{ id: 'PBL-1', title: 'User authentication' }] },
      EPICS: [{ id: 'EPIC-1', title: 'Authentication & Profile Management' }],
      FEATURES: [{ id: 'FEAT-1', epic_id: 'EPIC-1', title: 'OAuth Login' }],
      USER_STORIES: [{ id: 'US-1', epic_id: 'EPIC-1', title: 'As a user, I want to sign in with Google' }],
      TASKS: [{ id: 'TASK-1', story_id: 'US-1', title: 'Implement Google OAuth callback' }],
      SPRINT_PLAN: [
        {
          id: 'SPRINT-1',
          name: 'Sprint 1',
          duration_days: 14,
          capacity_points: 40,
          planned_points: 25,
          utilization_percent: 62.5,
          item_refs: ['TASK-1'],
        },
      ],
      JIRA_PLAN: {
        epics: [{ id: 'EPIC-1', title: 'Authentication & Profile Management' }],
        stories: [{ id: 'US-1', epic_id: 'EPIC-1', title: 'As a user, I want to sign in with Google' }],
        tasks: [{ id: 'TASK-1', story_id: 'US-1', title: 'Implement Google OAuth callback' }],
        sprints: [{ id: 'SPRINT-1', name: 'Sprint 1', item_refs: ['TASK-1'] }],
        assignments: [],
        priorities: [{ item_id: 'TASK-1', priority: 'HIGH' }],
        synchronization: 'NOT_PERFORMED',
      },
    },
  }

  it('renders empty state when no planning outputs are available', () => {
    render(
      <PlanningResultsPanel
        project={mockProject}
        run={null}
        outputs={{}}
      />,
    )

    expect(screen.getByTestId('agent2-panel-PLANNING_RESULTS')).toBeInTheDocument()
    expect(screen.getByText('No planning results recorded yet')).toBeInTheDocument()
    expect(screen.getByText(/Generate Agent 2 deliverables in Node 5/i)).toBeInTheDocument()
  })

  it('renders all planning subtabs for historical RUN-014 without regeneration', async () => {
    const user = userEvent.setup()
    render(
      <PlanningResultsPanel
        project={mockProject}
        run={mockRun014}
        outputs={mockRun014.output_manifest}
      />,
    )

    expect(screen.getByTestId('agent2-panel-PLANNING_RESULTS')).toBeInTheDocument()
    expect(screen.getByText('RUN-014')).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()

    // Subtabs present
    const hierarchyTab = screen.getByRole('tab', { name: 'Planning Hierarchy' })
    const sprintTab = screen.getByRole('tab', { name: 'Sprint Plan' })
    const jiraTab = screen.getByRole('tab', { name: 'Jira-ready Plan' })
    expect(hierarchyTab).toBeInTheDocument()
    expect(sprintTab).toBeInTheDocument()
    expect(jiraTab).toBeInTheDocument()

    // Default tab is Planning Hierarchy
    expect(screen.getByText(/Authentication & Profile Management/)).toBeInTheDocument()
    expect(screen.getAllByText(/EPIC-1/).length).toBeGreaterThan(0)

    // Switch to Sprint Plan tab
    await user.click(sprintTab)
    expect(screen.getByText('Sprint 1')).toBeInTheDocument()
    expect(screen.getByText(/40 units/i)).toBeInTheDocument()

    // Switch to Jira Plan tab
    await user.click(jiraTab)
    expect(screen.getByText('NOT SYNCHRONIZED')).toBeInTheDocument()
    expect(screen.getByText('Synchronization: NOT_PERFORMED')).toBeInTheDocument()
    expect(screen.getByText(/No Jira credentials or remote API calls are used/i)).toBeInTheDocument()
  })

  it('renders run switcher dropdown when multiple historical runs are provided', async () => {
    const user = userEvent.setup()
    const onSelectRun = vi.fn()
    const mockRun013 = {
      run_id: 'RUN-013',
      status: 'COMPLETED',
      created_at: '2026-10-21T08:00:00Z',
      selected_outputs: ['PRODUCT_BACKLOG'],
      output_manifest: { PRODUCT_BACKLOG: { items: [] } },
    }

    render(
      <PlanningResultsPanel
        project={mockProject}
        run={mockRun014}
        outputs={mockRun014.output_manifest}
        runs={[mockRun014, mockRun013]}
        onSelectRun={onSelectRun}
      />,
    )

    const runSelect = screen.getByLabelText('Select run to display')
    expect(runSelect).toBeInTheDocument()
    expect(runSelect).toHaveValue('RUN-014')

    await user.selectOptions(runSelect, 'RUN-013')
    expect(onSelectRun).toHaveBeenCalledWith('RUN-013')
  })

  it('navigates to Node 5 from empty state', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <PlanningResultsPanel
        project={mockProject}
        run={null}
        outputs={{}}
        onNavigate={onNavigate}
      />,
    )

    const goNode5Btn = screen.getByRole('button', { name: /Go to Node 5/i })
    await user.click(goNode5Btn)
    expect(onNavigate).toHaveBeenCalledWith('GENERATE_DESIGN_PLANNING')
  })

  it('navigates to Node 6 and Node 8 from populated state', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <PlanningResultsPanel
        project={mockProject}
        run={mockRun014}
        outputs={mockRun014.output_manifest}
        onNavigate={onNavigate}
      />,
    )

    const node6Btn = screen.getByRole('button', { name: /Node 6 \(Design Results\)/i })
    await user.click(node6Btn)
    expect(onNavigate).toHaveBeenCalledWith('DESIGN_RESULTS')

    const node8Btn = screen.getByRole('button', { name: /Node 8 \(Validation & Traceability\)/i })
    await user.click(node8Btn)
    expect(onNavigate).toHaveBeenCalledWith('VALIDATION_TRACEABILITY')
  })
})
