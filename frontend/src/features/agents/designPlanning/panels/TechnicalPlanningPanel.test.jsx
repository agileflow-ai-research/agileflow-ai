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
    selectedOutputs: [],
    errors: {},
    onUpdateField: vi.fn(),
    onNavigate: vi.fn(),
    onValidate: vi.fn(() => true),
  }

  it('renders all 3 sections: Required inputs, Recommended inputs, and Optional technical preferences', () => {
    render(<TechnicalPlanningPanel {...defaultProps} />)

    // Top banner
    expect(screen.getByRole('heading', { name: /selected outputs/i })).toBeInTheDocument()
    expect(screen.getByText(/provide the additional technical and planning information/i)).toBeInTheDocument()

    // 3 Organized Sections
    expect(screen.getByRole('heading', { name: /required inputs/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /recommended inputs/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /optional technical preferences/i })).toBeInTheDocument()

    // Technical preferences fields
    expect(screen.getByLabelText(/preferred technology stack/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/technical constraints/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/deployment preference/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/database preference/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/ui\/ux constraints/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/architecture notes/i)).toBeInTheDocument()

    // Planning inputs fields
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
    expect(screen.getByRole('button', { name: /back — output selection/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next — human review/i })).toBeInTheDocument()
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
        selectedOutputs={['SPRINT_PLAN']}
        errors={{
          development_team_count: 'Development team count is required because SPRINT_PLAN was selected.',
          sprint_duration: 'Sprint duration is required because SPRINT_PLAN was selected.',
        }}
      />,
    )

    expect(screen.getByText('Development team count is required because SPRINT_PLAN was selected.')).toBeInTheDocument()
    expect(screen.getByText('Sprint duration is required because SPRINT_PLAN was selected.')).toBeInTheDocument()
  })

  it('dynamically requires team count and sprint duration when SPRINT_PLAN is selected', () => {
    render(
      <TechnicalPlanningPanel
        {...defaultProps}
        selectedOutputs={['SPRINT_PLAN']}
      />,
    )

    expect(screen.getByLabelText(/development team count \*/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/sprint duration \(days\) \*/i)).toBeInTheDocument()
    expect(screen.getAllByText(/required because sprint_plan was selected/i).length).toBeGreaterThan(0)
  })

  it('dynamically requires team count only when TASK_ASSIGNMENT is selected', () => {
    render(
      <TechnicalPlanningPanel
        {...defaultProps}
        selectedOutputs={['TASK_ASSIGNMENT']}
      />,
    )

    expect(screen.getByLabelText(/development team count \*/i)).toBeInTheDocument()
    expect(screen.getByText(/required because task_assignment was selected/i)).toBeInTheDocument()
    // sprint duration is optional (in recommended inputs, without asterisk)
    expect(screen.getByLabelText(/^sprint duration \(days\)$/i)).toBeInTheDocument()
  })

  it('dynamically requires team count only when JIRA_PLAN is selected', () => {
    render(
      <TechnicalPlanningPanel
        {...defaultProps}
        selectedOutputs={['JIRA_PLAN']}
      />,
    )

    expect(screen.getByLabelText(/development team count \*/i)).toBeInTheDocument()
    expect(screen.getByText(/required because jira_plan was selected/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^sprint duration \(days\)$/i)).toBeInTheDocument()
  })

  it('does not require planning fields for architecture-only outputs and shows technical preferences prominently', () => {
    render(
      <TechnicalPlanningPanel
        {...defaultProps}
        selectedOutputs={['SYSTEM_ARCHITECTURE', 'DATABASE_SCHEMA', 'API_SPECIFICATION']}
      />,
    )

    expect(screen.getByText(/none required/i)).toBeInTheDocument()
    expect(screen.getByText(/your selected outputs do not require team count or sprint duration/i)).toBeInTheDocument()
    expect(screen.getByText(/design context/i)).toBeInTheDocument()
  })

  it('preserves previously entered values when output selections change', () => {
    const inputWithValues = {
      ...defaultProps.input,
      development_team_count: '6',
      sprint_duration: '10',
      preferred_technology_stack: 'React + Node',
    }

    const { rerender } = render(
      <TechnicalPlanningPanel
        {...defaultProps}
        input={inputWithValues}
        selectedOutputs={['SPRINT_PLAN']}
      />,
    )

    expect(screen.getByLabelText(/development team count/i)).toHaveValue(6)
    expect(screen.getByLabelText(/sprint duration/i)).toHaveValue(10)

    // Deselect SPRINT_PLAN and switch to architecture only
    rerender(
      <TechnicalPlanningPanel
        {...defaultProps}
        input={inputWithValues}
        selectedOutputs={['SYSTEM_ARCHITECTURE']}
      />,
    )

    expect(screen.getByLabelText(/development team count/i)).toHaveValue(6)
    expect(screen.getByLabelText(/sprint duration/i)).toHaveValue(10)
    expect(screen.getByLabelText(/preferred technology stack/i)).toHaveValue('React + Node')
  })

  it('navigates back to Output Selection', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(<TechnicalPlanningPanel {...defaultProps} onNavigate={onNavigate} />)

    await user.click(screen.getByRole('button', { name: /back — output selection/i }))
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)
  })

  it('calls onValidate and navigates to Human Review', async () => {
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

    await user.click(screen.getByRole('button', { name: /next — human review/i }))
    expect(onValidate).toHaveBeenCalled()
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)
  })
})
