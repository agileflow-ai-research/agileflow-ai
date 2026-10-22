import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import OutputSelectionPanel from './OutputSelectionPanel.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

describe('OutputSelectionPanel', () => {
  const defaultProps = {
    input: {},
    selectedOutputs: [],
    errors: {},
    onToggleOutput: vi.fn(),
    onSelectAll: vi.fn(),
    onClearAll: vi.fn(),
    onNavigate: vi.fn(),
    onValidate: vi.fn(() => true),
  }

  it('renders 3 output groups with all 14 outputs', () => {
    render(<OutputSelectionPanel {...defaultProps} />)

    // 3 Groups
    expect(screen.getByRole('heading', { name: 'Design outputs' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Agile planning' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Planning & Jira' })).toBeInTheDocument()

    // 14 Outputs
    expect(screen.getByLabelText('System Architecture')).toBeInTheDocument()
    expect(screen.getByLabelText('UML Diagrams')).toBeInTheDocument()
    expect(screen.getByLabelText('Database Schema')).toBeInTheDocument()
    expect(screen.getByLabelText('API Specification')).toBeInTheDocument()
    expect(screen.getByLabelText('Wireframes')).toBeInTheDocument()
    expect(screen.getByLabelText('UI Flow')).toBeInTheDocument()
    expect(screen.getByLabelText('Product Backlog')).toBeInTheDocument()
    expect(screen.getByLabelText('Epics')).toBeInTheDocument()
    expect(screen.getByLabelText('Features')).toBeInTheDocument()
    expect(screen.getByLabelText('User Stories')).toBeInTheDocument()
    expect(screen.getByLabelText('Tasks')).toBeInTheDocument()
    expect(screen.getByLabelText('Sprint Plan')).toBeInTheDocument()
    expect(screen.getByLabelText('Task Assignment')).toBeInTheDocument()
    expect(screen.getByLabelText('Jira-ready Plan')).toBeInTheDocument()

    // Dependency hints
    expect(screen.getByText(/requires: development_team_count \+ sprint_duration/i)).toBeInTheDocument()

    // Selection behavior card
    expect(screen.getByRole('heading', { name: /selection behavior/i })).toBeInTheDocument()
  })

  it('toggles outputs when clicking checkboxes', async () => {
    const user = userEvent.setup()
    const onToggleOutput = vi.fn()
    render(<OutputSelectionPanel {...defaultProps} onToggleOutput={onToggleOutput} />)

    await user.click(screen.getByLabelText('System Architecture'))
    expect(onToggleOutput).toHaveBeenCalledWith('SYSTEM_ARCHITECTURE')
  })

  it('triggers onSelectAll and onClearAll', async () => {
    const user = userEvent.setup()
    const onSelectAll = vi.fn()
    const onClearAll = vi.fn()
    render(
      <OutputSelectionPanel
        {...defaultProps}
        onSelectAll={onSelectAll}
        onClearAll={onClearAll}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Select all (14)' }))
    expect(onSelectAll).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(onClearAll).toHaveBeenCalled()
  })

  it('displays conditional warning when SPRINT_PLAN is selected without planning parameters', () => {
    render(
      <OutputSelectionPanel
        {...defaultProps}
        selectedOutputs={['SPRINT_PLAN']}
        input={{ development_team_count: '', sprint_duration: '' }}
      />,
    )

    expect(screen.getByLabelText('Planning requirements warning')).toBeInTheDocument()
    expect(
      screen.getByText(/planning parameters required/i),
    ).toBeInTheDocument()
  })

  it('displays error alert when errors.outputs is set', () => {
    render(
      <OutputSelectionPanel
        {...defaultProps}
        errors={{ outputs: 'Select at least one output.' }}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Select at least one output.')
  })

  it('navigates back to Technical & Planning', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(<OutputSelectionPanel {...defaultProps} onNavigate={onNavigate} />)

    await user.click(screen.getByRole('button', { name: /back — technical & planning/i }))
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)
  })

  it('calls onValidate and navigates to Human Review', async () => {
    const user = userEvent.setup()
    const onValidate = vi.fn(() => true)
    const onNavigate = vi.fn()
    render(
      <OutputSelectionPanel
        {...defaultProps}
        selectedOutputs={['SYSTEM_ARCHITECTURE']}
        onValidate={onValidate}
        onNavigate={onNavigate}
      />,
    )

    await user.click(screen.getByRole('button', { name: /next — human review/i }))
    expect(onValidate).toHaveBeenCalled()
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)
  })
})
