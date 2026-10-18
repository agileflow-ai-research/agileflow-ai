import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runTestingValidationAgent } from './testingValidationAgentService.js'
import TestingValidationWorkspace from './TestingValidationWorkspace.jsx'
import {
  deleteStandaloneArtifact,
  extractStandaloneArtifactDocument,
  uploadStandaloneArtifact,
} from '../../../services/agentArtifactUploadService.js'

vi.mock('./testingValidationAgentService.js', () => ({
  runTestingValidationAgent: vi.fn(),
}))

vi.mock('../../../services/agentArtifactUploadService.js', () => ({
  uploadStandaloneArtifact: vi.fn(),
  extractStandaloneArtifactDocument: vi.fn(),
  deleteStandaloneArtifact: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-004', agent_type: 'TESTING_VALIDATION',
  name: 'Quality Gate', domain: 'Fintech',
}

const DOCUMENT_ID = 'SAUP-0123456789abcdef0123456789abcdef'
const IMAGE_ID = 'SAUP-fedcba9876543210fedcba9876543210'

function mockUploadsAndExtraction(extraction = { status: 'SUCCESS', extracted_text: 'AC-001: Email must be unique.', usable_as_context: true }) {
  uploadStandaloneArtifact.mockImplementation(async (_projectId, { source_type, artifact_type, file }) => ({ data: {
    upload_id: source_type === 'DOCUMENT' ? DOCUMENT_ID : IMAGE_ID,
    source_type,
    artifact_type,
    label: null,
    original_filename: file.name,
    mime_type: file.type,
    size_bytes: file.size,
    created_at: '2026-10-18T10:00:00Z',
    processing_status: source_type === 'DOCUMENT' ? 'PENDING_EXTRACTION' : 'PENDING_ANALYSIS',
  } }))
  extractStandaloneArtifactDocument.mockResolvedValue({ data: extraction })
}

async function chooseGeneration(user) {
  await user.click(screen.getByRole('button', { name: /Test Case Generation/ }))
}

async function next(user) {
  await user.click(screen.getByRole('button', { name: 'Next' }))
}

async function addText(user, { type, text }) {
  if (type) await user.selectOptions(screen.getByLabelText('Artifact Type'), type)
  await user.type(screen.getByLabelText('Artifact text'), text)
  await user.click(screen.getByRole('button', { name: 'Add Artifact' }))
}

async function addUpload(user, { source, type, name, mime }) {
  await user.selectOptions(screen.getByLabelText('Input Source'), source)
  if (type) await user.selectOptions(screen.getByLabelText('Artifact Type'), type)
  await user.upload(screen.getByLabelText(source === 'DOCUMENT' ? 'Document file' : 'Image file'), new File(['content'], name, { type: mime }))
  await user.click(screen.getByRole('button', { name: 'Upload and Add Artifact' }))
  await screen.findByText(`File: ${name}`)
}

describe('TestingValidationWorkspace uploaded artifacts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUploadsAndExtraction()
  })

  it('accepts a successfully extracted SRS document as requirements context through the shared service', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    expect(uploadStandaloneArtifact).toHaveBeenCalledWith('AGP-004', expect.objectContaining({ source_type: 'DOCUMENT', artifact_type: 'SRS' }))
    expect(extractStandaloneArtifactDocument).toHaveBeenCalledWith('AGP-004', DOCUMENT_ID)
    await next(user)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Design & Technical Artifacts' })).toBeInTheDocument()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('does not let a pending image satisfy the requirements gate', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'IMAGE', type: 'REQUIREMENTS', name: 'requirements-sheet.png', mime: 'image/png' })
    expect(screen.getByText('Status: Pending analysis')).toBeInTheDocument()
    await next(user)
    expect(screen.getByRole('alert')).toHaveTextContent('Add at least one requirements artifact with text content before continuing.')
    expect(extractStandaloneArtifactDocument).not.toHaveBeenCalled()
  })

  it('does not let a failed extraction satisfy the requirements gate', async () => {
    mockUploadsAndExtraction({ status: 'FAILED', extracted_text: '', usable_as_context: false })
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    expect(screen.getByText('Status: Extraction failed')).toBeInTheDocument()
    await next(user)
    expect(screen.getByRole('alert')).toHaveTextContent('Add at least one requirements artifact')
  })

  it('keeps uploaded artifacts across Back and Next navigation', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByText('File: srs.pdf')).toBeInTheDocument()
    expect(screen.getByText('Status: Extracted')).toBeInTheDocument()
  })

  it('removes an uploaded artifact after the shared delete service succeeds', async () => {
    const user = userEvent.setup()
    deleteStandaloneArtifact.mockResolvedValue({ data: { upload_id: DOCUMENT_ID, deleted: true } })
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(screen.queryByText('File: srs.pdf')).not.toBeInTheDocument())
    expect(deleteStandaloneArtifact).toHaveBeenCalledWith('AGP-004', DOCUMENT_ID)
  })

  it('shows file, status, and preview in Review, and a pending image without understood content', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addText(user, { type: 'REQUIREMENTS', text: 'Customers transfer funds' })
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await next(user)
    await addUpload(user, { source: 'IMAGE', type: 'UI_SPECIFICATION', name: 'registration-wireframe.png', mime: 'image/png' })
    await next(user)
    await next(user)
    await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
    await next(user)

    const requirements = screen.getByRole('heading', { name: 'Requirements Artifacts' }).parentElement
    expect(within(requirements).getByText('File: srs.pdf')).toBeInTheDocument()
    expect(within(requirements).getByText('Status: Extracted')).toBeInTheDocument()
    expect(within(requirements).getByText('AC-001: Email must be unique.')).toBeInTheDocument()
    expect(within(requirements).getByText('Status: Ready')).toBeInTheDocument()

    const design = screen.getByRole('heading', { name: 'Design & Technical Artifacts' }).parentElement
    expect(within(design).getByText('File: registration-wireframe.png')).toBeInTheDocument()
    expect(within(design).getByText('Status: Pending analysis')).toBeInTheDocument()
    expect(within(design).queryByText(/AC-001/)).not.toBeInTheDocument()

    expect(screen.getByText('Test Case Generation')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Selected outputs' })).toHaveTextContent('Unit Test Cases')
    expect(screen.getByRole('heading', { name: 'Quality Gate' })).toBeInTheDocument()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('sends extracted document content with provenance and excludes the pending image from the run payload', async () => {
    const user = userEvent.setup()
    runTestingValidationAgent.mockResolvedValue({ data: { run_id: 'RUN-601', status: 'COMPLETED', run_mode: 'TEST_GENERATION', warnings: [], errors: [], outputs: {} } })
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addText(user, { type: 'REQUIREMENTS', text: 'Customers transfer funds' })
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await next(user)
    await addUpload(user, { source: 'IMAGE', type: 'UI_SPECIFICATION', name: 'wireframe.png', mime: 'image/png' })
    await next(user)
    await next(user)
    await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))

    expect(runTestingValidationAgent).toHaveBeenCalledWith('AGP-004', {
      run_mode: 'TEST_GENERATION',
      selected_outputs: ['UNIT_TEST_CASES'],
      requirements: '--- Artifact: REQUIREMENTS / TEXT / INPUT-001 ---\nCustomers transfer funds',
      SRS: '--- Artifact: SRS / DOCUMENT / INPUT-002 ---\nFile: srs.pdf\nExtraction Status: SUCCESS\nAC-001: Email must be unique.',
    })
    const payload = runTestingValidationAgent.mock.calls[0][1]
    expect(payload).not.toHaveProperty('ui_specification')
    expect(JSON.stringify(payload)).not.toMatch(/wireframe\.png|SAUP-/)
  })

  it('accepts a PARTIAL requirements document and keeps its partial-extraction warning visible', async () => {
    mockUploadsAndExtraction({ status: 'PARTIAL', extracted_text: 'REQ-001 Login', usable_as_context: true })
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    expect(screen.getByText('Status: Partially Extracted')).toBeInTheDocument()
    expect(screen.getByText(/Some content could not be extracted/)).toBeInTheDocument()
    await next(user)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Design & Technical Artifacts' })).toBeInTheDocument()
  })

  it('same-mode Back and reselect keeps the draft upload and deletes nothing', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await chooseGeneration(user)
    expect(screen.getByText('File: srs.pdf')).toBeInTheDocument()
    expect(deleteStandaloneArtifact).not.toHaveBeenCalled()
  })

  it('switching to VALIDATION discards the TEST_GENERATION draft and deletes its uploads', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await user.click(screen.getByRole('button', { name: 'Change mode' }))
    await user.click(screen.getByRole('button', { name: /Testing & Validation/ }))
    await waitFor(() => expect(deleteStandaloneArtifact).toHaveBeenCalledWith('AGP-004', DOCUMENT_ID))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('Start another run deletes the completed draft-only uploads', async () => {
    const user = userEvent.setup()
    runTestingValidationAgent.mockResolvedValue({ data: { run_id: 'RUN-701', status: 'COMPLETED', run_mode: 'TEST_GENERATION', warnings: [], errors: [], outputs: {} } })
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await next(user)
    await next(user)
    await next(user)
    await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))
    await user.click(await screen.findByRole('button', { name: 'Start another run' }))
    await waitFor(() => expect(deleteStandaloneArtifact).toHaveBeenCalledWith('AGP-004', DOCUMENT_ID))
    expect(screen.getByRole('button', { name: /Test Case Generation/ })).toBeInTheDocument()
  })

  it('a failed server delete during discard stays queued, is announced, and can be retried', async () => {
    const user = userEvent.setup()
    deleteStandaloneArtifact.mockRejectedValueOnce({ status: 503, errors: [{ message: 'Artifact storage failed' }] })
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addUpload(user, { source: 'DOCUMENT', type: 'SRS', name: 'srs.pdf', mime: 'application/pdf' })
    await user.click(screen.getByRole('button', { name: 'Change mode' }))
    await user.click(screen.getByRole('button', { name: /Testing & Validation/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be removed from the server')
    await user.click(screen.getByRole('button', { name: 'Retry cleanup' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(deleteStandaloneArtifact).toHaveBeenCalledTimes(2)
    expect(deleteStandaloneArtifact).toHaveBeenLastCalledWith('AGP-004', DOCUMENT_ID)
  })
})
