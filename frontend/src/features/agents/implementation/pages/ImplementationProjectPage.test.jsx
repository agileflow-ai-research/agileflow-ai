import { forwardRef, useImperativeHandle } from 'react'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const canvasActions = vi.hoisted(() => ({ autoArrange: vi.fn(), resetLayout: vi.fn(), focusNode: vi.fn() }))
const workspaceActions = vi.hoisted(() => ({ emit: null }))

const reviewSnapshot = {
  preparationState: { result: { status: 'WAITING_FOR_HUMAN' } },
  artifactReviewQueue: [{ source_id: 'UP-1', status: 'WAITING_FOR_HUMAN' }],
}

function readySnapshot({ readinessStatus = 'evaluating', readiness = null, continuationApproved = false, deliveryDecision = 'PENDING' } = {}) {
  return {
    preparationState: { result: { status: 'ANALYSIS_READY' } },
    specificationState: { result: { status: 'SPECIFICATION_READY' } },
    consolidationState: { result: { status: 'READY' } },
    readinessState: {
      status: readinessStatus,
      result: readiness ? { status: readiness, current: true, continuation_approved: continuationApproved } : null,
      stale: false,
    },
    repositoryState: { status: 'idle', repository: null },
    deliveryDecision,
    runState: { status: 'loaded', runs: [] },
  }
}

vi.mock('../canvas/ImplementationCanvas.jsx', () => ({
  default: forwardRef(function TestCanvas({ onSelectNode }, ref) {
    useImperativeHandle(ref, () => canvasActions)
    return (
      <div aria-label="Agent 3 implementation workflow canvas">
        <button type="button" onClick={() => onSelectNode('PROJECT_SOURCES')}>Select sources</button>
        <button type="button" onClick={() => onSelectNode('INPUT_ANALYSIS')}>Select analysis</button>
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
  default: ({ activeSection, initialArtifactReviewQueue, onPresentationChange, onNavigateNode }) => {
    workspaceActions.emit = onPresentationChange
    return (
      <div data-testid="implementation-workspace">
        Workspace section: {activeSection}
        <span>Review queue size: {initialArtifactReviewQueue.length}</span>
        <button type="button" onClick={() => onPresentationChange(reviewSnapshot)}>Emit review transition</button>
        <button type="button" onClick={() => onPresentationChange(readySnapshot())}>Emit readiness transition</button>
        <button type="button" onClick={() => onPresentationChange(readySnapshot({ readiness: 'READY_WITH_WARNINGS', readinessStatus: 'complete' }))}>Emit readiness warning</button>
        <button type="button" onClick={() => onPresentationChange(readySnapshot({ readiness: 'READY_WITH_WARNINGS', readinessStatus: 'complete', continuationApproved: true }))}>Emit readiness approval</button>
        <button type="button" onClick={() => onPresentationChange(readySnapshot({ readiness: 'READY', readinessStatus: 'complete', deliveryDecision: 'SKIPPED' }))}>Emit delivery completion</button>
        <button type="button" onClick={() => onNavigateNode('SPECIFICATION_VERIFICATION')}>Explicit specification navigation</button>
      </div>
    )
  },
}))

import ImplementationProjectPage from './ImplementationProjectPage.jsx'

const project = { agent_project_id: 'AGP-003', name: 'Delivery Portal', status: 'ACTIVE' }
const projectStatus = { label: 'Active', tone: 'success' }

describe('ImplementationProjectPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    workspaceActions.emit = null
  })

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

  it('pins a manually opened modal while a new human gate updates behind it', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    await user.click(screen.getByRole('button', { name: 'Select analysis' }))
    canvasActions.focusNode.mockClear()

    await user.click(screen.getByRole('button', { name: 'Emit review transition' }))
    expect(screen.getByRole('dialog', { name: 'Input Analysis' })).toBeInTheDocument()
    expect(screen.getByText('Specification Verification needs your attention.')).toBeInTheDocument()
    expect(canvasActions.focusNode).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Emit review transition' }))
    expect(screen.getByRole('dialog', { name: 'Input Analysis' })).toBeInTheDocument()
    expect(canvasActions.focusNode).not.toHaveBeenCalled()
  })

  it('auto-opens a new human gate once only when no modal is open', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))

    act(() => workspaceActions.emit(reviewSnapshot))
    expect(screen.getByRole('dialog', { name: 'Specification Verification' })).toBeInTheDocument()
    expect(canvasActions.focusNode).toHaveBeenLastCalledWith('SPECIFICATION_VERIFICATION')
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    act(() => workspaceActions.emit({ ...reviewSnapshot }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Select specification' }))
    expect(screen.getByRole('dialog', { name: 'Specification Verification' })).toBeInTheDocument()
  })

  it('uses next-step actions as explicit manual navigation', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    await user.click(screen.getByRole('button', { name: 'Select analysis' }))
    await user.click(screen.getByRole('button', { name: 'Emit review transition' }))

    await user.click(screen.getByRole('button', { name: 'Go to Specification Verification' }))
    expect(screen.getByRole('dialog', { name: 'Specification Verification' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Explicit specification navigation' }))
    expect(screen.getByRole('dialog', { name: 'Specification Verification' })).toBeInTheDocument()
  })

  it('keeps Specification Verification pinned while readiness progresses', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    await user.click(screen.getByRole('button', { name: 'Select specification' }))
    await user.click(screen.getByRole('button', { name: 'Emit readiness transition' }))
    expect(screen.getByRole('dialog', { name: 'Specification Verification' })).toBeInTheDocument()
    expect(screen.getByText('Implementation Readiness is continuing automatically.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Emit readiness warning' }))
    expect(screen.getByRole('dialog', { name: 'Specification Verification' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review Readiness' })).toBeInTheDocument()
  })

  it('keeps Readiness pinned when approval unlocks Delivery Setup', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    await user.click(screen.getByRole('button', { name: 'Select readiness' }))
    await user.click(screen.getByRole('button', { name: 'Emit readiness approval' }))
    expect(screen.getByRole('dialog', { name: 'Implementation Readiness' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Go to Delivery Setup' })).toBeInTheDocument()
  })

  it('keeps Delivery pinned when final approval becomes actionable', async () => {
    const user = userEvent.setup()
    render(<ImplementationProjectPage project={project} projectStatus={projectStatus} />)
    await user.click(screen.getByRole('button', { name: 'Select delivery setup' }))
    await user.click(screen.getByRole('button', { name: 'Emit delivery completion' }))
    expect(screen.getByRole('dialog', { name: 'Delivery Setup' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review Implementation Plan' })).toBeInTheDocument()
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
