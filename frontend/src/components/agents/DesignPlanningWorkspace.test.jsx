import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runDesignPlanningAgent } from '../../services/designPlanningAgentService.js'
import DesignPlanningWorkspace from './DesignPlanningWorkspace.jsx'

vi.mock('../../services/designPlanningAgentService.js', () => ({
  runDesignPlanningAgent: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-002', agent_type: 'DESIGN_PLANNING',
  name: 'BookEase', domain: 'Hospitality',
}

describe('DesignPlanningWorkspace', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders Screen S2-01 with 5-step wizard, Step 1 active, and all four specification fields', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    expect(screen.getByRole('heading', { name: /standalone design & planning/i })).toBeInTheDocument()
    expect(screen.getByText(/Step 1 of 5 · Requirements \/ Specification Input/)).toBeInTheDocument()
    expect(screen.getByText('Draft input')).toBeInTheDocument()

    // 5-step wizard with Step 1 active
    const step1 = screen.getByText('Specification').closest('li')
    expect(step1).toHaveAttribute('aria-current', 'step')
    expect(screen.getByText('Planning')).toBeInTheDocument()
    expect(screen.getByText('Outputs')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(screen.getByText('Run')).toBeInTheDocument()

    // Specification Sources card
    expect(screen.getByRole('heading', { name: /specification sources/i })).toBeInTheDocument()
    expect(screen.getByText('Provide at least one usable source.')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /requirements selected/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^srs$/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^user stories$/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^acceptance criteria$/i })).toBeInTheDocument()

    // Project Context card
    expect(screen.getByRole('heading', { name: /project context/i })).toBeInTheDocument()
    expect(screen.getAllByText('BookEase').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Hospitality')).toBeInTheDocument()
    expect(screen.queryByLabelText(/project name/i)).not.toBeInTheDocument()

    // Validation information banner
    expect(
      screen.getByText(
        'At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.',
      ),
    ).toBeInTheDocument()

    // Default active specification input field is Requirements
    expect(screen.getByRole('heading', { name: 'Requirements' })).toBeInTheDocument()
    expect(screen.getByText('Manual input — Agent 2 does not require Agent 1.')).toBeInTheDocument()
    expect(screen.getByLabelText('Requirements')).toBeInTheDocument()

    // Can switch to SRS and verify field is available
    await user.click(screen.getByRole('tab', { name: /^srs$/i }))
    expect(screen.getByLabelText(/Software Requirements Specification/)).toBeInTheDocument()

    // Can switch to User Stories and verify field is available
    await user.click(screen.getByRole('tab', { name: /^user stories$/i }))
    expect(screen.getByLabelText('User Stories')).toBeInTheDocument()

    // Can switch to Acceptance Criteria and verify field is available
    await user.click(screen.getByRole('tab', { name: /^acceptance criteria$/i }))
    expect(screen.getByLabelText('Acceptance Criteria')).toBeInTheDocument()

    // Action buttons
    const saveDraftBtn = screen.getByRole('button', { name: 'Save draft' })
    expect(saveDraftBtn).toBeInTheDocument()
    expect(saveDraftBtn).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Continue to planning' })).toBeInTheDocument()
  })

  it('displays project name and domain from project context without duplicate inputs', () => {
    render(<DesignPlanningWorkspace project={project} />)

    expect(screen.getByRole('heading', { name: /project context/i })).toBeInTheDocument()
    expect(screen.getAllByText('BookEase').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Hospitality')).toBeInTheDocument()
    expect(screen.queryByLabelText(/project name/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/domain/i)).not.toBeInTheDocument()
  })

  it('cannot continue to planning with all specification sources empty and displays validation alert', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(
      'At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.',
    )
    expect(screen.getByText('Specification').closest('li')).toHaveAttribute('aria-current', 'step')
  })

  it('can continue to planning when one valid specification source exists', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    await user.click(screen.getByRole('tab', { name: /^user stories$/i }))
    await user.type(screen.getByLabelText('User Stories'), 'As an admin, I want to manage rooms.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // Advanced to Step 2 (Planning)
    expect(screen.getByText('Planning').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('Development team count')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('preserves existing specification values when navigating to planning and back', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    await user.type(screen.getByLabelText('Requirements'), 'High-level business rules.')
    await user.click(screen.getByRole('tab', { name: /^srs$/i }))
    await user.type(screen.getByLabelText(/Software Requirements Specification/), 'Detailed SRS section 1.0.')
    await user.click(screen.getByRole('tab', { name: /^user stories$/i }))
    await user.type(screen.getByLabelText('User Stories'), 'As a guest, I want to reserve a suite.')
    await user.click(screen.getByRole('tab', { name: /^acceptance criteria$/i }))
    await user.type(screen.getByLabelText('Acceptance Criteria'), 'Given a selected date, then suite is reserved.')

    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    expect(screen.getByText('Planning').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('Development team count')).toBeInTheDocument()

    // Navigate back to Step 1
    await user.click(screen.getByRole('button', { name: 'Back' }))

    expect(screen.getByText('Specification').closest('li')).toHaveAttribute('aria-current', 'step')
    await user.click(screen.getByRole('tab', { name: /requirements/i }))
    expect(screen.getByLabelText('Requirements')).toHaveValue('High-level business rules.')
    await user.click(screen.getByRole('tab', { name: /srs/i }))
    expect(screen.getByLabelText(/Software Requirements Specification/)).toHaveValue('Detailed SRS section 1.0.')
    await user.click(screen.getByRole('tab', { name: /user stories/i }))
    expect(screen.getByLabelText('User Stories')).toHaveValue('As a guest, I want to reserve a suite.')
    await user.click(screen.getByRole('tab', { name: /acceptance criteria/i }))
    expect(screen.getByLabelText('Acceptance Criteria')).toHaveValue('Given a selected date, then suite is reserved.')
  })

  it('executes the five-stage workspace and displays only real returned outputs', async () => {
    const user = userEvent.setup()
    const onRunCompleted = vi.fn()
    runDesignPlanningAgent.mockResolvedValue({
      data: {
        run_id: 'RUN-002', status: 'COMPLETED', warnings: [], errors: [],
        outputs: {
          EPICS: [{ id: 'EPIC-001', title: 'Booking', outcome: 'Guests can book', priority: 'HIGH', source_refs: ['SPEC-001'] }],
        },
      },
    })
    render(<DesignPlanningWorkspace project={project} onRunCompleted={onRunCompleted} />)

    expect(screen.getByText('Run')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Requirements'), 'Guests need room booking.')
    await user.click(screen.getByRole('button', { name: /continue to planning|next/i }))
    await user.type(screen.getByLabelText('Preferred Technology Stack'), 'React and FastAPI')
    await user.click(screen.getByRole('button', { name: /continue to outputs|next/i }))
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    await user.click(screen.getByRole('button', { name: /review selection|next/i }))
    await user.click(screen.getByRole('button', { name: /run agent/i }))

    expect(runDesignPlanningAgent).toHaveBeenCalledWith('AGP-002', {
      requirements: 'Guests need room booking.',
      preferred_technology_stack: 'React and FastAPI',
      selected_outputs: ['EPICS'],
    })
    expect(await screen.findByRole('heading', { name: /Agent 2 Results|Design and planning results/i })).toBeInTheDocument()
    expect(screen.getByText(/Booking/)).toBeInTheDocument()
    expect(screen.queryByText('System Architecture')).not.toBeInTheDocument()
    expect(onRunCompleted).toHaveBeenCalledWith(expect.objectContaining({ run_id: 'RUN-002' }))
  })

  it('validates specification, output selection, team count, and sprint duration', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)
    await user.click(screen.getByRole('button', { name: /continue to planning|next/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/at least one usable source/i)
    await user.click(screen.getByRole('tab', { name: /^srs$/i }))
    await user.type(screen.getByLabelText(/Software Requirements Specification/), 'Booking SRS')
    await user.click(screen.getByRole('button', { name: /continue to planning|next/i }))
    await user.click(screen.getByRole('button', { name: /continue to outputs|next/i }))
    await user.click(screen.getByRole('button', { name: /review selection|next/i }))
    expect(screen.getByRole('alert')).toHaveTextContent('Select at least one output')
    await user.click(screen.getByRole('checkbox', { name: 'Sprint Plan' }))
    await user.click(screen.getByRole('button', { name: /review selection|next/i }))
    await user.click(screen.getByRole('button', { name: /run agent/i }))
    expect(screen.getByText(/positive team count is required/i)).toBeInTheDocument()
    expect(screen.getByText(/positive sprint duration is required/i)).toBeInTheDocument()
    expect(runDesignPlanningAgent).not.toHaveBeenCalled()
  })

  it('labels Jira output as unsynchronized structured data', async () => {
    const user = userEvent.setup()
    runDesignPlanningAgent.mockResolvedValue({
      data: {
        run_id: 'RUN-003', status: 'COMPLETED', warnings: [{ code: 'JIRA_NOT_SYNCHRONIZED', message: 'No Jira Cloud synchronization was performed' }], errors: [],
        outputs: { JIRA_PLAN: { epics: [], stories: [], tasks: [], sprints: [], assignments: [], priorities: [], synchronization: 'NOT_PERFORMED' } },
      },
    })
    render(<DesignPlanningWorkspace project={project} />)
    await user.type(screen.getByLabelText('Requirements'), 'Plan booking work')
    await user.click(screen.getByRole('button', { name: /continue to planning|next/i }))
    await user.type(screen.getByLabelText('Development team count'), '2')
    await user.click(screen.getByRole('button', { name: /continue to outputs|next/i }))
    await user.click(screen.getByRole('checkbox', { name: 'Jira-ready Plan' }))
    await user.click(screen.getByRole('button', { name: /review selection|next/i }))
    await user.click(screen.getByRole('button', { name: /run agent/i }))
    expect(await screen.findByText(/Synchronization:/)).toHaveTextContent('Not performed')
    expect(screen.getByText(/No Jira Cloud synchronization was performed/)).toBeInTheDocument()
  })

  it('renders Screen S2-02 with Step 2 active, Technical preferences, Planning inputs, and Conditional validation', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    // Provide a valid specification and advance to Step 2
    await user.type(screen.getByLabelText('Requirements'), 'High-level requirement.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // Header & Badge
    expect(screen.getByRole('heading', { name: 'Technical & Planning Information' })).toBeInTheDocument()
    expect(screen.getByText(/Step 2 of 5 · Project preferences and team context/)).toBeInTheDocument()
    expect(screen.getByText('Inputs valid')).toBeInTheDocument()

    // 5-step wizard with Step 2 active
    const step2 = screen.getByText('Planning').closest('li')
    expect(step2).toHaveAttribute('aria-current', 'step')
    const step1 = screen.getByText('Specification').closest('li')
    expect(step1).not.toHaveAttribute('aria-current', 'step')

    // Technical preferences card
    expect(screen.getByRole('heading', { name: 'Technical preferences' })).toBeInTheDocument()
    expect(screen.getByText('Optional design constraints.')).toBeInTheDocument()
    expect(screen.getByLabelText('Preferred Technology Stack')).toBeInTheDocument()
    expect(screen.getByLabelText('Technical Constraints')).toBeInTheDocument()
    expect(screen.getByLabelText('Deployment Preference')).toBeInTheDocument()
    expect(screen.getByLabelText('Database Preference')).toBeInTheDocument()
    expect(screen.getByLabelText('UI/UX Constraints')).toBeInTheDocument()
    expect(screen.getByLabelText('Architecture Notes')).toBeInTheDocument()

    // Planning inputs card
    expect(screen.getByRole('heading', { name: 'Planning inputs' })).toBeInTheDocument()
    expect(screen.getByText('Used by sprint and assignment outputs.')).toBeInTheDocument()
    expect(screen.getByLabelText('Development team count')).toBeInTheDocument()
    expect(screen.getByLabelText('Sprint duration (days)')).toBeInTheDocument()
    expect(screen.getByLabelText('Expected project duration')).toBeInTheDocument()
    expect(screen.getByLabelText('Developer Roles')).toBeInTheDocument()
    expect(screen.getByLabelText('Developer Skills')).toBeInTheDocument()
    expect(screen.getByLabelText('Team Composition')).toBeInTheDocument()

    // Conditional validation card
    expect(screen.getByRole('heading', { name: 'Conditional validation' })).toBeInTheDocument()
    expect(screen.getByText('Planning data is checked before Agent2Engine runs.')).toBeInTheDocument()
    expect(screen.getByText(/requires development_team_count \+ sprint_duration/)).toBeInTheDocument()
    expect(screen.getByText('SPRINT_PLAN')).toBeInTheDocument()
    expect(screen.getByText('TASK_ASSIGNMENT')).toBeInTheDocument()
    expect(screen.getByText('JIRA_PLAN')).toBeInTheDocument()

    // Action buttons
    expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue to outputs' })).toBeInTheDocument()
  })

  it('navigates seamlessly between S2-01, S2-02, and S2-03 while preserving all entered values', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    // S2-01: Enter Requirements
    await user.type(screen.getByLabelText('Requirements'), 'System specification text.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02: Enter technical and planning values
    await user.type(screen.getByLabelText('Preferred Technology Stack'), 'FastAPI + React')
    await user.type(screen.getByLabelText('Technical Constraints'), 'Low latency required')
    await user.type(screen.getByLabelText('Deployment Preference'), 'Docker')
    await user.type(screen.getByLabelText('Database Preference'), 'PostgreSQL')
    await user.type(screen.getByLabelText('UI/UX Constraints'), 'Accessible dark mode')
    await user.type(screen.getByLabelText('Architecture Notes'), 'Clean architecture')
    await user.type(screen.getByLabelText('Development team count'), '4')
    await user.type(screen.getByLabelText('Sprint duration (days)'), '14')
    await user.type(screen.getByLabelText('Expected project duration'), '6 months')
    await user.type(screen.getByLabelText('Developer Roles'), '2 BE, 2 FE')
    await user.type(screen.getByLabelText('Developer Skills'), 'Python, React')
    await user.type(screen.getByLabelText('Team Composition'), 'Full stack crew')

    // Navigate back to S2-01
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByText('Specification').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('Requirements')).toHaveValue('System specification text.')

    // Navigate forward to S2-02 again
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))
    expect(screen.getByText('Planning').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('Preferred Technology Stack')).toHaveValue('FastAPI + React')
    expect(screen.getByLabelText('Technical Constraints')).toHaveValue('Low latency required')
    expect(screen.getByLabelText('Deployment Preference')).toHaveValue('Docker')
    expect(screen.getByLabelText('Database Preference')).toHaveValue('PostgreSQL')
    expect(screen.getByLabelText('UI/UX Constraints')).toHaveValue('Accessible dark mode')
    expect(screen.getByLabelText('Architecture Notes')).toHaveValue('Clean architecture')
    expect(screen.getByLabelText('Development team count')).toHaveValue(4)
    expect(screen.getByLabelText('Sprint duration (days)')).toHaveValue(14)
    expect(screen.getByLabelText('Expected project duration')).toHaveValue('6 months')
    expect(screen.getByLabelText('Developer Roles')).toHaveValue('2 BE, 2 FE')
    expect(screen.getByLabelText('Developer Skills')).toHaveValue('Python, React')
    expect(screen.getByLabelText('Team Composition')).toHaveValue('Full stack crew')

    // Navigate forward to S2-03 (Outputs)
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Outputs').closest('li')).toHaveAttribute('aria-current', 'step')

    // Navigate back to S2-02
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByText('Planning').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('Preferred Technology Stack')).toHaveValue('FastAPI + React')
    expect(screen.getByLabelText('Development team count')).toHaveValue(4)
  })

  it('does not block advancing from Step 2 to Step 3 when planning inputs are empty', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    await user.type(screen.getByLabelText('Requirements'), 'Base spec.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // On Step 2, click Continue to outputs without entering any team count or sprint duration
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // Successfully advanced to Step 3 (Outputs) without blocking
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Outputs').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renders Screen S2-03 with Step 3 active, 3 output groups, and all exact 14 outputs', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    // Navigate from S2-01 through S2-02 to S2-03
    await user.type(screen.getByLabelText('Requirements'), 'High-level requirement.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // Header & Dynamic Badge
    expect(screen.getByRole('heading', { name: 'Select Agent 2 Outputs' })).toBeInTheDocument()
    expect(screen.getByText(/Step 3 of 5 · Choose only the artifacts needed for this run/)).toBeInTheDocument()
    expect(screen.getByText('0 selected')).toBeInTheDocument()

    // 5-step wizard with Step 3 active
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Outputs').closest('li')).toHaveAttribute('aria-current', 'step')

    // 3 Output Groups
    expect(screen.getByRole('heading', { name: 'Design outputs' })).toBeInTheDocument()
    expect(screen.getByText('Structured technical design artifacts.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Agile planning' })).toBeInTheDocument()
    expect(screen.getByText('Traceable planning hierarchy.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Planning & Jira' })).toBeInTheDocument()
    expect(screen.getByText('Execution-ready planning data.')).toBeInTheDocument()

    // All exact 14 outputs present with both labels and enums
    const expectedOutputs = [
      ['System Architecture', 'SYSTEM_ARCHITECTURE'],
      ['UML Diagrams', 'UML_DIAGRAMS'],
      ['Database Schema', 'DATABASE_SCHEMA'],
      ['API Specification', 'API_SPECIFICATION'],
      ['Wireframes', 'WIREFRAMES'],
      ['UI Flow', 'UI_FLOW'],
      ['Product Backlog', 'PRODUCT_BACKLOG'],
      ['Epics', 'EPICS'],
      ['Features', 'FEATURES'],
      ['User Stories', 'USER_STORIES'],
      ['Tasks', 'TASKS'],
      ['Sprint Plan', 'SPRINT_PLAN'],
      ['Task Assignment', 'TASK_ASSIGNMENT'],
      ['Jira-ready Plan', 'JIRA_PLAN'],
    ]

    expectedOutputs.forEach(([label, code]) => {
      expect(screen.getByRole('checkbox', { name: label })).toBeInTheDocument()
      expect(screen.getByText(code)).toBeInTheDocument()
    })

    // Dependency hints on Group 3 outputs
    expect(screen.getByText(/Requires: development_team_count \+ sprint_duration/)).toBeInTheDocument()
    expect(screen.getAllByText(/^Requires: development_team_count$/).length).toBe(2)

    // Selection behavior callout card
    expect(screen.getByRole('heading', { name: 'Selection behavior' })).toBeInTheDocument()
    expect(
      screen.getByText('Only selected outputs are generated, validated, persisted, and displayed.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Cross-artifact checks are selection-aware: Agent 2 never requires an artifact that the user did not request.',
      ),
    ).toBeInTheDocument()

    // Action buttons
    expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review selection' })).toBeInTheDocument()
  })

  it('handles dynamic selection count, select/deselect, and preserves selections across navigation', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    await user.type(screen.getByLabelText('Requirements'), 'System spec.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    expect(screen.getByText('0 selected')).toBeInTheDocument()

    // Select outputs across different groups
    await user.click(screen.getByRole('checkbox', { name: 'System Architecture' }))
    expect(screen.getByText('1 selected')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    expect(screen.getByText('2 selected')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: 'Sprint Plan' }))
    expect(screen.getByText('3 selected')).toBeInTheDocument()

    // Deselect one
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    expect(screen.getByText('2 selected')).toBeInTheDocument()

    // Navigate back to S2-02
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByText('Planning').closest('li')).toHaveAttribute('aria-current', 'step')

    // Navigate forward to S2-03
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))
    expect(screen.getByText('2 selected')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'System Architecture' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Sprint Plan' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Epics' })).not.toBeChecked()

    // Advance to Step 4 (Review)
    await user.click(screen.getByRole('button', { name: 'Review selection' }))
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Review').closest('li')).toHaveAttribute('aria-current', 'step')

    // Navigate back to S2-03 from Step 4
    await user.click(screen.getByRole('button', { name: /edit inputs|back/i }))
    expect(within(wizardList).getByText('Outputs').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('checkbox', { name: 'System Architecture' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Sprint Plan' })).toBeChecked()
  })

  it('blocks advancing to Review when zero outputs are selected, and shows accessible alert', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    await user.type(screen.getByLabelText('Requirements'), 'System spec.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // With 0 outputs selected, attempt to advance to Review
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // Blocks and shows alert
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Select at least one output.')
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Outputs').closest('li')).toHaveAttribute('aria-current', 'step')

    // Select an output and the error clears / advances
    await user.click(screen.getByRole('checkbox', { name: 'Database Schema' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Review selection' }))
    expect(within(wizardList).getByText('Review').closest('li')).toHaveAttribute('aria-current', 'step')
  })

  it('renders Screen S2-04 with Step 4 active, dynamic metric cards, input summary, selected outputs summary with enums, and human review callout', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    // S2-01: Fill 2 specification sources
    await user.type(screen.getByLabelText('Requirements'), 'High-level business specification.')
    await user.click(screen.getByRole('tab', { name: /^user stories$/i }))
    await user.type(screen.getByLabelText('User Stories'), 'As a guest, I want to book a room.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02: Fill technical preferences and planning inputs
    await user.type(screen.getByLabelText('Preferred Technology Stack'), 'React + FastAPI + MongoDB')
    await user.type(screen.getByLabelText('Architecture Notes'), 'Clean modular architecture')
    await user.type(screen.getByLabelText('Development team count'), '4')
    await user.type(screen.getByLabelText('Sprint duration (days)'), '14')
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // S2-03: Select 3 outputs across different groups
    await user.click(screen.getByRole('checkbox', { name: 'System Architecture' }))
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    await user.click(screen.getByRole('checkbox', { name: 'Sprint Plan' }))
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // Step 4 is active
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Review').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('heading', { level: 2, name: 'Review Before Run' })).toBeInTheDocument()
    expect(screen.getByText('Step 4 of 5 · Human-in-the-loop checkpoint before execution')).toBeInTheDocument()
    expect(screen.getByText('Ready to run')).toBeInTheDocument()

    // Dynamic metric cards
    const metrics = screen.getByLabelText('Summary metrics')
    expect(within(metrics).getByText('Specification sources')).toBeInTheDocument()
    expect(within(metrics).getByText('2')).toBeInTheDocument()
    expect(within(metrics).getByText('Developers')).toBeInTheDocument()
    expect(within(metrics).getByText('4')).toBeInTheDocument()
    expect(within(metrics).getByText('Sprint duration')).toBeInTheDocument()
    expect(within(metrics).getByText('14 days')).toBeInTheDocument()
    expect(within(metrics).getByText('Selected outputs')).toBeInTheDocument()
    expect(within(metrics).getByText('3')).toBeInTheDocument()

    // Input summary card
    expect(screen.getByRole('heading', { name: 'Input summary' })).toBeInTheDocument()
    expect(screen.getByText(/BookEase · Hospitality/)).toBeInTheDocument()
    expect(screen.getByText(/React \+ FastAPI \+ MongoDB/)).toBeInTheDocument()
    expect(screen.getByText(/Clean modular architecture/)).toBeInTheDocument()
    expect(screen.queryByText(/Database:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Deployment:/)).not.toBeInTheDocument()

    // Selected outputs card with grouped summary and enums
    expect(screen.getByRole('heading', { name: 'Selected outputs' })).toBeInTheDocument()
    expect(screen.getByText(/Design outputs \+ Agile planning \+ Planning & Jira/)).toBeInTheDocument()
    expect(screen.getByText('SYSTEM_ARCHITECTURE')).toBeInTheDocument()
    expect(screen.getByText('EPICS')).toBeInTheDocument()
    expect(screen.getByText('SPRINT_PLAN')).toBeInTheDocument()
    expect(screen.queryByText('DATABASE_SCHEMA')).not.toBeInTheDocument()
    expect(screen.queryByText('TASKS')).not.toBeInTheDocument()

    // Human review callout card
    expect(
      screen.getByRole('heading', { name: 'Human review required before starting this standalone run' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'You can go back and correct inputs or output selection. This standalone flow does not invoke integrated H2 approval.',
      ),
    ).toBeInTheDocument()

    // Navigation buttons
    expect(screen.getByRole('button', { name: 'Edit inputs' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run Agent 2' })).toBeInTheDocument()
  })

  it('displays neutral "Not provided" for missing optional planning inputs in summary metrics and preserves state on Edit inputs navigation', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    // S2-01: 1 source filled
    await user.type(screen.getByLabelText('Requirements'), 'Simple standalone spec.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02: Leave optional technical/planning fields blank
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // S2-03: Select 2 design outputs (no team/sprint requirements)
    await user.click(screen.getByRole('checkbox', { name: 'System Architecture' }))
    await user.click(screen.getByRole('checkbox', { name: 'Database Schema' }))
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // S2-04 Metrics
    const metrics = screen.getByLabelText('Summary metrics')
    expect(within(metrics).getByText('Specification sources')).toBeInTheDocument()
    expect(within(metrics).getByText('1')).toBeInTheDocument()
    expect(within(metrics).getAllByText('Not provided').length).toBe(2)
    expect(within(metrics).getByText('2')).toBeInTheDocument()

    // Input summary card shows no optional preferences message
    expect(screen.getByText('No additional technical preferences provided.')).toBeInTheDocument()

    // Click Edit inputs to navigate back to S2-03
    await user.click(screen.getByRole('button', { name: 'Edit inputs' }))
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Outputs').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('checkbox', { name: 'System Architecture' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Database Schema' })).toBeChecked()

    // Click Back to S2-02
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(within(wizardList).getByText('Planning').closest('li')).toHaveAttribute('aria-current', 'step')

    // Click Back to S2-01
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(within(wizardList).getByText('Specification').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('Requirements')).toHaveValue('Simple standalone spec.')
  })

  it('blocks execution from Step 4 when selected outputs require planning inputs, redirecting to Step 2 with errors', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)

    // S2-01
    await user.type(screen.getByLabelText('Requirements'), 'Hotel booking spec.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02: skip entering team count and sprint duration
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // S2-03: Select Sprint Plan (requires team count and sprint duration)
    await user.click(screen.getByRole('checkbox', { name: 'Sprint Plan' }))
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // On Step 4, click Run Agent 2
    await user.click(screen.getByRole('button', { name: 'Run Agent 2' }))

    // Redirected to Step 2 (Planning) with validation errors
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Planning').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByText('A positive team count is required for capacity or assignment planning.')).toBeInTheDocument()
    expect(screen.getByText('A positive sprint duration is required for sprint planning.')).toBeInTheDocument()
    expect(runDesignPlanningAgent).not.toHaveBeenCalled()
  })

  it('renders Screen S2-05 with Step 5 active, RUNNING status, pipeline stages, activity, run evidence, and safety note while execution is pending', async () => {
    const user = userEvent.setup()
    let resolveRun
    runDesignPlanningAgent.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRun = resolve
        }),
    )

    render(<DesignPlanningWorkspace project={project} />)

    // S2-01
    await user.type(screen.getByLabelText('Requirements'), 'Production-grade reservation system.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02
    await user.type(screen.getByLabelText('Development team count'), '3')
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // S2-03
    await user.click(screen.getByRole('checkbox', { name: 'System Architecture' }))
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // S2-04 -> click Run Agent 2
    await user.click(screen.getByRole('button', { name: 'Run Agent 2' }))

    // Step 5 is active
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Run').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('heading', { level: 2, name: 'Agent 2 is Processing' })).toBeInTheDocument()
    expect(screen.getByText('Step 5 of 5 · Agent 2 execution in progress')).toBeInTheDocument()
    expect(screen.getAllByText('RUNNING').length).toBe(2)

    // Execution pipeline card with all 7 stages
    expect(screen.getByRole('heading', { name: 'Execution pipeline' })).toBeInTheDocument()
    expect(screen.getByText('Provider generation is combined with deterministic checks.')).toBeInTheDocument()
    const pipeline = screen.getByLabelText('Execution pipeline stages')
    const stages = [
      'Input validation',
      'Normalization',
      'Agent2Engine',
      'Structured generation',
      'Consistency validation',
      'Correction',
      'Persist results',
    ]
    stages.forEach((stage) => {
      expect(within(pipeline).getByText(stage)).toBeInTheDocument()
    })

    // Current activity card
    expect(screen.getByRole('heading', { name: 'Current activity' })).toBeInTheDocument()
    expect(screen.getByText('Generating and validating the selected Agent 2 outputs.')).toBeInTheDocument()

    // Run evidence card
    expect(screen.getByRole('heading', { name: 'Run evidence' })).toBeInTheDocument()
    const evidence = screen.getByLabelText('Run evidence details')
    expect(within(evidence).getByText(/Run status:/)).toBeInTheDocument()
    expect(within(evidence).getByText('RUNNING')).toBeInTheDocument()
    expect(within(evidence).getByText(/BookEase · Hospitality/)).toBeInTheDocument()
    expect(within(evidence).getByText(/Selected outputs \(2\): SYSTEM_ARCHITECTURE, EPICS/)).toBeInTheDocument()
    expect(within(evidence).getByText(/Development team count: 3/)).toBeInTheDocument()

    // Safety note card
    expect(
      screen.getByText('Deterministic user-input errors are rejected before model execution and do not consume correction attempts.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Generated-output correction is bounded by the existing engine policy/),
    ).toBeInTheDocument()

    // No navigation buttons during processing
    expect(screen.queryByRole('button', { name: /edit inputs|back/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /run agent/i })).not.toBeInTheDocument()

    // API called exactly once with exact payload
    expect(runDesignPlanningAgent).toHaveBeenCalledTimes(1)
    expect(runDesignPlanningAgent).toHaveBeenCalledWith('AGP-002', {
      requirements: 'Production-grade reservation system.',
      development_team_count: 3,
      selected_outputs: ['SYSTEM_ARCHITECTURE', 'EPICS'],
    })

    // Complete the pending Promise
    resolveRun({
      data: {
        run_id: 'RUN-777',
        status: 'COMPLETED',
        warnings: [],
        errors: [],
        outputs: {
          EPICS: [{ id: 'EPIC-001', title: 'Booking', outcome: 'Guests can book', priority: 'HIGH', source_refs: ['SPEC-001'] }],
        },
      },
    })

    // Transitions to results screen
    expect(await screen.findByRole('heading', { name: /Agent 2 Results|Design and planning results/i })).toBeInTheDocument()
    expect(screen.queryByText('Agent 2 is Processing')).not.toBeInTheDocument()
  })

  it('failed response exits processing state and displays safe error message on Step 4', async () => {
    const user = userEvent.setup()
    runDesignPlanningAgent.mockRejectedValue(new Error('Backend processing timeout'))

    render(<DesignPlanningWorkspace project={project} />)

    // S2-01
    await user.type(screen.getByLabelText('Requirements'), 'Spec for failure test.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // S2-03
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // S2-04 -> Run Agent 2
    await user.click(screen.getByRole('button', { name: 'Run Agent 2' }))

    // Returns to Step 4 on error and displays error alert
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(await screen.findByRole('alert')).toHaveTextContent('Backend processing timeout')
    expect(within(wizardList).getByText('Review').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('button', { name: 'Run Agent 2' })).toBeEnabled()
  })

  it('renders Screen S2-06 Results Overview after successful API call with COMPLETED status, dynamic metrics, truthful summaries, and no fabricated values', async () => {
    const user = userEvent.setup()
    runDesignPlanningAgent.mockResolvedValue({
      data: {
        run_id: 'RUN-999',
        status: 'COMPLETED',
        warnings: [{ code: 'CAPACITY_NOTE', message: 'Calculated using baseline velocity' }],
        errors: [],
        outputs: {
          SYSTEM_ARCHITECTURE: {
            components: [
              { id: 'CMP-01', name: 'Web', source_refs: ['SPEC-01'] },
              { id: 'CMP-02', name: 'API', source_refs: ['SPEC-01'] },
            ],
          },
          EPICS: [{ id: 'EPIC-01', title: 'Onboarding', source_refs: ['SPEC-01'] }],
          USER_STORIES: [{ id: 'STORY-01', epic_id: 'EPIC-01', source_refs: ['SPEC-01'] }],
        },
      },
    })

    render(<DesignPlanningWorkspace project={project} />)

    // S2-01
    await user.type(screen.getByLabelText('Requirements'), 'System spec for results overview.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // S2-03
    await user.click(screen.getByRole('checkbox', { name: 'System Architecture' }))
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    await user.click(screen.getByRole('checkbox', { name: 'User Stories' }))
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // S2-04 -> Run Agent 2
    await user.click(screen.getByRole('button', { name: 'Run Agent 2' }))

    // S2-06 renders
    expect(await screen.findByRole('heading', { level: 2, name: 'Agent 2 Results' })).toBeInTheDocument()
    expect(screen.getByText('Generated design and planning artifacts')).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()

    // Summary metrics derived dynamically from real response
    const metrics = screen.getByLabelText('Summary metrics')
    expect(within(metrics).getByText('Outputs generated')).toBeInTheDocument()
    expect(within(metrics).getByText('3')).toBeInTheDocument()
    expect(within(metrics).getByText('Validation')).toBeInTheDocument()
    expect(within(metrics).getByText('Passed')).toBeInTheDocument()
    expect(within(metrics).getByText('Correction attempts')).toBeInTheDocument()
    expect(within(metrics).getByText('Not available')).toBeInTheDocument() // Not fabricated
    expect(within(metrics).getByText('Traceability')).toBeInTheDocument()
    expect(within(metrics).getByText('Available')).toBeInTheDocument()

    // Result package cards summarize only returned outputs
    expect(screen.getByRole('heading', { name: 'Design package' })).toBeInTheDocument()
    expect(screen.getByText(/System architecture · 2 components/)).toBeInTheDocument()
    expect(screen.queryByText(/Database schema/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Wireframes/)).not.toBeInTheDocument()

    expect(screen.getByRole('heading', { name: 'Planning package' })).toBeInTheDocument()
    expect(screen.getByText(/1 epic · 1 story/)).toBeInTheDocument()
    expect(screen.queryByText(/Sprint plan/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Task assignments/)).not.toBeInTheDocument()

    // Validation evidence & truthful warnings
    expect(screen.getByRole('heading', { name: 'Validation & traceability evidence' })).toBeInTheDocument()
    expect(screen.getByText('Structural validation passed')).toBeInTheDocument()
    expect(screen.getByText('Cross-artifact references valid')).toBeInTheDocument()
    expect(screen.getByText(/Calculated using baseline velocity/)).toBeInTheDocument()

    // Traceability chain derived from real objects
    expect(screen.getByText(/Example trace: SPEC-01 → EPIC-01 → STORY-01/)).toBeInTheDocument()

    // Actions
    expect(screen.getByRole('button', { name: 'View design artifacts' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'View planning hierarchy' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Open run history' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Start another run' })).toBeEnabled()

    // API was called only once
    expect(runDesignPlanningAgent).toHaveBeenCalledTimes(1)
  })

  it('Start another run resets to Step 0 (Specification) and preserves draft inputs without re-calling the API', async () => {
    const user = userEvent.setup()
    runDesignPlanningAgent.mockResolvedValue({
      data: {
        run_id: 'RUN-1000',
        status: 'COMPLETED',
        warnings: [],
        errors: [],
        outputs: {
          EPICS: [{ id: 'EPIC-01', title: 'Reservation' }],
        },
      },
    })

    render(<DesignPlanningWorkspace project={project} />)

    // S2-01
    await user.type(screen.getByLabelText('Requirements'), 'High-level hotel reservation spec.')
    await user.click(screen.getByRole('button', { name: 'Continue to planning' }))

    // S2-02
    await user.click(screen.getByRole('button', { name: 'Continue to outputs' }))

    // S2-03
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    await user.click(screen.getByRole('button', { name: 'Review selection' }))

    // S2-04
    await user.click(screen.getByRole('button', { name: 'Run Agent 2' }))

    // S2-06
    expect(await screen.findByRole('heading', { level: 2, name: 'Agent 2 Results' })).toBeInTheDocument()
    expect(runDesignPlanningAgent).toHaveBeenCalledTimes(1)

    // Click Start another run
    await user.click(screen.getByRole('button', { name: 'Start another run' }))

    // Resets to Step 0 (Specification)
    const wizardList = screen.getByRole('list', { name: /agent input steps/i })
    expect(within(wizardList).getByText('Specification').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('Requirements')).toHaveValue('High-level hotel reservation spec.')
    expect(screen.getByText('Draft input')).toBeInTheDocument()

    // API was NOT re-called
    expect(runDesignPlanningAgent).toHaveBeenCalledTimes(1)
  })
})


