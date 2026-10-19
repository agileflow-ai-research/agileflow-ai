import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  extractTestGenerationSource,
  getTestGenerationExtraction,
  listTestGenerationInputs,
  runTestingValidationAgent,
} from './services/testingValidationAgentService.js'
import TestingValidationWorkspace from './TestingValidationWorkspace.jsx'

vi.mock('./services/testingValidationAgentService.js', () => ({
  runTestingValidationAgent: vi.fn(),
  listTestGenerationInputs: vi.fn(),
  createTestGenerationTextInput: vi.fn(),
  uploadTestGenerationInputFile: vi.fn(),
  deleteTestGenerationInput: vi.fn(),
  extractTestGenerationSource: vi.fn(),
  getTestGenerationExtraction: vi.fn(),
}))

const project = { agent_project_id: 'AGP-004', agent_type: 'TESTING_VALIDATION', name: 'Quality Gate', domain: 'Fintech' }

function documentSource(number, overrides = {}) {
  return {
    source_id: `A4UP-${String(number).padStart(32, '0')}`,
    agent_project_id: 'AGP-004', run_mode: 'TEST_GENERATION',
    artifact_type: 'ACCEPTANCE_CRITERIA', source_type: 'DOCUMENT', normally_supplied_by: 'AGENT_1',
    supplied_via: 'STANDALONE_MANUAL_INPUT', label: null, processing_status: 'UPLOADED',
    text_content: null, original_filename: `booking-${number}.pdf`, mime_type: 'application/pdf',
    size_bytes: 2048, sha256: 'a'.repeat(64), extraction_status: null, created_at: '2026-10-19T00:00:00Z',
    ...overrides,
  }
}

function textSource() {
  return {
    source_id: 'LOCAL-' + '1'.repeat(32), agent_project_id: 'AGP-004', run_mode: 'TEST_GENERATION',
    artifact_type: 'ACCEPTANCE_CRITERIA', source_type: 'TEXT', normally_supplied_by: 'AGENT_1',
    supplied_via: 'STANDALONE_MANUAL_INPUT', label: null, processing_status: 'COLLECTED',
    text_content: 'Refund within 14 days', original_filename: null, mime_type: null, size_bytes: null,
    sha256: null, extraction_status: null, created_at: '2026-10-19T00:00:00Z',
  }
}

function imageSource() {
  return documentSource(9, {
    artifact_type: 'WIREFRAMES', source_type: 'IMAGE', normally_supplied_by: 'AGENT_2',
    processing_status: 'PENDING_ANALYSIS', original_filename: 'checkout.png', mime_type: 'image/png',
  })
}

function extraction(source, status, overrides = {}) {
  return {
    source_id: source.source_id, agent_project_id: 'AGP-004', run_mode: 'TEST_GENERATION',
    artifact_type: source.artifact_type, original_filename: source.original_filename,
    document_type: 'PDF', status, extractor_version: '1', source_sha256: source.sha256,
    content: { pages: [], combined_text: 'Booking requires a confirmation code' },
    metrics: {}, warnings: [], extracted_at: '2026-10-19T00:00:00Z', ...overrides,
  }
}

async function openInputs(user) {
  render(<TestingValidationWorkspace project={project} />)
  await user.click(screen.getByRole('button', { name: /^Test Case Generation/ }))
  return screen.findByRole('button', { name: 'Add Source' })
}

