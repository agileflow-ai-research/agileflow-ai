import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import HumanReviewPanel from './HumanReviewPanel.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

describe('HumanReviewPanel', () => {
  const project = {
    agent_project_id: 'AGP-002',
    name: 'BookEase',
    domain: 'Hospitality',
  }

  const validProps = {
    project,
    input: {
      requirements: 'Users can register, book rooms, and cancel reservations.',
      SRS: '',
      user_stories: '',
      acceptance_criteria: '',
      preferred_technology_stack: 'React 19, FastAPI, PostgreSQL',
      technical_constraints: 'Sub-200ms API response',
      deployment_preference: 'Docker',
      database_preference: 'PostgreSQL 16',
      ui_ux_constraints: 'Dark theme',
      architecture_notes: 'Modular monolith',
      project_start_date: '2026-11-01',
      development_team_count: '5',
      sprint_duration: '14',
      expected_project_duration: '3 months',
      developer_roles: '2 FE, 2 BE, 1 QA',
      developer_skills: 'React, Python',
      team_composition: 'Agile team',
    },
    uploadProvenance: {
      requirements: {
        original_filename: 'SRS.docx',
        size_bytes: 4096,
      },
    },
    selectedOutputs: ['SYSTEM_ARCHITECTURE', 'SPRINT_PLAN'],
    humanReviewApproved: false,
    onSetHumanReviewApproved: vi.fn(),
    onNavigate: vi.fn(),
  }

  it('renders summary metrics, specification summary, selected outputs, and technical summary in order', () => {
    render(<HumanReviewPanel {...validProps} />)

    // Summary metrics
    const metrics = screen.getByLabelText('Summary metrics')
    expect(within(metrics).getByText('Specification sources')).toBeInTheDocument()
    expect(within(metrics).getByText('Selected outputs')).toBeInTheDocument()
    expect(within(metrics).getByText('Developers')).toBeInTheDocument()
    expect(within(metrics).getByText('5')).toBeInTheDocument()
    expect(within(metrics).getByText('Sprint duration')).toBeInTheDocument()
    expect(within(metrics).getByText('14 days')).toBeInTheDocument()

    // 1. Specification summary
    expect(screen.getByRole('heading', { name: /specification summary \(1\)/i })).toBeInTheDocument()
    expect(screen.getByText(/uploaded: SRS\.docx/i)).toBeInTheDocument()
    expect(screen.getByText(/users can register, book rooms/i)).toBeInTheDocument()

    // 2. Selected outputs
    expect(screen.getByRole('heading', { name: /selected outputs \(2\)/i })).toBeInTheDocument()
    expect(screen.getByText('System Architecture')).toBeInTheDocument()
    expect(screen.getByText('SYSTEM_ARCHITECTURE')).toBeInTheDocument()
    expect(screen.getByText('Sprint Plan')).toBeInTheDocument()
    expect(screen.getByText('SPRINT_PLAN')).toBeInTheDocument()

    // 3. Technical & Planning summary with requirement rationale
    expect(screen.getByRole('heading', { name: /technical & planning summary/i })).toBeInTheDocument()
    expect(screen.getByText(/BookEase · Hospitality/i)).toBeInTheDocument()
    expect(screen.getAllByText(/required because sprint_plan was selected/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/React 19, FastAPI, PostgreSQL/i)).toBeInTheDocument()
    expect(screen.getByText(/Modular monolith/i)).toBeInTheDocument()

    // 4. Validation success banner
    expect(screen.getByText(/all validation requirements satisfied/i)).toBeInTheDocument()

    // Standalone review callout
    expect(screen.getByRole('heading', { name: /human review required before starting this standalone run/i })).toBeInTheDocument()
    expect(screen.getByText(/this standalone flow does not invoke integrated h2 approval/i)).toBeInTheDocument()
  })

  it('displays blocked alert and disables approval when validation issues exist', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    // Missing specifications and missing outputs
    render(
      <HumanReviewPanel
        {...validProps}
        input={{ requirements: '', SRS: '', user_stories: '', acceptance_criteria: '' }}
        selectedOutputs={[]}
        onNavigate={onNavigate}
      />,
    )

    // Blocked alert is present
    expect(screen.getByRole('alert', { name: /validation issues/i })).toBeInTheDocument()
    expect(screen.getByText(/Validation Issues \(2\) · Human Review Blocked/i)).toBeInTheDocument()
    expect(screen.getByText(/at least one usable specification source is required/i)).toBeInTheDocument()
    expect(screen.getByText(/at least one output artifact must be selected/i)).toBeInTheDocument()

    // Checkbox is disabled
    const checkbox = screen.getByLabelText(/i have reviewed and confirmed/i)
    expect(checkbox).toBeDisabled()

    // Proceed button is disabled
    const proceedBtn = screen.getByRole('button', { name: /proceed to generate design & planning/i })
    expect(proceedBtn).toBeDisabled()

    // Quick navigation buttons work
    await user.click(screen.getByRole('button', { name: 'Edit in Node 1' }))
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)

    await user.click(screen.getByRole('button', { name: 'Edit in Node 2' }))
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)
  })

  it('displays planning constraint validation issue when SPRINT_PLAN lacks team count or sprint duration with Edit in Node 3', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <HumanReviewPanel
        {...validProps}
        input={{
          ...validProps.input,
          planning_mode: 'CAPACITY_AWARE',
          development_team_count: '',
          sprint_duration: '',
        }}
        selectedOutputs={['SPRINT_PLAN']}
        onNavigate={onNavigate}
      />,
    )

    const alertBox = screen.getByRole('alert')
    expect(within(alertBox).getByText(/development team count is required for capacity-aware sprint planning/i)).toBeInTheDocument()
    expect(within(alertBox).getByText(/sprint duration is required because sprint_plan was selected/i)).toBeInTheDocument()

    const editNode3Buttons = screen.getAllByRole('button', { name: 'Edit in Node 3' })
    expect(editNode3Buttons.length).toBeGreaterThan(0)
    await user.click(editNode3Buttons[0])
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)
  })

  it('allows checking the review confirmation and enables Proceed button', async () => {
    const user = userEvent.setup()
    const onSetHumanReviewApproved = vi.fn()

    const { rerender } = render(
      <HumanReviewPanel
        {...validProps}
        humanReviewApproved={false}
        onSetHumanReviewApproved={onSetHumanReviewApproved}
      />,
    )

    const checkbox = screen.getByLabelText(/i have reviewed and confirmed/i)
    expect(checkbox).toBeEnabled()
    expect(checkbox).not.toBeChecked()

    const proceedBtn = screen.getByRole('button', { name: /proceed to generate design & planning/i })
    expect(proceedBtn).toBeDisabled()

    await user.click(checkbox)
    expect(onSetHumanReviewApproved).toHaveBeenCalledWith(true)

    // When approved, button becomes enabled
    rerender(
      <HumanReviewPanel
        {...validProps}
        humanReviewApproved={true}
        onSetHumanReviewApproved={onSetHumanReviewApproved}
      />,
    )

    expect(proceedBtn).toBeEnabled()
  })

  it('navigates to Node 5 Generate Design & Planning when clicking Proceed', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <HumanReviewPanel
        {...validProps}
        humanReviewApproved={true}
        onNavigate={onNavigate}
      />,
    )

    const proceedBtn = screen.getByRole('button', { name: /proceed to generate design & planning/i })
    await user.click(proceedBtn)

    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)
  })

  it('navigates back to Technical & Planning', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <HumanReviewPanel
        {...validProps}
        onNavigate={onNavigate}
      />,
    )

    await user.click(screen.getByRole('button', { name: /back — technical & planning/i }))
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)
  })
})
