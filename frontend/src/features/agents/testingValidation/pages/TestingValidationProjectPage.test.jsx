import { forwardRef, useImperativeHandle } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  confirmTestGenerationSetup,
  getTestGenerationWorkflow,
  listTestingValidationSources,
  runTestingValidationAgent,
} from '../testingValidationAgentService.js'
import TestingValidationProjectPage from './TestingValidationProjectPage.jsx'

const canvasActions = vi.hoisted(() => ({
  autoArrange: vi.fn(), resetLayout: vi.fn(), focusNode: vi.fn(),
}))
const canvasNodes = vi.hoisted(() => ([
  ['INPUT_OUTPUT_SETUP', 'Input & Output Setup'],
  ['INPUT_PREPARATION', 'Input Preparation'],
  ['TESTING_INTELLIGENCE', 'Testing Intelligence'],
  ['CONTEXT_TESTABILITY', 'Context & Testability'],
  ['TEST_PLANNING_REVIEW', 'Test Planning & Human Review'],
  ['TEST_GENERATION_RESULTS', 'Test Generation & Results'],
]))
const workflow = {
  schema_version: '1',
  workflow_version: 'W1',
  agent_project_id: 'AGP-404',
  agent_stage: 'TEST_GENERATION',
  pipeline_status: 'WAITING_FOR_HUMAN',
  current_node_id: 'INPUT_OUTPUT_SETUP',
  selected_outputs: [],
  selection_revision: 0,
  selection_updated_at: null,
  n1_confirmation: null,
  nodes: canvasNodes.map(([nodeId], index) => ({
    node_id: nodeId,
    status: index === 0 ? 'WAITING_FOR_HUMAN' : 'LOCKED',
    updated_at: '2026-10-21T00:00:00Z',
  })),
  created_at: '2026-10-21T00:00:00Z',
  updated_at: '2026-10-21T00:00:00Z',
}

vi.mock('../testingValidationAgentService.js', () => ({
  confirmTestGenerationSetup: vi.fn(),
  createTestingValidationTextSource: vi.fn(),
  deleteTestingValidationSource: vi.fn(),
  getTestGenerationWorkflow: vi.fn(),
  listTestingValidationSources: vi.fn(),
  runTestingValidationAgent: vi.fn(),
  updateTestGenerationOutputs: vi.fn(),
  uploadTestingValidationSource: vi.fn(),
}))

vi.mock('../canvas/TestingValidationCanvas.jsx', () => ({
  default: forwardRef(function MockTestingValidationCanvas(
    { onSelectNode, presentation, selectedNodeId },
    ref,
  ) {
    useImperativeHandle(ref, () => canvasActions)
    return (
      <div aria-label="Agent 4 test generation workflow canvas" data-selected-node={selectedNodeId ?? ''}>
        {canvasNodes.map(([id, title]) => (
          <button key={id} type="button" onClick={() => onSelectNode(id)}>
            Open {title}
            <span>{presentation[id].statusLabel ?? presentation[id].status}</span>
          </button>
        ))}
      </div>
    )
  }),
}))

const project = {
  agent_project_id: 'AGP-404', agent_type: 'TESTING_VALIDATION',
  agent_stage: 'TEST_GENERATION', name: 'Quality Gate', status: 'ACTIVE',
}
const projectStatus = { label: 'Active', tone: 'success' }

function renderPage(entryMode = 'existing') {
  return render(
    <TestingValidationProjectPage
      project={project}
      projectStatus={projectStatus}
      projectActions={<button type="button">Archive Project</button>}
      entryMode={entryMode}
    />,
  )
}

