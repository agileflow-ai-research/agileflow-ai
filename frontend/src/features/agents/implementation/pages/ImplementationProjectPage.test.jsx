import { forwardRef, useImperativeHandle } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const canvasActions = vi.hoisted(() => ({ autoArrange: vi.fn(), resetLayout: vi.fn() }))

vi.mock('../canvas/ImplementationCanvas.jsx', () => ({
  default: forwardRef(function TestCanvas({ onSelectNode }, ref) {
    useImperativeHandle(ref, () => canvasActions)
    return (
      <div aria-label="Agent 3 implementation workflow canvas">
        <button type="button" onClick={() => onSelectNode('PROJECT_SOURCES')}>Select sources</button>
        <button type="button" onClick={() => onSelectNode('IMPLEMENTATION_READINESS')}>Select readiness</button>
        <button type="button" onClick={() => onSelectNode('DELIVERY_SETUP')}>Select delivery setup</button>
        <button type="button" onClick={() => onSelectNode('GENERATE_IMPLEMENTATION')}>Select locked stage</button>
      </div>
    )
  }),
}))

vi.mock('../ImplementationWorkspace.jsx', () => ({
  default: ({ activeSection }) => <div data-testid="implementation-workspace">Workspace section: {activeSection}</div>,
}))

import ImplementationProjectPage from './ImplementationProjectPage.jsx'

const project = { agent_project_id: 'AGP-003', name: 'Delivery Portal', status: 'ACTIVE' }
const projectStatus = { label: 'Active', tone: 'success' }

describe('ImplementationProjectPage', () => {
  it('opens active node details, closes them, and exposes the existing workspace by section', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)

    await user.click(screen.getByRole('button', { name: 'Select sources' }))
    expect(screen.getByRole('heading', { name: 'Project & Sources' })).toBeInTheDocument()
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('PROJECT_SOURCES')

    await user.click(screen.getByRole('button', { name: 'Close workflow details' }))
    expect(screen.getByLabelText('Workflow node details')).toHaveClass('hidden')

    await user.click(screen.getByRole('button', { name: 'Select readiness' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('IMPLEMENTATION_READINESS')
    await user.click(screen.getByRole('button', { name: 'Select delivery setup' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('DELIVERY_SETUP')
  })

  it('marks future stages as locked without exposing workspace functionality', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)

    await user.click(screen.getByRole('button', { name: 'Select locked stage' }))
    expect(screen.getByRole('heading', { name: 'Generate Implementation' })).toBeInTheDocument()
    expect(screen.getAllByText('Locked').length).toBeGreaterThan(0)
    expect(screen.getByText('Not implemented yet')).toBeInTheDocument()
    expect(screen.getByTestId('implementation-workspace').parentElement).toHaveClass('hidden')
  })

  it('wires accessible layout controls to the canvas without workflow calls', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)

    await user.click(screen.getByRole('button', { name: 'Auto Arrange' }))
    await user.click(screen.getByRole('button', { name: 'Reset Layout' }))
    expect(canvasActions.autoArrange).toHaveBeenCalledOnce()
    expect(canvasActions.resetLayout).toHaveBeenCalledOnce()
  })
})
