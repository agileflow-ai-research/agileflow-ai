import { forwardRef, useImperativeHandle } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runTestingValidationAgent } from '../testingValidationAgentService.js'
import TestingValidationProjectPage from './TestingValidationProjectPage.jsx'

const canvasActions = vi.hoisted(() => ({
  autoArrange: vi.fn(),
  resetLayout: vi.fn(),
  focusNode: vi.fn(),
}))
const canvasNodes = vi.hoisted(() => ([
  ['INPUT_OUTPUT_SETUP', 'Input & Output Setup'],
  ['INPUT_PREPARATION', 'Input Preparation'],
  ['TESTING_INTELLIGENCE', 'Testing Intelligence'],
  ['CONTEXT_TESTABILITY', 'Context & Testability'],
  ['TEST_PLANNING_REVIEW', 'Test Planning & Human Review'],
  ['TEST_GENERATION_RESULTS', 'Test Generation & Results'],
]))

vi.mock('../testingValidationAgentService.js', () => ({
  runTestingValidationAgent: vi.fn(),
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
            <span>{presentation[id].statusLabel}</span>
          </button>
        ))}
      </div>
    )
  }),
}))

const project = {
  agent_project_id: 'AGP-404',
  agent_type: 'TESTING_VALIDATION',
  agent_stage: 'TEST_GENERATION',
  name: 'Quality Gate',
  status: 'ACTIVE',
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
  beforeEach(() => vi.clearAllMocks())

  it('renders the six-node Stage 1 canvas with only N1 available', () => {
    renderPage()

    expect(screen.getByLabelText('Agent 4 test generation workflow canvas')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Open / })).toHaveLength(6)
    expect(screen.getAllByText('Available · Current')).toHaveLength(1)
    expect(screen.getAllByText('Locked · Not Available Yet')).toHaveLength(5)
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/upload/i)).not.toBeInTheDocument()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it.each([
    ['Input & Output Setup', /Input and output setup will be implemented next/],
    ['Input Preparation', /No extraction, normalization, or chunking/],
    ['Testing Intelligence', /performs no model inference/],
    ['Context & Testability', /performs no traceability, readiness, or feasibility/],
    ['Test Planning & Human Review', /Mandatory Human Approval Gate/],
    ['Test Generation & Results', /NOT_EXECUTED/],
  ])('opens the %s shell panel without processing', async (title, expectedContent) => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: new RegExp(`Open ${title}`) }))
    const dialog = screen.getByRole('dialog', { name: title })
    expect(dialog).toHaveTextContent(expectedContent)
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('opens N1 for a newly created project and exposes only layout controls', async () => {
    const user = userEvent.setup()
    renderPage('created')

    expect(screen.getByRole('dialog', { name: 'Input & Output Setup' })).toBeInTheDocument()
    expect(canvasActions.focusNode).toHaveBeenCalledWith('INPUT_OUTPUT_SETUP')
    await user.click(screen.getByRole('button', { name: 'Auto Arrange' }))
    await user.click(screen.getByRole('button', { name: 'Reset Layout' }))
    expect(canvasActions.autoArrange).toHaveBeenCalledOnce()
    expect(canvasActions.resetLayout).toHaveBeenCalledOnce()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('closes a selected node normally and keeps processing unavailable', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: /Open Input Preparation/ }))
    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Agent 4 test generation workflow canvas')).toHaveAttribute('data-selected-node', '')
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })
})