describe('TestingValidationProjectPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTestGenerationWorkflow.mockResolvedValue({ data: workflow })
    listTestingValidationSources.mockResolvedValue({ data: [] })
  })

  it('loads the authoritative workflow and renders its six node states', async () => {
    renderPage()

    expect(screen.getByText('Loading Test Generation workflow')).toBeInTheDocument()
    expect(await screen.findByLabelText('Agent 4 test generation workflow canvas')).toHaveAttribute(
      'data-selected-node', 'INPUT_OUTPUT_SETUP',
    )
    expect(getTestGenerationWorkflow).toHaveBeenCalledWith('AGP-404')
    expect(screen.getAllByRole('button', { name: /Open / })).toHaveLength(6)
    expect(screen.getAllByText('Available - Waiting for Setup')).toHaveLength(1)
    expect(screen.getAllByText('LOCKED')).toHaveLength(5)
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
    expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['Input & Output Setup', /Sources and desired outputs remain editable draft setup/],
    ['Input Preparation', /No extraction, normalization, or chunking/],
    ['Testing Intelligence', /performs no model inference/],
    ['Context & Testability', /performs no traceability, readiness, or feasibility/],
    ['Test Planning & Human Review', /Mandatory Human Approval Gate/],
    ['Test Generation & Results', /NOT_EXECUTED/],
  ])('opens the %s shell panel without processing', async (title, expectedContent) => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByLabelText('Agent 4 test generation workflow canvas')

    await user.click(screen.getByRole('button', { name: new RegExp(`Open ${title}`) }))
    expect(screen.getByRole('dialog', { name: title })).toHaveTextContent(expectedContent)
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('opens N1 after a newly created project loads and exposes only layout controls', async () => {
    const user = userEvent.setup()
    renderPage('created')

    expect(await screen.findByRole('dialog', { name: 'Input & Output Setup' })).toBeInTheDocument()
    await waitFor(() => expect(canvasActions.focusNode).toHaveBeenCalledWith('INPUT_OUTPUT_SETUP'))
    await user.click(screen.getByRole('button', { name: 'Auto Arrange' }))
    await user.click(screen.getByRole('button', { name: 'Reset Layout' }))
    expect(canvasActions.autoArrange).toHaveBeenCalledOnce()
    expect(canvasActions.resetLayout).toHaveBeenCalledOnce()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('shows a project workflow error and retries explicitly without fake state', async () => {
    const user = userEvent.setup()
    getTestGenerationWorkflow
      .mockRejectedValueOnce({ status: 503, errors: [{ message: 'Workflow temporarily unavailable' }] })
      .mockResolvedValueOnce({ data: workflow })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Workflow temporarily unavailable')
    expect(screen.queryByLabelText('Agent 4 test generation workflow canvas')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByLabelText('Agent 4 test generation workflow canvas')).toBeInTheDocument()
    expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(2)
  })

  it('keeps backend current-node emphasis after closing a manually selected panel', async () => {
    const user = userEvent.setup()
    renderPage()
    const canvas = await screen.findByLabelText('Agent 4 test generation workflow canvas')
    await user.click(screen.getByRole('button', { name: /Open Input Preparation/ }))
    expect(canvas).toHaveAttribute('data-selected-node', 'INPUT_PREPARATION')
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(canvas).toHaveAttribute('data-selected-node', 'INPUT_OUTPUT_SETUP')
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('confirms N1, moves current emphasis to Not Started N2, and starts no processing', async () => {
    const user = userEvent.setup()
    const prepared = {
      ...workflow,
      selected_outputs: ['UNIT_TEST_CASES'],
      selection_revision: 1,
      selection_updated_at: '2026-10-21T01:00:00Z',
    }
    const confirmation = {
      confirmation_id: `A4N1C-${'a'.repeat(32)}`,
      source_set_digest: 'b'.repeat(64),
      selection_digest: 'c'.repeat(64),
      selection_revision: 1,
      source_ids: [`A4SRC-${'d'.repeat(32)}`],
      selected_outputs: ['UNIT_TEST_CASES'],
      source_count: 1,
      selected_output_count: 1,
      confirmed_at: '2026-10-21T02:00:00Z',
    }
    const confirmed = {
      ...prepared,
      pipeline_status: 'RUNNING',
      current_node_id: 'INPUT_PREPARATION',
      n1_confirmation: confirmation,
      nodes: canvasNodes.map(([nodeId], index) => ({
        node_id: nodeId,
        status: index === 0 ? 'COMPLETED' : index === 1 ? 'NOT_STARTED' : 'LOCKED',
        updated_at: '2026-10-21T02:00:00Z',
      })),
    }
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: prepared })
    listTestingValidationSources.mockResolvedValue({ data: [{
      source_id: confirmation.source_ids[0],
      artifact_type: 'FUNCTIONAL_REQUIREMENTS',
      source_type: 'TEXT',
      normally_supplied_by: 'AGENT_1',
      supplied_via: 'STANDALONE_MANUAL_INPUT',
      collection_status: 'READY',
      text_content: 'Customers can transfer funds.',
      created_at: '2026-10-21T00:00:00Z',
    }] })
    confirmTestGenerationSetup.mockResolvedValueOnce({ data: confirmed })
    renderPage()
    await screen.findByLabelText('Agent 4 test generation workflow canvas')
    await user.click(screen.getByRole('button', { name: /Open Input & Output Setup/ }))
    await screen.findByText('✓ Primary functional artifact present')

    await user.click(screen.getByRole('button', { name: 'Confirm Inputs & Outputs' }))

    expect(confirmTestGenerationSetup).toHaveBeenCalledWith('AGP-404')
    expect(await screen.findByRole('dialog', { name: 'Input Preparation' })).toHaveTextContent(
      'Input Preparation is the next workflow node',
    )
    expect(screen.getByLabelText('Agent 4 test generation workflow canvas')).toHaveAttribute(
      'data-selected-node', 'INPUT_PREPARATION',
    )
    expect(screen.getAllByText('COMPLETE')).toHaveLength(1)
    expect(screen.getAllByText('NOT_STARTED')).toHaveLength(1)
    expect(screen.getAllByText('LOCKED')).toHaveLength(4)
    expect(screen.queryByRole('button', { name: /Start|Run|Extract/ })).not.toBeInTheDocument()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /Open Input & Output Setup/ }))
    expect(await screen.findByText('Setup Confirmed')).toBeInTheDocument()
  })
})
