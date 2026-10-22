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

    // Fill team count and sprint duration in Node 3 (dynamically required because SPRINT_PLAN was selected in Node 2)
    const teamInput = within(modal).getByLabelText(/development team count/i)
    const sprintInput = within(modal).getByLabelText(/sprint duration/i)
    await user.type(teamInput, '6')
    await user.type(sprintInput, '10')

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

  it('opens placeholder modal shell for Node 6 Design Results', async () => {
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

    // Modal shell opens with S2-07 details
    expect(await screen.findByTestId('agent2-placeholder-DESIGN_RESULTS')).toBeInTheDocument()
    expect(screen.getByText(/S2-07 · Results Overview/i)).toBeInTheDocument()

    // Close modal
    const closeBtn = screen.getByRole('button', { name: 'Close' })
    await user.click(closeBtn)
    expect(screen.queryByTestId('agent2-placeholder-DESIGN_RESULTS')).not.toBeInTheDocument()
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
    expect(screen.getByRole('heading', { level: 2, name: 'Validation, Traceability & Run History' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'Standalone scope: no Agent 1/3/4 execution · no Orchestrator · no H2 · no integrated SKB write · no Jira Cloud sync · no RAG.',
      ),
    ).toBeInTheDocument()

    // Close modal
    const closeBtn = screen.getByRole('button', { name: 'Close' })
    await user.click(closeBtn)
    expect(screen.queryByTestId('agent2-panel-VALIDATION_TRACEABILITY')).not.toBeInTheDocument()
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
