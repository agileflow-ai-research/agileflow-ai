import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { REQUIREMENTS_NODE_IDS } from '../workflow/nodeDefinitions.js'
import RequirementsProjectPage from './RequirementsProjectPage.jsx'

const canvasApi = {
  autoArrange: vi.fn(),
  resetLayout: vi.fn(),
  fitView: vi.fn(),
  focusNode: vi.fn(),
}

vi.mock('../canvas/RequirementsCanvas.jsx', async () => {
  const React = await import('react')
  return {
    default: React.forwardRef(function MockRequirementsCanvas({ onSelectNode, presentation, selectedNodeId }, ref) {
      React.useImperativeHandle(ref, () => canvasApi)
      return (
        <div aria-label="Agent 1 requirements workflow canvas" data-selected-node={selectedNodeId ?? ''}>
          <span data-testid="n1-status">{presentation.INPUT_COLLECTION?.status}</span>
          <span data-testid="n2-status">{presentation.PROCESSING_AND_CHUNKING?.status}</span>
          <button type="button" onClick={() => onSelectNode('INPUT_COLLECTION')}>Select N1</button>
          <button type="button" onClick={() => onSelectNode('PROCESSING_AND_CHUNKING')}>Select N2</button>
          <button type="button" onClick={() => onSelectNode('DISCOVERY_AND_STRUCTURING')}>Select N3</button>
        </div>
      )
    }),
  }
})

vi.mock('../RequirementsWorkspace.jsx', () => ({
  default: ({ activeSection, onPresentationChange }) => (
    <div data-testid="requirements-workspace" data-active-section={activeSection}>
      <button
        type="button"
        onClick={() => onPresentationChange({
          loadStatus: 'success',
          sources: [{ source_id: 'DOC-001', source_type: 'DOCUMENT' }],
          workflowState: { n1_state: 'COMPLETE', selected_outputs: ['SRS'] },
          processingStates: { 'DOC-001': { status: 'READY' } },
          preparationStates: { 'DOC-001': { status: 'READY' } },
        })}
      >
        Publish snapshot
      </button>
      <button
        type="button"
        onClick={() => onPresentationChange({
          loadStatus: 'success',
          sources: [{ source_id: 'AUD-001', source_type: 'AUDIO' }],
          workflowState: {
            n1_state: 'COMPLETE',
            n2_is_current: true,
            n2_execution: { execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'RUNNING' },
          },
          processingStates: {},
          preparationStates: {},
        })}
      >
        Publish N2 running
      </button>
      <button
        type="button"
        onClick={() => onPresentationChange({
          loadStatus: 'success',
          sources: [{ source_id: 'AUD-001', source_type: 'AUDIO' }],
          workflowState: {
            n1_state: 'COMPLETE',
            n2_is_current: true,
            n2_execution: { execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'COMPLETE' },
          },
          processingStates: { 'AUD-001': { status: 'COMPLETED' } },
          preparationStates: { 'AUD-001': { status: 'COMPLETED', chunks: { chunks: Array(7).fill({}) } } },
        })}
      >
        Publish N2 complete
      </button>
    </div>
  ),
}))

const project = { agent_project_id: 'AGP-001', name: 'BookEase' }
const projectStatus = { label: 'Active', tone: 'success' }

describe('RequirementsProjectPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the wide canvas header and opens N1 for a newly created project', () => {
    render(
      <RequirementsProjectPage
        project={project}
        projectStatus={projectStatus}
        projectActions={<button type="button">Archive Project</button>}
        entryMode="created"
      />,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'BookEase' })).toBeInTheDocument()
    expect(screen.getByText('Agent 1 — Requirements & Analysis')).toBeInTheDocument()
    expect(screen.getByLabelText('Agent 1 requirements workflow canvas')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toHaveTextContent('Project & Client Input Collection')
    expect(screen.getByTestId('requirements-workspace')).toHaveAttribute('data-active-section', REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
    expect(canvasApi.focusNode).toHaveBeenCalledWith(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
  })

  it('selects N2 and locked N3 without mutating their workflow status', async () => {
    const user = userEvent.setup()
    render(<RequirementsProjectPage project={project} projectStatus={projectStatus} entryMode="existing" />)
    await user.click(screen.getByRole('button', { name: 'Select N1' }))
    await user.click(screen.getByRole('button', { name: 'Publish snapshot' }))
    expect(screen.getByTestId('n1-status')).toHaveTextContent('COMPLETE')

    await user.click(screen.getByRole('button', { name: 'Select N2' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Multimodal Processing & Chunking')
    expect(screen.getByTestId('requirements-workspace')).toHaveAttribute('data-active-section', REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)

    await user.click(screen.getByRole('button', { name: 'Select N3' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Requirement Discovery & Structuring')
    expect(screen.getByRole('dialog')).toHaveTextContent('Locked')
    expect(screen.getByTestId('n1-status')).toHaveTextContent('COMPLETE')
  })

  it('keeps the workspace mounted across close and reopen', async () => {
    const user = userEvent.setup()
    render(<RequirementsProjectPage project={project} projectStatus={projectStatus} entryMode="existing" />)
    expect(screen.getByTestId('requirements-workspace')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Select N1' }))
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('requirements-workspace')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Select N2' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('updates the canvas and open modal from RUNNING to COMPLETE without a remount', async () => {
    const user = userEvent.setup()
    render(<RequirementsProjectPage project={project} projectStatus={projectStatus} entryMode="existing" />)
    await user.click(screen.getByRole('button', { name: 'Select N2' }))
    await user.click(screen.getByRole('button', { name: 'Publish N2 running' }))
    expect(screen.getByTestId('n2-status')).toHaveTextContent('RUNNING')
    expect(screen.getByRole('dialog')).toHaveTextContent('In Progress')

    await user.click(screen.getByRole('button', { name: 'Publish N2 complete' }))
    expect(screen.getByTestId('n2-status')).toHaveTextContent('COMPLETE')
    expect(screen.getByRole('dialog')).toHaveTextContent('Complete')
  })

  it('keeps workflow publication active while the modal is closed and reopens at COMPLETE', async () => {
    const user = userEvent.setup()
    render(<RequirementsProjectPage project={project} projectStatus={projectStatus} entryMode="existing" />)
    await user.click(screen.getByRole('button', { name: 'Select N2' }))
    await user.click(screen.getByRole('button', { name: 'Publish N2 running' }))
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))

    fireEvent.click(screen.getByRole('button', { name: 'Publish N2 complete', hidden: true }))
    expect(screen.getByTestId('n2-status')).toHaveTextContent('COMPLETE')

    await user.click(screen.getByRole('button', { name: 'Select N2' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Complete')
  })

  it('routes Auto Arrange and Reset Layout through the shared canvas ref', () => {
    render(<RequirementsProjectPage project={project} projectStatus={projectStatus} entryMode="existing" />)
    fireEvent.click(screen.getByRole('button', { name: 'Auto Arrange' }))
    fireEvent.click(screen.getByRole('button', { name: 'Reset Layout' }))
    expect(canvasApi.autoArrange).toHaveBeenCalledTimes(1)
    expect(canvasApi.resetLayout).toHaveBeenCalledTimes(1)
  })
})