describe('Document extraction in TEST_GENERATION', () => {
  let fetchMock

  beforeEach(() => {
    vi.clearAllMocks()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    listTestGenerationInputs.mockResolvedValue({ data: [] })
    getTestGenerationExtraction.mockResolvedValue({ data: {} })
  })

  it('shows an uploaded document as Uploaded with an Extract action before extraction', async () => {
    const user = userEvent.setup()
    listTestGenerationInputs.mockResolvedValue({ data: [documentSource(1)] })
    await openInputs(user)

    const card = await screen.findByRole('article', { name: 'Acceptance Criteria Document source' })
    expect(within(card).getByText('Uploaded')).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: /^Extract Acceptance Criteria/ })).toBeInTheDocument()
  })

  it('triggers extraction through the service and shows the extracting state', async () => {
    const user = userEvent.setup()
    const source = documentSource(1)
    listTestGenerationInputs.mockResolvedValue({ data: [source] })
    let resolve
    extractTestGenerationSource.mockReturnValue(new Promise((done) => { resolve = done }))
    await openInputs(user)

    await user.click(await screen.findByRole('button', { name: /^Extract Acceptance Criteria/ }))
    expect(extractTestGenerationSource).toHaveBeenCalledWith('AGP-004', source.source_id, { force: false })
    expect(await screen.findByRole('status')).toHaveTextContent('Extracting document text')

    resolve({ data: extraction(source, 'SUCCESS') })
    expect(await screen.findByText('Extracted')).toBeInTheDocument()
  })

  it('shows SUCCESS as Extracted with a content preview and no retry', async () => {
    const user = userEvent.setup()
    const source = documentSource(1)
    listTestGenerationInputs.mockResolvedValue({ data: [{ ...source, extraction_status: 'SUCCESS' }] })
    getTestGenerationExtraction.mockResolvedValue({ data: extraction(source, 'SUCCESS') })
    await openInputs(user)

    const card = await screen.findByRole('article', { name: 'Acceptance Criteria Document source' })
    expect(await within(card).findByText('Extracted')).toBeInTheDocument()
    expect(within(card).getByText('Extracted content preview')).toBeInTheDocument()
    expect(within(card).getByText('Booking requires a confirmation code')).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: /Retry extraction/ })).not.toBeInTheDocument()
  })

  it('shows PARTIAL as Partially Extracted with its warnings and a retry action', async () => {
    const user = userEvent.setup()
    const source = documentSource(1)
    listTestGenerationInputs.mockResolvedValue({ data: [{ ...source, extraction_status: 'PARTIAL' }] })
    getTestGenerationExtraction.mockResolvedValue({
      data: extraction(source, 'PARTIAL', {
        warnings: [{ code: 'NO_TEXT_ON_PAGE', message: 'No extractable text was found on page 2.' }],
      }),
    })
    await openInputs(user)

    const card = await screen.findByRole('article', { name: 'Acceptance Criteria Document source' })
    expect(await within(card).findByText('Partially Extracted')).toBeInTheDocument()
    expect(within(card).getByText('No extractable text was found on page 2.')).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: /^Retry extraction/ })).toBeInTheDocument()
  })

  it('shows FAILED safely without a preview and retries with force', async () => {
    const user = userEvent.setup()
    const source = documentSource(1)
    listTestGenerationInputs.mockResolvedValue({ data: [{ ...source, extraction_status: 'FAILED' }] })
    getTestGenerationExtraction.mockResolvedValue({
      data: extraction(source, 'FAILED', {
        content: { pages: [], combined_text: '' },
        warnings: [{ code: 'EXTRACTION_ERROR', message: 'The document could not be extracted safely.' }],
      }),
    })
    extractTestGenerationSource.mockResolvedValue({ data: extraction(source, 'SUCCESS') })
    await openInputs(user)

    const card = await screen.findByRole('article', { name: 'Acceptance Criteria Document source' })
    expect(await within(card).findByText('Extraction Failed')).toBeInTheDocument()
    expect(within(card).getByText('The document could not be extracted safely.')).toBeInTheDocument()
    expect(within(card).queryByText('Extracted content preview')).not.toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: /^Retry extraction/ }))
    expect(extractTestGenerationSource).toHaveBeenCalledWith('AGP-004', source.source_id, { force: true })
    expect(await within(card).findByText('Extracted')).toBeInTheDocument()
  })

  it('reports a failed extraction request without crashing the workspace', async () => {
    const user = userEvent.setup()
    listTestGenerationInputs.mockResolvedValue({ data: [documentSource(1)] })
    extractTestGenerationSource.mockRejectedValue({ errors: [{ message: 'Document extraction storage is unavailable' }] })
    await openInputs(user)

    await user.click(await screen.findByRole('button', { name: /^Extract Acceptance Criteria/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Document extraction storage is unavailable')
    expect(screen.getByRole('button', { name: 'Add Source' })).toBeInTheDocument()
  })

  it('never offers extraction for IMAGE or TEXT sources', async () => {
    const user = userEvent.setup()
    listTestGenerationInputs.mockResolvedValue({ data: [imageSource(), textSource()] })
    await openInputs(user)

    const image = await screen.findByRole('article', { name: 'Wireframes Image source' })
    expect(within(image).getByText('Pending analysis')).toBeInTheDocument()
    expect(within(image).queryByRole('button', { name: /Extract/ })).not.toBeInTheDocument()

    const text = screen.getByRole('article', { name: 'Acceptance Criteria Text source' })
    expect(within(text).queryByRole('button', { name: /Extract/ })).not.toBeInTheDocument()
    expect(within(text).getByText('Collected')).toBeInTheDocument()
  })

  it('keeps several document sources with independent statuses', async () => {
    const user = userEvent.setup()
    const good = documentSource(1)
    const partial = documentSource(2)
    const failed = documentSource(3)
    listTestGenerationInputs.mockResolvedValue({
      data: [
        { ...good, extraction_status: 'SUCCESS' },
        { ...partial, extraction_status: 'PARTIAL' },
        { ...failed, extraction_status: 'FAILED' },
      ],
    })
    const statusById = { [good.source_id]: 'SUCCESS', [partial.source_id]: 'PARTIAL', [failed.source_id]: 'FAILED' }
    getTestGenerationExtraction.mockImplementation(async (_projectId, sourceId) => {
      const source = [good, partial, failed].find((item) => item.source_id === sourceId)
      return { data: extraction(source, statusById[sourceId]) }
    })
    await openInputs(user)

    const cards = await screen.findAllByRole('article', { name: 'Acceptance Criteria Document source' })
    expect(cards).toHaveLength(3)
    expect(await within(cards[0]).findByText('Extracted')).toBeInTheDocument()
    expect(await within(cards[1]).findByText('Partially Extracted')).toBeInTheDocument()
    expect(await within(cards[2]).findByText('Extraction Failed')).toBeInTheDocument()
  })

  it('does not create an AgentRun, call the run endpoint, or show later-stage output', async () => {
    const user = userEvent.setup()
    const source = documentSource(1)
    listTestGenerationInputs.mockResolvedValue({ data: [source] })
    extractTestGenerationSource.mockResolvedValue({ data: extraction(source, 'SUCCESS') })
    await openInputs(user)

    await user.click(await screen.findByRole('button', { name: /^Extract Acceptance Criteria/ }))
    await waitFor(() => expect(screen.getByText('Extracted')).toBeInTheDocument())

    expect(runTestingValidationAgent).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByText(/Normalized|Readiness|Classification|Traceability|Plan generated|Test Case Plan generated/i)).not.toBeInTheDocument()
  })
})
