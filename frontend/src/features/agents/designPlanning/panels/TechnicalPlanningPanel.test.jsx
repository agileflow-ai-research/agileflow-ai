import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import TechnicalPlanningPanel from './TechnicalPlanningPanel.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

describe('TechnicalPlanningPanel', () => {
  const defaultProps = {
    input: {
      preferred_technology_stack: '',
      technical_constraints: '',
      deployment_preference: '',
      database_preference: '',
      ui_ux_constraints: '',
      architecture_notes: '',
      development_team_count: '',
      sprint_duration: '',
      expected_project_duration: '',
      developer_roles: '',
      developer_skills: '',
      team_composition: '',
    },
    errors: {},
    onUpdateField: vi.fn(),
    onNavigate: vi.fn(),
    onValidate: vi.fn(() => true),
  }

  it('renders all technical preferences and planning input fields', () => {
    render(<TechnicalPlanningPanel {...defaultProps} />)

    // Technical preferences
    expect(screen.getByRole('heading', { name: /technical preferences/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/preferred technology stack/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/technical constraints/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/deployment preference/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/database preference/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/ui\/ux constraints/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/architecture notes/i)).toBeInTheDocument()

    // Planning inputs
    expect(screen.getByRole('heading', { name: /planning inputs/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/development team count/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/sprint duration/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/expected project duration/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/developer roles/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/developer skills/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/team composition/i)).toBeInTheDocument()

    // Conditional validation card
    expect(screen.getByRole('heading', { name: /conditional validation/i })).toBeInTheDocument()
    expect(screen.getByText(/SPRINT_PLAN/)).toBeInTheDocument()
    expect(screen.getByText(/TASK_ASSIGNMENT/)).toBeInTheDocument()
    expect(screen.getByText(/JIRA_PLAN/)).toBeInTheDocument()

    // Footer buttons
    expect(screen.getByRole('button', { name: /back — project & specifications/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next — output selection/i })).toBeInTheDocument()
  })

  it('updates fields when user types', async () => {
    const user = userEvent.setup()
    const onUpdateField = vi.fn()
    render(<TechnicalPlanningPanel {...defaultProps} onUpdateField={onUpdateField} />)

    const stackInput = screen.getByLabelText(/preferred technology stack/i)
    await user.type(stackInput, 'React')
    expect(onUpdateField).toHaveBeenCalled()

    const teamInput = screen.getByLabelText(/development team count/i)
    await user.type(teamInput, '5')
    expect(onUpdateField).toHaveBeenCalled()
  })

  it('displays validation errors on team count and sprint duration', () => {
    render(
      <TechnicalPlanningPanel
        {...defaultProps}
        errors={{
          development_team_count: 'Team count required',
          sprint_duration: 'Sprint duration required',
        }}
      />,
    )

    expect(screen.getByText('Team count required')).toBeInTheDocument()
    expect(screen.getByText('Sprint duration required')).toBeInTheDocument()
  })

  it('navigates back to Project & Specifications', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(<TechnicalPlanningPanel {...defaultProps} onNavigate={onNavigate} />)

    await user.click(screen.getByRole('button', { name: /back — project & specifications/i }))
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)
  })

  it('calls onValidate and navigates to Output Selection', async () => {
    const user = userEvent.setup()
    const onValidate = vi.fn(() => true)
    const onNavigate = vi.fn()
    render(
      <TechnicalPlanningPanel
        {...defaultProps}
        onValidate={onValidate}
        onNavigate={onNavigate}
      />,
    )

    await user.click(screen.getByRole('button', { name: /next — output selection/i }))
    expect(onValidate).toHaveBeenCalled()
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)
  })
})
