import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TestingArtifactCollector, { ArtifactReviewList } from './TestingArtifactCollector.jsx'
import { createArtifact, createUploadedArtifact, getArtifactGroup } from './testGenerationArtifacts.js'
import {
  deleteStandaloneArtifact,
  extractStandaloneArtifactDocument,
  uploadStandaloneArtifact,
} from '../../../services/agentArtifactUploadService.js'

vi.mock('../../../services/agentArtifactUploadService.js', () => ({
  uploadStandaloneArtifact: vi.fn(),
  extractStandaloneArtifactDocument: vi.fn(),
  deleteStandaloneArtifact: vi.fn(),
}))

const requirements = getArtifactGroup('REQUIREMENTS')
const UPLOAD_ID = 'SAUP-0123456789abcdef0123456789abcdef'

const extractedDocument = createUploadedArtifact({
  input_id: 'INPUT-002', artifact_type: 'ACCEPTANCE_CRITERIA', source_type: 'DOCUMENT', upload_reference: UPLOAD_ID,
  original_filename: 'acceptance-criteria.pdf', mime_type: 'application/pdf', processing_status: 'SUCCESS',
  extracted_content: 'AC-001: Email must be unique.',
})

const pendingDocument = createUploadedArtifact({
  input_id: 'INPUT-003', artifact_type: 'SRS', source_type: 'DOCUMENT', upload_reference: 'SAUP-fedcba9876543210fedcba9876543210',
  original_filename: 'srs-draft.docx', mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  processing_status: 'PENDING_EXTRACTION',
})

const partialDocument = createUploadedArtifact({
  input_id: 'INPUT-005', artifact_type: 'USER_STORIES', source_type: 'DOCUMENT', upload_reference: 'SAUP-11111111111111111111111111111111',
  original_filename: 'stories.pdf', mime_type: 'application/pdf', processing_status: 'PARTIAL', extracted_content: 'Only page one',
})

const pendingImage = createUploadedArtifact({
  input_id: 'INPUT-004', artifact_type: 'REQUIREMENTS', source_type: 'IMAGE', upload_reference: 'SAUP-22222222222222222222222222222222',
  original_filename: 'requirements-sheet.png', mime_type: 'image/png', processing_status: 'PENDING_ANALYSIS',
})

const text = createArtifact({ input_id: 'INPUT-001', artifact_type: 'USER_STORIES', content: 'As a patient I book', label: 'Booking' })

function renderCollector(props = {}) {
  const handlers = { onAdd: vi.fn(), onReplace: vi.fn(), onRemove: vi.fn() }
  const view = render(
    <TestingArtifactCollector
      group={requirements}
      agentProjectId="AGP-001"
      artifacts={[]}
      {...handlers}
      {...props}
    />,
  )
  return { ...view, ...handlers }
}

