import { forwardRef, useImperativeHandle } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import DesignPlanningProjectPage from './DesignPlanningProjectPage.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

const canvasActions = vi.hoisted(() => ({
  autoArrange: vi.fn(),
  resetLayout: vi.fn(),
  focusNode: vi.fn(),
}))

vi.mock('../canvas/DesignPlanningCanvas.jsx', () => ({
  default: forwardRef(function MockDesignPlanningCanvas({ onSelectNode, selectedNodeId }, ref) {
    useImperativeHandle(ref, () => canvasActions)
    return (
      <div aria-label="Agent 2 design and planning workflow canvas" data-selected={selectedNodeId}>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)}>
          Select Project & Specifications
        </button>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)}>
          Select Technical & Planning
        </button>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)}>
          Select Output Selection
        </button>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)}>
          Select Human Review
        </button>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)}>
          Select Generate Design & Planning
        </button>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS)}>
          Select Design Results
        </button>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS)}>
          Select Planning Results
        </button>
        <button type="button" onClick={() => onSelectNode(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}>
          Select Validation & Traceability
        </button>
      </div>
    )
  }),
}))

describe('DesignPlanningProjectPage', () => {
  const mockProject = {
    agent_project_id: 'AGP-002',
    name: 'BookEase Architecture & Sprints',
    agent_type: 'DESIGN_PLANNING',
    status: 'ACTIVE',
  }

  const mockStatus = {
    label: 'Active',
    tone: 'success',
  }

  const mockRun014 = {
    run_id: 'RUN-014',
    status: 'COMPLETED',
    created_at: '2026-10-22T08:00:00Z',
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

  it('renders page header, status badge, controls, and canvas', () => {
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
      />,
    )

    expect(screen.getByRole('heading', { name: 'BookEase Architecture & Sprints' })).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Auto Arrange' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reset Layout' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Agent 2 design and planning workflow canvas/i)).toBeInTheDocument()
  })

  it('triggers canvas imperative controls on auto arrange and reset layout', async () => {
    const user = userEvent.setup()
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Auto Arrange' }))
    expect(canvasActions.autoArrange).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Reset Layout' }))
    expect(canvasActions.resetLayout).toHaveBeenCalled()
  })

  it('opens real Node 1 panel and navigates through Nodes 1 to 5 while preserving state', async () => {
    const user = userEvent.setup()
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
      />,
    )

    // Open Node 1: Project & Specifications
    await user.click(screen.getByRole('button', { name: 'Select Project & Specifications' }))
    const modal = screen.getByRole('dialog')
    expect(within(modal).getByTestId('agent2-panel-PROJECT_SPECIFICATIONS')).toBeInTheDocument()

    // Type requirements text in Node 1
    const reqTextarea = within(modal).getByPlaceholderText(/users can register and log in/i)
    await user.type(reqTextarea, 'Core booking system requirement')
    expect(reqTextarea).toHaveValue('Core booking system requirement')

    // Navigate to Node 2: Output Selection via button
    await user.click(within(modal).getByRole('button', { name: /next — output selection/i }))
    expect(within(modal).getByTestId('agent2-panel-OUTPUT_SELECTION')).toBeInTheDocument()

    // Select SPRINT_PLAN and SYSTEM_ARCHITECTURE checkboxes in Node 2
    const sprintCheckbox = within(modal).getByLabelText('Sprint Plan')
    const archCheckbox = within(modal).getByLabelText('System Architecture')
    await user.click(sprintCheckbox)
    await user.click(archCheckbox)
    expect(sprintCheckbox).toBeChecked()
    expect(archCheckbox).toBeChecked()

    // Navigate to Node 3: Technical & Planning via button
    await user.click(within(modal).getByRole('button', { name: /next — technical & planning/i }))
    expect(within(modal).getByTestId('agent2-panel-TECHNICAL_PLANNING')).toBeInTheDocument()

    // Fill timeline planning inputs in Node 3 (required because SPRINT_PLAN was selected in Node 2)
    const startDateInput = within(modal).getByLabelText(/project start date/i)
    const durationInput = within(modal).getByLabelText(/expected project duration/i)
    const sprintInput = within(modal).getByLabelText(/sprint duration/i)
    const teamInput = within(modal).getByLabelText(/development team count/i)
    await user.type(startDateInput, '2026-11-01')
    await user.type(durationInput, '3 months')
    await user.type(sprintInput, '10')
    await user.type(teamInput, '6')

    // Navigate forward to Node 4: Human Review
    await user.click(within(modal).getByRole('button', { name: /next — human review/i }))
    expect(within(modal).getByTestId('agent2-panel-HUMAN_REVIEW')).toBeInTheDocument()

    // Verify Node 4 displays summary metrics and validation success
    expect(within(modal).getByText(/all validation requirements satisfied/i)).toBeInTheDocument()
    expect(within(modal).getByText('Core booking system requirement')).toBeInTheDocument()

    // Check review confirmation checkbox
    const reviewCheckbox = within(modal).getByLabelText(/i have reviewed and confirmed/i)
    expect(reviewCheckbox).not.toBeChecked()
    await user.click(reviewCheckbox)
    expect(reviewCheckbox).toBeChecked()

    // Navigate forward to Node 5: Generate Design & Planning
    await user.click(within(modal).getByRole('button', { name: /proceed to generate design & planning/i }))
    expect(within(modal).getByTestId('agent2-panel-GENERATE_DESIGN_PLANNING')).toBeInTheDocument()
    expect(within(modal).getByText('Ready to launch Agent 2 generation')).toBeInTheDocument()
    expect(within(modal).getByRole('button', { name: /start agent 2 generation/i })).toBeEnabled()

    // Navigate back to Node 4
    await user.click(within(modal).getByRole('button', { name: /back — human review/i }))
    expect(within(modal).getByTestId('agent2-panel-HUMAN_REVIEW')).toBeInTheDocument()

    // Navigate back to Node 1
    await user.click(within(modal).getByRole('button', { name: /edit node 1/i }))
    expect(within(modal).getByTestId('agent2-panel-PROJECT_SPECIFICATIONS')).toBeInTheDocument()
    expect(within(modal).getByPlaceholderText(/users can register and log in/i)).toHaveValue(
      'Core booking system requirement',
    )
  })

  it('opens real DesignResultsPanel when Node 6 is selected', async () => {
    const user = userEvent.setup()
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
      />,
    )

    // Click on Design Results node (Node 6)
    await user.click(screen.getByRole('button', { name: 'Select Design Results' }))

    // Real panel is rendered inside modal
    expect(await screen.findByTestId('agent2-panel-DESIGN_RESULTS')).toBeInTheDocument()

    // Close modal
    const closeBtn = screen.getByRole('button', { name: 'Close' })
    await user.click(closeBtn)
    expect(screen.queryByTestId('agent2-panel-DESIGN_RESULTS')).not.toBeInTheDocument()
  })

  it('opens real PlanningResultsPanel when Node 7 is selected', async () => {
    const user = userEvent.setup()
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
      />,
    )

    // Click on Planning Results node (Node 7)
    await user.click(screen.getByRole('button', { name: 'Select Planning Results' }))

    // Real panel is rendered inside modal
    expect(await screen.findByTestId('agent2-panel-PLANNING_RESULTS')).toBeInTheDocument()

    // Close modal
    const closeBtn = screen.getByRole('button', { name: 'Close' })
    await user.click(closeBtn)
    expect(screen.queryByTestId('agent2-panel-PLANNING_RESULTS')).not.toBeInTheDocument()
  })

  it('opens real ValidationTraceabilityPanel when Node 8 is selected', async () => {
    const user = userEvent.setup()
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
      />,
    )

    // Click on Validation & Traceability node (Node 8)
    await user.click(screen.getByRole('button', { name: 'Select Validation & Traceability' }))

    // Real panel is rendered inside modal
    expect(await screen.findByTestId('agent2-panel-VALIDATION_TRACEABILITY')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: /Validation, Traceability & Run History/i })).toBeInTheDocument()

    // Close modal
    const closeBtn = screen.getByRole('button', { name: 'Close' })
    await user.click(closeBtn)
    expect(screen.queryByTestId('agent2-panel-VALIDATION_TRACEABILITY')).not.toBeInTheDocument()
  })

  it('inspects historical RUN-014 outputs in Planning Results without regeneration or Jira sync', async () => {
    const user = userEvent.setup()
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
        runs={[mockRun014]}
      />,
    )

    // Select Node 7 (Planning Results)
    await user.click(screen.getByRole('button', { name: 'Select Planning Results' }))
    const modal = await screen.findByRole('dialog')
    expect(within(modal).getByTestId('agent2-panel-PLANNING_RESULTS')).toBeInTheDocument()

    // Verify historical run badge shows RUN-014 and COMPLETED status
    expect(within(modal).getByText(/RUN-014/i)).toBeInTheDocument()
    expect(within(modal).getByText('COMPLETED')).toBeInTheDocument()

    // Verify sub-tabs are available
    expect(within(modal).getByRole('tab', { name: /planning hierarchy/i })).toBeInTheDocument()
    expect(within(modal).getByRole('tab', { name: /sprint plan/i })).toBeInTheDocument()
    expect(within(modal).getByRole('tab', { name: /jira-ready plan/i })).toBeInTheDocument()

    // Switch to Sprint Plan tab
    await user.click(within(modal).getByRole('tab', { name: /sprint plan/i }))
    expect(within(modal).getByText('Sprint 1')).toBeInTheDocument()
    expect(within(modal).getByText(/40 units/i)).toBeInTheDocument()

    // Switch to Jira-ready Plan tab
    await user.click(within(modal).getByRole('tab', { name: /jira-ready plan/i }))
    expect(within(modal).getByText(/NOT SYNCHRONIZED/i)).toBeInTheDocument()
    expect(within(modal).getByText('Synchronization: NOT_PERFORMED')).toBeInTheDocument()
    expect(within(modal).getByText(/No Jira credentials or remote API calls are used/i)).toBeInTheDocument()
  })

  it('shows clear explanation in Design Results when inspecting planning-only historical run and links to Node 7', async () => {
    const user = userEvent.setup()
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
        runs={[mockRun014]}
      />,
    )

    // Select Node 6 (Design Results)
    await user.click(screen.getByRole('button', { name: 'Select Design Results' }))
    const modal = await screen.findByRole('dialog')
    expect(within(modal).getByTestId('agent2-panel-DESIGN_RESULTS')).toBeInTheDocument()

    // Explanatory state for planning-only run
    expect(within(modal).getByText(/No technical design deliverables selected for this run/i)).toBeInTheDocument()
    expect(within(modal).getByRole('button', { name: /View Planning Results \(Node 7\)/i })).toBeInTheDocument()

    // Clicking button transitions to Node 7
    await user.click(within(modal).getByRole('button', { name: /View Planning Results \(Node 7\)/i }))
    expect(await screen.findByTestId('agent2-panel-PLANNING_RESULTS')).toBeInTheDocument()
  })

  it('does not render duplicate DesignPlanningWorkspace below canvas, keeping page structure clean for Run History', () => {
    render(
      <DesignPlanningProjectPage
        project={mockProject}
        projectStatus={mockStatus}
        entryMode="existing"
      />,
    )

    // Verify DesignPlanningWorkspace is NOT present below canvas
    expect(screen.queryByRole('region', { name: 'Agent 2 Workspace' })).not.toBeInTheDocument()
    // Verify Agent 2 project section has appropriate label
    expect(screen.getByLabelText('Agent 2 design and planning project')).toBeInTheDocument()
  })
})
