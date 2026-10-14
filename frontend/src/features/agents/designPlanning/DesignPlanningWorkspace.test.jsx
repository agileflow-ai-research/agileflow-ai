import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runDesignPlanningAgent } from './designPlanningAgentService.js'
import DesignPlanningWorkspace from './DesignPlanningWorkspace.jsx'

vi.mock('./designPlanningAgentService.js', () => ({
  runDesignPlanningAgent: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-002', agent_type: 'DESIGN_PLANNING',
  name: 'BookEase', domain: 'Hospitality',
}

describe('DesignPlanningWorkspace', () => {
  beforeEach(() => vi.clearAllMocks())

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
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.type(screen.getByLabelText('Preferred Technology Stack'), 'React and FastAPI')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Epics' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))

    expect(runDesignPlanningAgent).toHaveBeenCalledWith('AGP-002', {
      requirements: 'Guests need room booking.',
      preferred_technology_stack: 'React and FastAPI',
      selected_outputs: ['EPICS'],
    })
    expect(await screen.findByRole('heading', { name: 'Design and planning results' })).toBeInTheDocument()
    expect(screen.getByText('Booking')).toBeInTheDocument()
    expect(screen.queryByText('System Architecture')).not.toBeInTheDocument()
    expect(onRunCompleted).toHaveBeenCalledWith(expect.objectContaining({ run_id: 'RUN-002' }))
  })

  it('validates specification, output selection, team count, and sprint duration', async () => {
    const user = userEvent.setup()
    render(<DesignPlanningWorkspace project={project} />)
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('at least one usable specification source')
    await user.type(screen.getByLabelText(/Software Requirements Specification/), 'Booking SRS')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Select at least one output')
    await user.click(screen.getByRole('checkbox', { name: 'Sprint Plan' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))
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
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.type(screen.getByLabelText('Development team count'), '2')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Jira-ready Plan' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))
    expect(await screen.findByText(/Synchronization:/)).toHaveTextContent('Not performed')
    expect(screen.getByText(/No Jira Cloud synchronization was performed/)).toBeInTheDocument()
  })
})
