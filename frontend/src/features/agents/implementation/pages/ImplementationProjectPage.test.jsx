import { forwardRef, useImperativeHandle } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const canvasActions = vi.hoisted(() => ({ autoArrange: vi.fn(), resetLayout: vi.fn(), focusNode: vi.fn() }))

vi.mock('../canvas/ImplementationCanvas.jsx', () => ({
  default: forwardRef(function TestCanvas({ onSelectNode }, ref) {
    useImperativeHandle(ref, () => canvasActions)
    return (
      <div aria-label="Agent 3 implementation workflow canvas">
        <button type="button" onClick={() => onSelectNode('PROJECT_SOURCES')}>Select sources</button>
        <button type="button" onClick={() => onSelectNode('SPECIFICATION_VERIFICATION')}>Select specification</button>
        <button type="button" onClick={() => onSelectNode('IMPLEMENTATION_READINESS')}>Select readiness</button>
        <button type="button" onClick={() => onSelectNode('DELIVERY_SETUP')}>Select delivery setup</button>
        <button type="button" onClick={() => onSelectNode('GENERATE_IMPLEMENTATION')}>Select final approval</button>
        <button type="button" onClick={() => onSelectNode('BUILD_EXECUTE')}>Select locked stage</button>
      </div>
    )
  }),
}))

vi.mock('../ImplementationWorkspace.jsx', () => ({
  default: ({ activeSection, initialArtifactReviewQueue, onPresentationChange }) => (
    <div data-testid="implementation-workspace">
      Workspace section: {activeSection}
      <span>Review queue size: {initialArtifactReviewQueue.length}</span>
      <button
        type="button"
        onClick={() => onPresentationChange({
          preparationState: { result: { status: 'WAITING_FOR_HUMAN' } },
          artifactReviewQueue: [{ source_id: 'UP-1', status: 'WAITING_FOR_HUMAN' }],
        })}
      >
        Emit review transition
      </button>
    </div>
  ),
}))

import ImplementationProjectPage from './ImplementationProjectPage.jsx'

const project = { agent_project_id: 'AGP-003', name: 'Delivery Portal', status: 'ACTIVE' }
const projectStatus = { label: 'Active', tone: 'success' }

describe('ImplementationProjectPage', () => {
  it('opens Project & Sources immediately and focuses the first workflow step', () => {
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)

    expect(screen.getByRole('heading', { name: 'Project & Sources' })).toBeInTheDocument()
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('PROJECT_SOURCES')
    expect(canvasActions.focusNode).toHaveBeenCalledWith('PROJECT_SOURCES')
  })

  it('opens active node details, closes them, and exposes the existing workspace by section', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)

    await user.click(screen.getByRole('button', { name: 'Select sources' }))
    expect(screen.getByRole('heading', { name: 'Project & Sources' })).toBeInTheDocument()
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('PROJECT_SOURCES')

    expect(screen.getByRole('dialog', { name: 'Project & Sources' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Select readiness' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('IMPLEMENTATION_READINESS')
    await user.click(screen.getByRole('button', { name: 'Select delivery setup' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('DELIVERY_SETUP')
  })

  it('uses an accessible internally scrolling modal and closes safely with Escape', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    const canvas = screen.getByLabelText('Agent 3 implementation workflow canvas')

    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByTestId('workflow-modal-body')).toHaveClass('overflow-y-auto')
    expect(screen.getByTestId('workflow-modal-header')).toHaveClass('sticky', 'top-0')
    expect(screen.getByTestId('workflow-modal-footer')).toHaveClass('sticky', 'bottom-0')
    expect(screen.queryByLabelText('Workflow node details')).not.toBeInTheDocument()
    expect(screen.getByTestId('workflow-modal-backdrop')).toHaveClass('fixed', 'inset-0')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Agent 3 implementation workflow canvas')).toBe(canvas)
  })

  it('opens final approval while keeping actual execution stages locked', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)

    await user.click(screen.getByRole('button', { name: 'Select final approval' }))
    expect(screen.getByRole('heading', { name: 'Generate Implementation' })).toBeInTheDocument()
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('GENERATE_IMPLEMENTATION')
    expect(screen.queryByText('Not implemented yet')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Select locked stage' }))
    expect(screen.getByRole('heading', { name: 'Build & Execute' })).toBeInTheDocument()
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

  it('auto-selects a human review transition once without stealing focus on repeated state', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    canvasActions.focusNode.mockClear()

    await user.click(screen.getByRole('button', { name: 'Emit review transition' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('SPECIFICATION_VERIFICATION')
    expect(canvasActions.focusNode).toHaveBeenCalledTimes(1)
    expect(canvasActions.focusNode).toHaveBeenCalledWith('SPECIFICATION_VERIFICATION')

    await user.click(screen.getByRole('button', { name: 'Select sources' }))
    await user.click(screen.getByRole('button', { name: 'Emit review transition' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('PROJECT_SOURCES')
    expect(canvasActions.focusNode).toHaveBeenCalledTimes(1)
  })

  it('preserves the review queue when the modal closes and reopens at the overview', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)

    await user.click(screen.getByRole('button', { name: 'Emit review transition' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('Review queue size: 1')
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Select specification' }))
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('Review queue size: 1')
    expect(screen.getByTestId('implementation-workspace')).toHaveTextContent('SPECIFICATION_VERIFICATION')
  })
})