describe('TestingArtifactCollector upload flow', () => {
  beforeEach(() => vi.clearAllMocks())

  it('offers Text, Document, and Image as selectable input sources', () => {
    renderCollector()
    const source = within(screen.getByLabelText('Input Source'))
    expect(source.getByRole('option', { name: 'Text' })).not.toBeDisabled()
    expect(source.getByRole('option', { name: 'Document' })).not.toBeDisabled()
    expect(source.getByRole('option', { name: 'Image' })).not.toBeDisabled()
  })

  it('uploads a document through the shared service, extracts it, and adds only trusted metadata', async () => {
    const user = userEvent.setup()
    uploadStandaloneArtifact.mockResolvedValue({ data: {
      upload_id: UPLOAD_ID, source_type: 'DOCUMENT', artifact_type: 'ACCEPTANCE_CRITERIA', label: null,
      original_filename: 'acceptance-criteria.pdf', mime_type: 'application/pdf', size_bytes: 9,
      created_at: '2026-10-18T10:00:00Z', processing_status: 'PENDING_EXTRACTION',
    } })
    extractStandaloneArtifactDocument.mockResolvedValue({ data: { status: 'SUCCESS', extracted_text: 'AC-001: Email must be unique.', usable_as_context: true } })
    const { onAdd } = renderCollector()

    await user.selectOptions(screen.getByLabelText('Input Source'), 'DOCUMENT')
    await user.selectOptions(screen.getByLabelText('Artifact Type'), 'ACCEPTANCE_CRITERIA')
    const file = new File(['AC-001'], 'acceptance-criteria.pdf', { type: 'application/pdf' })
    await user.upload(screen.getByLabelText('Document file'), file)
    await user.click(screen.getByRole('button', { name: 'Upload and Add Artifact' }))

    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1))
    expect(uploadStandaloneArtifact).toHaveBeenCalledWith('AGP-001', {
      source_type: 'DOCUMENT', artifact_type: 'ACCEPTANCE_CRITERIA', label: '', file,
    })
    expect(extractStandaloneArtifactDocument).toHaveBeenCalledWith('AGP-001', UPLOAD_ID)
    expect(onAdd).toHaveBeenCalledWith({
      artifact_type: 'ACCEPTANCE_CRITERIA',
      source_type: 'DOCUMENT',
      label: '',
      uploaded: {
        upload_reference: UPLOAD_ID,
        original_filename: 'acceptance-criteria.pdf',
        mime_type: 'application/pdf',
        processing_status: 'SUCCESS',
        extracted_content: 'AC-001: Email must be unique.',
      },
    })
  })

  it('uploads an image through the shared service without any extraction and reports it is not understood', async () => {
    const user = userEvent.setup()
    uploadStandaloneArtifact.mockResolvedValue({ data: {
      upload_id: 'SAUP-33333333333333333333333333333333', source_type: 'IMAGE', artifact_type: 'UI_SPECIFICATION',
      original_filename: 'registration-wireframe.png', mime_type: 'image/png', size_bytes: 80,
      created_at: '2026-10-18T10:00:00Z', processing_status: 'PENDING_ANALYSIS',
    } })
    const { onAdd } = renderCollector()

    await user.selectOptions(screen.getByLabelText('Input Source'), 'IMAGE')
    await user.selectOptions(screen.getByLabelText('Artifact Type'), 'REQUIREMENTS')
    await user.upload(screen.getByLabelText('Image file'), new File(['png'], 'registration-wireframe.png', { type: 'image/png' }))
    await user.click(screen.getByRole('button', { name: 'Upload and Add Artifact' }))

    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1))
    expect(extractStandaloneArtifactDocument).not.toHaveBeenCalled()
    expect(onAdd.mock.calls[0][0].uploaded).toMatchObject({ processing_status: 'PENDING_ANALYSIS', extracted_content: null })
    expect(screen.getByRole('status')).toHaveTextContent('Visual understanding is not available yet')
  })

  it('blocks a second submit while an upload is pending', async () => {
    const user = userEvent.setup()
    uploadStandaloneArtifact.mockReturnValue(new Promise(() => {}))
    renderCollector()
    await user.selectOptions(screen.getByLabelText('Input Source'), 'DOCUMENT')
    await user.upload(screen.getByLabelText('Document file'), new File(['AC'], 'ac.pdf', { type: 'application/pdf' }))
    await user.dblClick(screen.getByRole('button', { name: 'Upload and Add Artifact' }))
    expect(uploadStandaloneArtifact).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Uploading file' })).toBeDisabled()
  })

  it('keeps a document pending and visible when extraction fails after upload', async () => {
    const user = userEvent.setup()
    uploadStandaloneArtifact.mockResolvedValue({ data: {
      upload_id: UPLOAD_ID, source_type: 'DOCUMENT', artifact_type: 'SRS', original_filename: 'srs.pdf',
      mime_type: 'application/pdf', size_bytes: 9, created_at: '2026-10-18T10:00:00Z', processing_status: 'PENDING_EXTRACTION',
    } })
    extractStandaloneArtifactDocument.mockRejectedValue({ status: 503, errors: [{ message: 'Artifact storage failed' }] })
    const { onAdd } = renderCollector()
    await user.selectOptions(screen.getByLabelText('Input Source'), 'DOCUMENT')
    await user.selectOptions(screen.getByLabelText('Artifact Type'), 'SRS')
    await user.upload(screen.getByLabelText('Document file'), new File(['%PDF-'], 'srs.pdf', { type: 'application/pdf' }))
    await user.click(screen.getByRole('button', { name: 'Upload and Add Artifact' }))

    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1))
    expect(onAdd.mock.calls[0][0].uploaded.processing_status).toBe('PENDING_EXTRACTION')
    expect(screen.getByRole('alert')).toHaveTextContent('remains pending')
  })

  it('shows an error and adds nothing when the upload is rejected', async () => {
    const user = userEvent.setup()
    uploadStandaloneArtifact.mockRejectedValue({ status: 422, errors: [{ message: 'File content does not match the declared .pdf type' }] })
    const { onAdd } = renderCollector()
    await user.selectOptions(screen.getByLabelText('Input Source'), 'DOCUMENT')
    await user.upload(screen.getByLabelText('Document file'), new File(['%PDF-'], 'broken.pdf', { type: 'application/pdf' }))
    await user.click(screen.getByRole('button', { name: 'Upload and Add Artifact' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('File content does not match the declared .pdf type')
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('requires a chosen file before an upload is attempted', async () => {
    const user = userEvent.setup()
    renderCollector()
    await user.selectOptions(screen.getByLabelText('Input Source'), 'DOCUMENT')
    expect(screen.getByRole('button', { name: 'Upload and Add Artifact' })).toBeDisabled()
    expect(uploadStandaloneArtifact).not.toHaveBeenCalled()
  })

  it('removes an uploaded artifact through the shared delete service before removing it from the draft', async () => {
    const user = userEvent.setup()
    deleteStandaloneArtifact.mockResolvedValue({ data: { upload_id: UPLOAD_ID, deleted: true } })
    const { onRemove } = renderCollector({ artifacts: [extractedDocument] })
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(onRemove).toHaveBeenCalledWith('INPUT-002'))
    expect(deleteStandaloneArtifact).toHaveBeenCalledWith('AGP-001', UPLOAD_ID)
  })

  it('keeps an uploaded artifact when its server removal fails', async () => {
    const user = userEvent.setup()
    deleteStandaloneArtifact.mockRejectedValue({ status: 503, errors: [{ message: 'Artifact storage failed' }] })
    const { onRemove } = renderCollector({ artifacts: [extractedDocument] })
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Artifact storage failed')
    expect(onRemove).not.toHaveBeenCalled()
  })
})

describe('TestingArtifactCollector cards', () => {
  it('displays an extracted document with filename, status, and preview, without Edit', () => {
    renderCollector({ artifacts: [extractedDocument] })
    const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
    expect(within(list).getByText('File: acceptance-criteria.pdf')).toBeInTheDocument()
    expect(within(list).getByText('Status: Extracted')).toBeInTheDocument()
    expect(within(list).getByText('AC-001: Email must be unique.')).toBeInTheDocument()
    expect(within(list).getByText('Usable as test-generation context.')).toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
  })

  it('explains that a pending image is preserved but not understood context', () => {
    renderCollector({ artifacts: [pendingImage] })
    const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
    expect(within(list).getByText('Status: Pending analysis')).toBeInTheDocument()
    expect(within(list).getByText(/Not usable as context: image analysis has not produced understood content/)).toBeInTheDocument()
  })

  it('shows a partially extracted document as usable with a visible partial-extraction warning', () => {
    renderCollector({ artifacts: [partialDocument] })
    const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
    expect(within(list).getByText('Status: Partially Extracted')).toBeInTheDocument()
    expect(within(list).getByText(/Some content could not be extracted\. This artifact is usable/)).toBeInTheDocument()
    expect(within(list).getByText(/Usable as test-generation context, with a partial-extraction warning/)).toBeInTheDocument()
    expect(within(list).getByText('Only page one')).toBeInTheDocument()
  })

  it('treats a 404 from server removal as already removed', async () => {
    const user = userEvent.setup()
    deleteStandaloneArtifact.mockRejectedValue({ status: 404, errors: [{ message: 'Artifact upload not found' }] })
    const { onRemove } = renderCollector({ artifacts: [extractedDocument] })
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(onRemove).toHaveBeenCalledWith('INPUT-002'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('removes TEXT artifacts locally without calling the delete service', async () => {
    const user = userEvent.setup()
    const { onRemove } = renderCollector({ artifacts: [text] })
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    expect(onRemove).toHaveBeenCalledWith('INPUT-001')
    expect(deleteStandaloneArtifact).not.toHaveBeenCalled()
  })

  it('removes an uploaded IMAGE through the shared delete service', async () => {
    const user = userEvent.setup()
    deleteStandaloneArtifact.mockResolvedValue({ data: { upload_id: 'SAUP-22222222222222222222222222222222', deleted: true } })
    const { onRemove } = renderCollector({ artifacts: [pendingImage] })
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(onRemove).toHaveBeenCalledWith('INPUT-004'))
    expect(deleteStandaloneArtifact).toHaveBeenCalledWith('AGP-001', 'SAUP-22222222222222222222222222222222')
  })

  it('shows the partial-extraction warning in Review for a partially extracted document', () => {
    render(<ArtifactReviewList artifacts={[partialDocument]} />)
    expect(screen.getByText('Status: Partially Extracted')).toBeInTheDocument()
    expect(screen.getByText(/Some content could not be extracted\. This artifact is usable, but test generation may have incomplete source coverage\./)).toBeInTheDocument()
    expect(screen.getByText('Only page one')).toBeInTheDocument()
  })

  it('keeps Edit for TEXT artifacts and updates them in place', async () => {
    const user = userEvent.setup()
    const { onReplace } = renderCollector({ artifacts: [text] })
    const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
    await user.click(within(list).getByRole('button', { name: 'Edit' }))
    expect(screen.getByLabelText('Artifact text')).toHaveValue('As a patient I book')
    await user.clear(screen.getByLabelText('Artifact text'))
    await user.type(screen.getByLabelText('Artifact text'), 'Updated story')
    await user.click(screen.getByRole('button', { name: 'Save artifact' }))
    expect(onReplace).toHaveBeenCalledWith('INPUT-001', expect.objectContaining({ content: 'Updated story' }))
  })

  it('keeps several same-type artifacts visually and logically separate', () => {
    const second = createUploadedArtifact({
      input_id: 'INPUT-006', artifact_type: 'ACCEPTANCE_CRITERIA', source_type: 'DOCUMENT', upload_reference: 'SAUP-44444444444444444444444444444444',
      original_filename: 'payment-ac.pdf', mime_type: 'application/pdf', processing_status: 'PENDING_EXTRACTION',
    })
    renderCollector({ artifacts: [extractedDocument, second] })
    const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)
    expect(within(list).getByText('INPUT-002')).toBeInTheDocument()
    expect(within(list).getByText('INPUT-006')).toBeInTheDocument()
    expect(within(list).getByText('File: payment-ac.pdf')).toBeInTheDocument()
  })
})

describe('ArtifactReviewList', () => {
  it('shows type, source, filename, status, and preview for an extracted document', () => {
    render(<ArtifactReviewList artifacts={[extractedDocument]} />)
    expect(screen.getByText('1. Acceptance Criteria')).toBeInTheDocument()
    expect(screen.getByText(/Source: Document · INPUT-002/)).toBeInTheDocument()
    expect(screen.getByText('File: acceptance-criteria.pdf')).toBeInTheDocument()
    expect(screen.getByText('Status: Extracted')).toBeInTheDocument()
    expect(screen.getByText('AC-001: Email must be unique.')).toBeInTheDocument()
  })

  it('shows a pending image with its state and no preview', () => {
    render(<ArtifactReviewList artifacts={[pendingImage]} />)
    expect(screen.getByText('File: requirements-sheet.png')).toBeInTheDocument()
    expect(screen.getByText('Status: Pending analysis')).toBeInTheDocument()
    expect(screen.getByText(/Source: Image/)).toBeInTheDocument()
  })

  it('shows a pending document without a preview and labels TEXT as Ready', () => {
    render(<ArtifactReviewList artifacts={[pendingDocument, text]} />)
    expect(screen.getByText('File: srs-draft.docx')).toBeInTheDocument()
    expect(screen.getByText('Status: Pending extraction')).toBeInTheDocument()
    expect(screen.getByText('As a patient I book')).toBeInTheDocument()
    expect(screen.getByText('Status: Ready')).toBeInTheDocument()
    expect(screen.queryByText(/Email must be unique/)).not.toBeInTheDocument()
  })

  it('does not expose upload references, storage roots, or filesystem paths', () => {
    const { container } = render(<ArtifactReviewList artifacts={[extractedDocument, pendingImage, text]} />)
    expect(container.textContent).not.toMatch(/SAUP|storage|uploads|\//)
  })
})
