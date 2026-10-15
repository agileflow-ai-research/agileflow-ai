import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ImplementationWorkspace from './ImplementationWorkspace.jsx'

const project = {
  agent_project_id: 'AGP-003',
  agent_type: 'IMPLEMENTATION',
  name: 'BookEase Builder',
  domain: 'Hospitality',
}

const outputLabels = [
  'Project Structure',
  'Frontend Code',
  'Backend Code',
  'Database Implementation',
  'API Implementation',
  'Configuration Files',
  'Container Configuration',
  'Git Summary',
]

describe('ImplementationWorkspace', () => {
  it('manages multiple TEXT inputs and reviews existing project context without execution', async () => {
    const user = userEvent.setup()
    const executionSpy = vi.fn()
    render(<ImplementationWorkspace project={project} onRunCompleted={executionSpy} />)

    expect(screen.getByRole('heading', { name: 'Implementation Inputs' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Connect GitHub' })).toBeDisabled()
    expect(screen.getByText(/GitHub account connection will be enabled/i)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText(/Artifact Type/), 'API_SPECIFICATION')
    await user.type(screen.getByLabelText(/Content/), '  POST /bookings creates a booking.  ')
    await user.type(screen.getByLabelText('Label (optional)'), 'Booking API')
    await user.click(screen.getByRole('button', { name: 'Add Input' }))

    const contentFields = screen.getAllByLabelText(/Content/)
    expect(contentFields).toHaveLength(2)
    await user.selectOptions(screen.getAllByLabelText(/Artifact Type/)[1], 'UI_WIREFRAMES')
    await user.type(contentFields[1], 'Booking form with guest and date fields.')
    await user.click(screen.getAllByRole('button', { name: 'Remove Input' })[1])
    expect(screen.getAllByLabelText(/Content/)).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Add Input' }))
    await user.selectOptions(screen.getAllByLabelText(/Artifact Type/)[1], 'TECHNOLOGY_STACK')
    await user.type(screen.getAllByLabelText(/Content/)[1], 'React and FastAPI')
    await user.click(screen.getByRole('button', { name: 'Next' }))

    outputLabels.forEach((label) => {
      expect(screen.getByRole('checkbox', { name: label })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('checkbox', { name: 'Project Structure' }))
    await user.click(screen.getByRole('checkbox', { name: 'Backend Code' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))

    expect(screen.getByText('BookEase Builder')).toBeInTheDocument()
    expect(screen.getByText('Hospitality')).toBeInTheDocument()
    expect(screen.getByText(/Booking API: API Specification/)).toBeInTheDocument()
    expect(screen.getByText('POST /bookings creates a booking.')).toBeInTheDocument()
    expect(screen.getByText(/Input 2: Technology Stack/)).toBeInTheDocument()
    expect(screen.getByText(/Not connected — integration is not available/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Workspace Ready' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
    expect(executionSpy).not.toHaveBeenCalled()
  })

  it('validates empty inputs and requires at least one output', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter content for every implementation input.')

    await user.type(screen.getByLabelText(/Content/), 'A usable requirement')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Select at least one output.')
  })

  it('shows DOCUMENT and IMAGE as disabled future source formats', () => {
    render(<ImplementationWorkspace project={project} />)

    const source = screen.getByLabelText(/Input Source/)
    expect(source).toHaveValue('TEXT')
    expect(within(source).getByRole('option', { name: 'Document — coming next' })).toBeDisabled()
    expect(within(source).getByRole('option', { name: 'Image — coming next' })).toBeDisabled()
    expect(screen.getByText(/File upload support will be added in the next implementation step/i)).toBeInTheDocument()
  })

  it('allows every input to be removed and reports that an input is required', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)

    await user.click(screen.getByRole('button', { name: 'Remove Input' }))
    expect(screen.queryByLabelText(/Content/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Add at least one implementation input.')
  })
})
