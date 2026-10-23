import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import DesignResultsPanel from './DesignResultsPanel.jsx'

describe('DesignResultsPanel', () => {
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
      SPRINT_PLAN: [{ id: 'SPRINT-1', name: 'Sprint 1' }],
      JIRA_PLAN: { epics: [], stories: [], tasks: [], sprints: [] },
    },
  }

  const mockDesignRun = {
    run_id: 'RUN-015',
    status: 'COMPLETED',
    selected_outputs: ['SYSTEM_ARCHITECTURE', 'DATABASE_SCHEMA'],
    output_manifest: {
      SYSTEM_ARCHITECTURE: {
        components: [
          { name: 'AuthService', description: 'Handles authentication and token exchange' },
        ],
        data_flow: 'Frontend -> API Gateway -> AuthService -> PostgreSQL',
      },
      DATABASE_SCHEMA: {
        tables: [
          { name: 'users', columns: [{ name: 'id', type: 'UUID' }, { name: 'email', type: 'VARCHAR' }] },
        ],
      },
    },
  }

  it('renders empty state when no active run or historical runs exist', () => {
    render(
      <DesignResultsPanel
        project={mockProject}
        run={null}
        outputs={{}}
      />,
    )

    expect(screen.getByTestId('agent2-panel-DESIGN_RESULTS')).toBeInTheDocument()
    expect(screen.getByText('No design results recorded yet')).toBeInTheDocument()
    expect(screen.getByText(/Generate Agent 2 deliverables in Node 5/i)).toBeInTheDocument()
  })

  it('navigates to Node 5 from empty state', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <DesignResultsPanel
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

  it('renders explanatory state for planning-only run like RUN-014 with direct link to Node 7', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <DesignResultsPanel
        project={mockProject}
        run={mockRun014}
        outputs={mockRun014.output_manifest}
        onNavigate={onNavigate}
      />,
    )

    expect(screen.getByTestId('agent2-panel-DESIGN_RESULTS')).toBeInTheDocument()
    expect(screen.getAllByText('RUN-014').length).toBeGreaterThan(0)
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('No technical design deliverables selected for this run')).toBeInTheDocument()
    expect(screen.getByText(/was executed with agile planning deliverables only/i)).toBeInTheDocument()

    // Persisted deliverable tags
    expect(screen.getByText('PRODUCT_BACKLOG')).toBeInTheDocument()
    expect(screen.getByText('EPICS')).toBeInTheDocument()
    expect(screen.getByText('SPRINT_PLAN')).toBeInTheDocument()
    expect(screen.getByText('JIRA_PLAN')).toBeInTheDocument()

    // Direct navigation button to Node 7 (Planning Results)
    const viewPlanningBtn = screen.getByRole('button', { name: /View Planning Results \(Node 7\)/i })
    await user.click(viewPlanningBtn)
    expect(onNavigate).toHaveBeenCalledWith('PLANNING_RESULTS')
  })

  it('renders design artifacts when technical design outputs exist', () => {
    render(
      <DesignResultsPanel
        project={mockProject}
        run={mockDesignRun}
        outputs={mockDesignRun.output_manifest}
      />,
    )

    expect(screen.getByTestId('agent2-panel-DESIGN_RESULTS')).toBeInTheDocument()
    expect(screen.getByText('RUN-015')).toBeInTheDocument()
    // Should render System Architecture or DesignArtifacts content
    expect(screen.getByText(/AuthService/i)).toBeInTheDocument()
  })

  it('renders run switcher and triggers onSelectRun', async () => {
    const user = userEvent.setup()
    const onSelectRun = vi.fn()

    render(
      <DesignResultsPanel
        project={mockProject}
        run={mockRun014}
        outputs={mockRun014.output_manifest}
        runs={[mockRun014, mockDesignRun]}
        onSelectRun={onSelectRun}
      />,
    )

    const select = screen.getByLabelText('Select run to display')
    expect(select).toBeInTheDocument()
    expect(select).toHaveValue('RUN-014')

    await user.selectOptions(select, 'RUN-015')
    expect(onSelectRun).toHaveBeenCalledWith('RUN-015')
  })

  it('navigates via footer navigation buttons', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <DesignResultsPanel
        project={mockProject}
        run={mockRun014}
        outputs={mockRun014.output_manifest}
        onNavigate={onNavigate}
      />,
    )

    const backBtn = screen.getByRole('button', { name: /← Back to Node 5 \(Generate\)/i })
    await user.click(backBtn)
    expect(onNavigate).toHaveBeenCalledWith('GENERATE_DESIGN_PLANNING')

    const node7Btn = screen.getByRole('button', { name: /Go to Node 7 \(Planning Results\) →/i })
    await user.click(node7Btn)
    expect(onNavigate).toHaveBeenCalledWith('PLANNING_RESULTS')
  })
})
