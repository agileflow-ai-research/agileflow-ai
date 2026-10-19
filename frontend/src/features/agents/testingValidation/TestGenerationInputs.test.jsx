import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createTestGenerationTextInput,
  deleteTestGenerationInput,
  listTestGenerationInputs,
  runTestingValidationAgent,
  uploadTestGenerationInputFile,
} from './services/testingValidationAgentService.js'
import TestingValidationWorkspace from './TestingValidationWorkspace.jsx'

vi.mock('./services/testingValidationAgentService.js', () => ({
  runTestingValidationAgent: vi.fn(),
  listTestGenerationInputs: vi.fn(),
  createTestGenerationTextInput: vi.fn(),
  uploadTestGenerationInputFile: vi.fn(),
  deleteTestGenerationInput: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-004', agent_type: 'TESTING_VALIDATION',
  name: 'Quality Gate', domain: 'Fintech',
}

let nextNumber = 1
function nextId(prefix) {
  return `${prefix}-${String(nextNumber++).padStart(32, '0')}`
}

function source(overrides = {}) {
  return {
    source_id: nextId('LOCAL'), agent_project_id: 'AGP-004', run_mode: 'TEST_GENERATION',
    artifact_type: 'ACCEPTANCE_CRITERIA', source_type: 'TEXT', normally_supplied_by: 'AGENT_1',
    supplied_via: 'STANDALONE_MANUAL_INPUT', label: null, processing_status: 'COLLECTED',
    text_content: 'Refund within 14 days', original_filename: null, mime_type: null,
    size_bytes: null, sha256: null, created_at: '2026-10-19T00:00:00Z', ...overrides,
  }
}

async function openInputs(user) {
  render(<TestingValidationWorkspace project={project} />)
  await user.click(screen.getByRole('button', { name: /^Test Case Generation/ }))
  return screen.findByRole('button', { name: 'Add Source' })
}

async function chooseArtifact(user, value) {
  await user.selectOptions(screen.getByLabelText(/^Artifact type/), value)
}

describe('TEST_GENERATION input collection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTestGenerationInputs.mockResolvedValue({ data: [] })
    createTestGenerationTextInput.mockImplementation(async (_projectId, payload) => ({
      data: source({
        artifact_type: payload.artifact_type,
        normally_supplied_by: payload.origin_agent ?? (payload.artifact_type.startsWith('API') ? 'AGENT_2' : 'AGENT_1'),
        label: payload.label ?? null,
        text_content: payload.content,
      }),
    }))
    uploadTestGenerationInputFile.mockImplementation(async (_projectId, payload) => ({
      data: source({
        artifact_type: payload.artifact_type,
        source_type: payload.source_type,
        normally_supplied_by: 'AGENT_2',
        processing_status: payload.source_type === 'IMAGE' ? 'PENDING_ANALYSIS' : 'UPLOADED',
        text_content: null,
        original_filename: payload.file.name,
        mime_type: 'image/png',
        size_bytes: payload.file.size,
        sha256: 'a'.repeat(64),
      }),
    }))
    deleteTestGenerationInput.mockResolvedValue({ data: {} })
  })

  it('shows the Agent 1 and Agent 2 artifact groups and the canonical types', async () => {
    const user = userEvent.setup()
    await openInputs(user)

    expect(screen.getByRole('option', { name: /Requirements & Quality Artifacts/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Design & Technical Artifacts/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Acceptance Criteria' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Software Requirements Specification (SRS)' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Product Backlog|Sprint Plan|Epics/i })).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText(/^Artifact group/), 'DESIGN_AND_TECHNICAL')
    expect(screen.getByRole('option', { name: 'API Specification' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Wireframes' })).toBeInTheDocument()
  })

  it('offers TEXT, DOCUMENT, and IMAGE source types', async () => {
    const user = userEvent.setup()
    await openInputs(user)

    const sourceType = screen.getByLabelText(/^Source type/)
    expect(within(sourceType).getByRole('option', { name: 'Text' })).toBeInTheDocument()
    expect(within(sourceType).getByRole('option', { name: 'Document' })).toBeInTheDocument()
    expect(within(sourceType).getByRole('option', { name: 'Image' })).toBeInTheDocument()
  })

  it('adds a TEXT source, shows its card, and sends no run or plan request', async () => {
    const user = userEvent.setup()
    await openInputs(user)

    await chooseArtifact(user, 'ACCEPTANCE_CRITERIA')
    await user.type(screen.getByLabelText(/^Content/), 'Refund within 14 days')
    await user.click(screen.getByRole('button', { name: 'Add Source' }))

    await waitFor(() => expect(createTestGenerationTextInput).toHaveBeenCalledWith('AGP-004', {
      artifact_type: 'ACCEPTANCE_CRITERIA',
      content: 'Refund within 14 days',
    }))
    const card = await screen.findByRole('article', { name: 'Acceptance Criteria Text source' })
    expect(within(card).getByText('Refund within 14 days')).toBeInTheDocument()
    expect(within(card).getByText(/Normally supplied by Agent 1/)).toBeInTheDocument()
    expect(within(card).getByText('Collected')).toBeInTheDocument()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /plan|generate/i })).not.toBeInTheDocument()
  })

  it('keeps several sources, including several of the same artifact type, as separate cards', async () => {
    const user = userEvent.setup()
    await openInputs(user)

    for (const text of ['Checkout AC', 'Refund AC']) {
      await chooseArtifact(user, 'ACCEPTANCE_CRITERIA')
      await user.type(screen.getByLabelText(/^Content/), text)
      await user.click(screen.getByRole('button', { name: 'Add Source' }))
      await screen.findByText(text)
    }

    const cards = screen.getAllByRole('article', { name: 'Acceptance Criteria Text source' })
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByText('Checkout AC')).toBeInTheDocument()
    expect(within(cards[1]).getByText('Refund AC')).toBeInTheDocument()
    expect(screen.getByText('2 of 100 sources collected')).toBeInTheDocument()
  })

  it('removes a source through the service and drops its card', async () => {
    const user = userEvent.setup()
    listTestGenerationInputs.mockResolvedValue({ data: [source({ text_content: 'Remove me' })] })
    await openInputs(user)

    await screen.findByText('Remove me')
    await user.click(screen.getByRole('button', { name: 'Remove Acceptance Criteria text source 1' }))

    await waitFor(() => expect(deleteTestGenerationInput).toHaveBeenCalledWith('AGP-004', expect.stringMatching(/^LOCAL-/)))
    await waitFor(() => expect(screen.queryByText('Remove me')).not.toBeInTheDocument())
  })

  it('adds an IMAGE source as PENDING_ANALYSIS without showing any understanding', async () => {
    const user = userEvent.setup()
    await openInputs(user)

    await user.selectOptions(screen.getByLabelText(/^Artifact group/), 'DESIGN_AND_TECHNICAL')
    await chooseArtifact(user, 'WIREFRAMES')
    await user.selectOptions(screen.getByLabelText(/^Source type/), 'IMAGE')
    const fileInput = screen.getByLabelText(/^File/)
    expect(fileInput).toHaveAttribute('accept', '.png,.jpg,.jpeg,.webp')
    await user.upload(fileInput, new File(['png'], 'checkout-wireframe.png', { type: 'image/png' }))
    await user.click(screen.getByRole('button', { name: 'Add Source' }))

    const card = await screen.findByRole('article', { name: 'Wireframes Image source' })
    expect(within(card).getByText('Pending analysis')).toBeInTheDocument()
    expect(within(card).getByText(/not treated as understood context/)).toBeInTheDocument()
    expect(within(card).getByText(/checkout-wireframe\.png/)).toBeInTheDocument()
    expect(uploadTestGenerationInputFile).toHaveBeenCalledWith('AGP-004', expect.objectContaining({
      artifact_type: 'WIREFRAMES', source_type: 'IMAGE',
    }))
    expect(within(card).queryByRole('button', { name: /Extract/ })).not.toBeInTheDocument()
    expect(within(card).queryByText(/Chunk|Classification|Rule-based|Extracted/i)).not.toBeInTheDocument()
  })

  it('rejects blank text and missing USER_STORIES origin before calling the service', async () => {
    const user = userEvent.setup()
    await openInputs(user)

    await chooseArtifact(user, 'ACCEPTANCE_CRITERIA')
    await user.type(screen.getByLabelText(/^Content/), '   ')
    await user.click(screen.getByRole('button', { name: 'Add Source' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter the text content.')

    await chooseArtifact(user, 'USER_STORIES')
    expect(await screen.findByLabelText(/^Normally supplied by/)).toBeInTheDocument()
    await user.type(screen.getByLabelText(/^Content/), 'As a customer I want refunds')
    await user.click(screen.getByRole('button', { name: 'Add Source' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Agent 1 or Agent 2/)
    expect(createTestGenerationTextInput).not.toHaveBeenCalled()
  })

  it('shows the user-stories origin from the chosen upstream agent', async () => {
    const user = userEvent.setup()
    await openInputs(user)

    await chooseArtifact(user, 'USER_STORIES')
    await user.selectOptions(screen.getByLabelText(/^Normally supplied by/), 'AGENT_2')
    await user.type(screen.getByLabelText(/^Content/), 'As a customer I want refunds')
    await user.click(screen.getByRole('button', { name: 'Add Source' }))

    await waitFor(() => expect(createTestGenerationTextInput).toHaveBeenCalledWith('AGP-004', expect.objectContaining({
      artifact_type: 'USER_STORIES', origin_agent: 'AGENT_2',
    })))
    expect(await screen.findByRole('article', { name: 'User Stories Text source' })).toHaveTextContent('Normally supplied by Agent 2')
  })

  it('shows existing server-side sources when the Inputs stage opens again', async () => {
    const user = userEvent.setup()
    listTestGenerationInputs.mockResolvedValue({ data: [source({ text_content: 'Persisted AC' })] })
    await openInputs(user)

    expect(await screen.findByText('Persisted AC')).toBeInTheDocument()
    expect(listTestGenerationInputs).toHaveBeenCalledWith('AGP-004')
  })

  it('does not expose inputs in VALIDATION and does not touch TEST_GENERATION sources there', async () => {
    const user = userEvent.setup()
    listTestGenerationInputs.mockResolvedValue({ data: [source({ text_content: 'Kept AC' })] })
    render(<TestingValidationWorkspace project={project} />)

    await user.click(screen.getByRole('button', { name: /^Testing & Validation/ }))

    expect(screen.queryByRole('button', { name: 'Add Source' })).not.toBeInTheDocument()
    expect(screen.queryByText('Kept AC')).not.toBeInTheDocument()
    expect(listTestGenerationInputs).not.toHaveBeenCalled()
    expect(deleteTestGenerationInput).not.toHaveBeenCalled()
  })
})
