import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runRequirementsAgent } from './requirementsAgentService.js'
import RequirementsWorkspace from './RequirementsWorkspace.jsx'

vi.mock('./requirementsAgentService.js', () => ({
  runRequirementsAgent: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-001',
  agent_type: 'REQUIREMENTS',
  name: 'BookEase',
  domain: 'Library',
}

describe('RequirementsWorkspace', () => {
  beforeEach(() => vi.clearAllMocks())

  it('runs the backend endpoint and renders real returned selected outputs', async () => {
    const user = userEvent.setup()
    const onRunCompleted = vi.fn()
    runRequirementsAgent.mockResolvedValue({
      data: {
        run_id: 'RUN-001',
        status: 'COMPLETED',
        outputs: {
          FUNCTIONAL_REQUIREMENTS: [
            { id: 'FR-001', statement: 'The system shall search.', source_refs: ['TEXT-001'] },
          ],
        },
        warnings: [],
        errors: [],
      },
    })
    render(<RequirementsWorkspace project={project} onRunCompleted={onRunCompleted} />)

    await user.type(screen.getByLabelText(/requirement text/i), 'Users need catalogue search.')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: /^functional requirements$/i }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))

    expect(runRequirementsAgent).toHaveBeenCalledWith('AGP-001', {
      text: 'Users need catalogue search.',
      selected_outputs: ['FUNCTIONAL_REQUIREMENTS'],
    })
    expect(await screen.findByRole('heading', { name: 'Requirements results' })).toBeInTheDocument()
    expect(screen.getByText(/The system shall search/)).toBeInTheDocument()
    expect(screen.queryByText('SRS')).not.toBeInTheDocument()
    expect(onRunCompleted).toHaveBeenCalledWith(expect.objectContaining({ run_id: 'RUN-001' }))
  })

  it('requires text and at least one output before advancing', async () => {
    const user = userEvent.setup()
    render(<RequirementsWorkspace project={project} />)
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByText('Enter at least one text requirement source.')).toBeInTheDocument()
    await user.type(screen.getByLabelText(/requirement text/i), 'A requirement')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Select at least one output')
    expect(runRequirementsAgent).not.toHaveBeenCalled()
  })

  it('shows persisted structured failure feedback and reports the failed run', async () => {
    const user = userEvent.setup()
    const onRunCompleted = vi.fn()
    runRequirementsAgent.mockResolvedValue({
      data: {
        run_id: 'RUN-002', status: 'FAILED', outputs: {}, warnings: [],
        errors: [{ code: 'MODEL_EXECUTION_FAILED', message: 'The configured model provider could not generate the requested outputs' }],
      },
    })
    render(<RequirementsWorkspace project={project} onRunCompleted={onRunCompleted} />)
    await user.type(screen.getByLabelText(/requirement text/i), 'A requirement')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'SRS' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))

    expect(await screen.findByRole('heading', { name: 'Requirements run failed' })).toBeInTheDocument()
    expect(screen.getByText(/MODEL_EXECUTION_FAILED/)).toBeInTheDocument()
    expect(screen.getByText(/did not produce a validated output artifact/i)).toBeInTheDocument()
    expect(onRunCompleted).toHaveBeenCalledWith(expect.objectContaining({ run_id: 'RUN-002', status: 'FAILED' }))
  })
})
