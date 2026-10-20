import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteRequirementSource,
  continueRequirementN1,
  getNormalizedRequirementEvidence,
  getRequirementAudioProcessingResult,
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingResult,
  getRequirementDocumentProcessingStatus,
  getRequirementEvidenceChunks,
  getRequirementPreparationStatus,
  getRequirementWorkflow,
  getRequirementVideoProcessingResult,
  getRequirementVideoProcessingStatus,
  listRequirementSources,
  prepareRequirementEvidence,
  processRequirementAudio,
  processRequirementDocument,
  processRequirementVideo,
  retryRequirementN2,
  uploadRequirementSource,
  updateRequirementOutputs,
} from './requirementsAgentService.js'
import RequirementsWorkspace from './RequirementsWorkspace.jsx'
import { REQUIREMENTS_NODE_IDS } from './workflow/nodeDefinitions.js'
import { deriveRequirementsWorkflowPresentation } from './workflow/presentation.js'

vi.mock('./requirementsAgentService.js', () => ({
  deleteRequirementSource: vi.fn(),
  continueRequirementN1: vi.fn(),
  getNormalizedRequirementEvidence: vi.fn(),
  getRequirementAudioProcessingResult: vi.fn(),
  getRequirementAudioProcessingStatus: vi.fn(),
  getRequirementDocumentProcessingResult: vi.fn(),
  getRequirementDocumentProcessingStatus: vi.fn(),
  getRequirementEvidenceChunks: vi.fn(),
  getRequirementPreparationStatus: vi.fn(),
  getRequirementWorkflow: vi.fn(),
  getRequirementVideoProcessingResult: vi.fn(),
  getRequirementVideoProcessingStatus: vi.fn(),
  listRequirementSources: vi.fn(),
  prepareRequirementEvidence: vi.fn(),
  processRequirementAudio: vi.fn(),
  processRequirementDocument: vi.fn(),
  processRequirementVideo: vi.fn(),
  retryRequirementN2: vi.fn(),
  uploadRequirementSource: vi.fn(),
  updateRequirementOutputs: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-001', agent_type: 'REQUIREMENTS', name: 'BookEase', domain: 'Library',
}
const persistedSources = [
  { source_id: 'DOC-001', source_type: 'DOCUMENT', original_filename: 'requirements.pdf', status: 'READY' },
  { source_id: 'AUD-001', source_type: 'AUDIO', original_filename: 'interview.mp3', status: 'READY' },
  { source_id: 'VID-001', source_type: 'VIDEO', original_filename: 'workflow.mp4', status: 'READY' },
]

function processingStatus(sourceId, status = 'READY', error = null) {
  return { data: { source_id: sourceId, status, error } }
}

function preparationStatus(sourceId, status = 'READY', error = null) {
  return { data: { source_id: sourceId, status, error } }
}

function chunksFor(sourceId, sourceType = 'DOCUMENT', provenance = []) {
  return { data: {
    source_id: sourceId,
    source_type: sourceType,
    chunks: [{
      chunk_id: `CHK-${sourceId.replace('-', '').padEnd(16, '0')}`,
      content: `Prepared evidence for ${sourceId}.`,
      provenance,
    }],
  } }
}

describe('RequirementsWorkspace seven-node pipeline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRequirementSources.mockResolvedValue({ data: persistedSources })
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'WAITING_FOR_HUMAN', selection_revision: 1,
    } })
    updateRequirementOutputs.mockResolvedValue({ data: {
      selected_outputs: ['FUNCTIONAL_REQUIREMENTS', 'SRS'], n1_state: 'WAITING_FOR_HUMAN', selection_revision: 2,
    } })
    continueRequirementN1.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', selection_revision: 1,
      n2_is_current: true,
      n2_execution: {
        execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'QUEUED', retryable: false,
        input_sources: persistedSources, source_progress: [],
      },
    } })
    retryRequirementN2.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', selection_revision: 1,
      n2_is_current: true,
      n2_execution: {
        execution_id: 'N2-AAAAAAAAAAAAAAAA-002', status: 'QUEUED', retryable: false,
        input_sources: persistedSources, source_progress: [],
      },
    } })
    getRequirementDocumentProcessingStatus.mockResolvedValue(processingStatus('DOC-001'))
    getRequirementAudioProcessingStatus.mockResolvedValue(processingStatus('AUD-001'))
    getRequirementVideoProcessingStatus.mockResolvedValue(processingStatus('VID-001'))
    getRequirementPreparationStatus.mockImplementation((_, sourceId) => (
      Promise.resolve(preparationStatus(sourceId))
    ))
  })

  it('renders locked informational content for an unimplemented active section', async () => {
    render(
      <RequirementsWorkspace
        project={project}
        activeSection={REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING}
      />,
    )
    expect(await screen.findByRole('heading', { name: 'Requirement Discovery & Structuring' })).toBeInTheDocument()
    expect(screen.getByText(/backend stage is implemented/i)).toBeInTheDocument()
    expect(screen.queryByText(/functional requirement/i)).not.toBeInTheDocument()
  })

  it('keeps completed N1 reviewable and contains only collection controls', async () => {
    render(<RequirementsWorkspace project={project} />)

    expect(await screen.findByRole('heading', { name: 'Client Requirement Sources' })).toBeInTheDocument()
    ;['Add Documents', 'Add Audio', 'Add Video'].forEach((label) => {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    })
    ;['DOC-001', 'AUD-001', 'VID-001', 'requirements.pdf', 'interview.mp3', 'workflow.mp4'].forEach((text) => {
      expect(screen.getByText(text)).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: /Process Document|Process Audio|Process Video|Prepare Evidence/ })).not.toBeInTheDocument()
    expect(screen.getByText('Functional Requirements')).toBeInTheDocument()
    expect(screen.getByText('Non-Functional Requirements')).toBeInTheDocument()
    expect(screen.getByText('Software Requirements Specification')).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(6)
    expect(screen.getByRole('checkbox', { name: 'Software Requirements Specification' })).toBeChecked()
    expect(screen.queryByText('Quality Findings')).not.toBeInTheDocument()
    expect(screen.queryByText('Clarification Questions')).not.toBeInTheDocument()
  })

  it('persists requested outputs and confirms N1 without starting N2', async () => {
    const user = userEvent.setup()
    render(<RequirementsWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Client Requirement Sources' })

    await user.click(screen.getByRole('checkbox', { name: 'Functional Requirements' }))
    await waitFor(() => expect(updateRequirementOutputs).toHaveBeenCalledWith(
      'AGP-001', ['SRS', 'FUNCTIONAL_REQUIREMENTS'],
    ))
    await user.click(screen.getByRole('button', { name: 'Continue — Process Evidence' }))
    await waitFor(() => expect(continueRequirementN1).toHaveBeenCalledWith('AGP-001'))
    expect(await screen.findByText('The current sources and requested outputs are confirmed.')).toBeInTheDocument()
    expect(processRequirementDocument).not.toHaveBeenCalled()
    expect(processRequirementAudio).not.toHaveBeenCalled()
    expect(processRequirementVideo).not.toHaveBeenCalled()
  })

  it('disables Continue until both a source and persisted output exist', async () => {
    listRequirementSources.mockResolvedValue({ data: [] })
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: [], n1_state: 'NOT_STARTED', selection_revision: 0,
    } })
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByRole('button', { name: 'Continue — Process Evidence' })).toBeDisabled()
  })

  it('shows safe N2 failure progress and sends the explicit retry command', async () => {
    const user = userEvent.setup()
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', n2_is_current: true,
      n2_execution: {
        execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'FAILED', retryable: true,
        input_sources: [{ source_id: 'DOC-001' }],
        source_progress: [{
          source_id: 'DOC-001', processing_status: 'FAILED', preparation_status: 'READY', chunk_count: 0,
        }],
        error: { code: 'SOURCE_PROCESSING_FAILED', message: 'A confirmed source could not be processed.' },
      },
    } })
    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)

    expect(await screen.findByLabelText('N2 orchestration status')).toHaveTextContent('SOURCE_PROCESSING_FAILED')
    expect(screen.getByLabelText('N2 orchestration status')).toHaveTextContent('Processing: FAILED')
    await new Promise((resolve) => window.setTimeout(resolve, 850))
    expect(getRequirementWorkflow).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Retry N2' }))
    await waitFor(() => expect(retryRequirementN2).toHaveBeenCalledWith('AGP-001'))
  })

  it('polls authoritative workflow state while N2 is active without issuing another start', async () => {
    const queued = {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', n2_is_current: true,
      n2_execution: {
        execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'QUEUED', retryable: false,
        input_sources: [{ source_id: 'DOC-001' }],
        source_progress: [{ source_id: 'DOC-001', processing_status: 'READY', preparation_status: 'READY', chunk_count: 0 }],
      },
    }
    getRequirementWorkflow
      .mockResolvedValueOnce({ data: queued })
      .mockResolvedValue({ data: {
        ...queued,
        n2_execution: { ...queued.n2_execution, status: 'COMPLETE' },
      } })
    let snapshot
    render(
      <RequirementsWorkspace
        project={project}
        activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING}
        onPresentationChange={(value) => { snapshot = value }}
      />,
    )

    await waitFor(() => {
      expect(deriveRequirementsWorkflowPresentation(snapshot)[REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING].status).toBe('COMPLETE')
    }, { timeout: 2000 })
    expect(continueRequirementN1).not.toHaveBeenCalled()
    await waitFor(() => expect(getRequirementWorkflow).toHaveBeenCalledTimes(3))
    await new Promise((resolve) => window.setTimeout(resolve, 850))
    expect(getRequirementWorkflow).toHaveBeenCalledTimes(3)
  })

  it('keeps Continue disabled when sources exist but no output is selected', async () => {
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: [], n1_state: 'NOT_STARTED', selection_revision: 0,
    } })
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByRole('button', { name: 'Continue — Process Evidence' })).toBeDisabled()
  })

  it('uploads mixed sources, removes one, and reloads persisted sources', async () => {
    const user = userEvent.setup()
    listRequirementSources.mockResolvedValueOnce({ data: [] })
    uploadRequirementSource
      .mockResolvedValueOnce({ data: { source_id: 'DOC-001', source_type: 'DOCUMENT', original_filename: 'one.pdf', status: 'READY' } })
      .mockResolvedValueOnce({ data: { source_id: 'DOC-002', source_type: 'DOCUMENT', original_filename: 'two.txt', status: 'READY' } })
      .mockResolvedValueOnce({ data: { source_id: 'AUD-001', source_type: 'AUDIO', original_filename: 'call.mp3', status: 'READY' } })
    deleteRequirementSource.mockResolvedValue({ data: { source_id: 'DOC-001' } })
    const firstView = render(<RequirementsWorkspace project={project} />)
    await screen.findByText('No requirement sources uploaded yet.')

    const document = new File(['pdf'], 'one.pdf', { type: 'application/pdf' })
    const text = new File(['notes'], 'two.txt', { type: 'text/plain' })
    const audio = new File(['audio'], 'call.mp3', { type: 'audio/mpeg' })
    await user.upload(screen.getByLabelText('Document files'), [document, text])
    await user.upload(screen.getByLabelText('Audio files'), audio)
    expect(await screen.findByText('AUD-001')).toBeInTheDocument()
    expect(uploadRequirementSource).toHaveBeenNthCalledWith(1, 'AGP-001', 'DOCUMENT', document)
    expect(uploadRequirementSource).toHaveBeenNthCalledWith(2, 'AGP-001', 'DOCUMENT', text)
    expect(uploadRequirementSource).toHaveBeenNthCalledWith(3, 'AGP-001', 'AUDIO', audio)

    await user.click(screen.getAllByRole('button', { name: 'Remove' })[0])
    await waitFor(() => expect(screen.queryByText('DOC-001')).not.toBeInTheDocument())
    expect(deleteRequirementSource).toHaveBeenCalledWith('AGP-001', 'DOC-001')
    firstView.unmount()

    listRequirementSources.mockResolvedValue({ data: persistedSources.slice(1) })
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('AUD-001')).toBeInTheDocument()
    expect(screen.queryByText('DOC-001')).not.toBeInTheDocument()
  })

  it('navigates to N2 and provides document, audio, video, and preparation actions', async () => {
    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)
    expect(await screen.findByRole('heading', { name: 'Multimodal Processing & Chunking' })).toBeInTheDocument()
    ;['Document Processing', 'Audio Transcription', 'Video Processing', 'Evidence Preparation'].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Process Document' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Process Audio' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Process Video' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add Documents' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Prepare Evidence' })).not.toBeInTheDocument()
  })

  it('uses the correct processor actions, including retry and force reprocessing', async () => {
    const user = userEvent.setup()
    getRequirementDocumentProcessingStatus.mockResolvedValue(processingStatus('DOC-001', 'FAILED', {
      code: 'NO_MACHINE_READABLE_TEXT', message: 'OCR is not available.',
    }))
    getRequirementAudioProcessingStatus.mockResolvedValue(processingStatus('AUD-001', 'COMPLETED'))
    getRequirementVideoProcessingStatus.mockResolvedValue(processingStatus('VID-001', 'FAILED', {
      code: 'VIDEO_NO_AUDIO_TRACK', message: 'The video has no usable audio track.',
    }))
    processRequirementDocument.mockResolvedValue(processingStatus('DOC-001', 'COMPLETED'))
    processRequirementAudio.mockResolvedValue(processingStatus('AUD-001', 'COMPLETED'))
    processRequirementVideo.mockResolvedValue(processingStatus('VID-001', 'COMPLETED'))
    getRequirementPreparationStatus.mockImplementation((_, sourceId) => Promise.resolve(
      preparationStatus(sourceId, sourceId === 'AUD-001' ? 'FAILED' : 'READY'),
    ))
    prepareRequirementEvidence.mockResolvedValue(preparationStatus('AUD-001', 'COMPLETED'))
    getRequirementEvidenceChunks.mockResolvedValue(chunksFor('AUD-001', 'AUDIO'))
    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)
    const documentCard = (await screen.findByText(/DOC-001 · requirements.pdf/)).closest('[data-variant]')
    const audioCard = screen.getByText(/AUD-001 · interview.mp3/).closest('[data-variant]')
    const videoCard = screen.getByText(/VID-001 · workflow.mp4/).closest('[data-variant]')

    expect(within(documentCard).getByText(/NO_MACHINE_READABLE_TEXT/)).toBeInTheDocument()
    await user.click(within(documentCard).getByRole('button', { name: 'Retry Processing' }))
    expect(processRequirementDocument).toHaveBeenCalledWith('AGP-001', 'DOC-001', { force: true })
    await user.click(within(audioCard).getByRole('button', { name: 'Retry Preparation' }))
    expect(prepareRequirementEvidence).toHaveBeenCalledWith('AGP-001', 'AUD-001', { force: true })
    await user.click(within(audioCard).getByRole('button', { name: 'Reprocess' }))
    expect(processRequirementAudio).toHaveBeenCalledWith('AGP-001', 'AUD-001', { force: true })
    expect(within(videoCard).getByText(/VIDEO_NO_AUDIO_TRACK/)).toBeInTheDocument()
    await user.click(within(videoCard).getByRole('button', { name: 'Retry' }))
    expect(processRequirementVideo).toHaveBeenCalledWith('AGP-001', 'VID-001', { force: true })
  })

  it('reloads real completed processing/preparation data and marks N2 complete only with chunks', async () => {
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', n2_is_current: true,
      n2_execution: { execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'COMPLETE' },
    } })
    getRequirementDocumentProcessingStatus.mockResolvedValue(processingStatus('DOC-001', 'COMPLETED'))
    getRequirementAudioProcessingStatus.mockResolvedValue(processingStatus('AUD-001', 'COMPLETED'))
    getRequirementVideoProcessingStatus.mockResolvedValue(processingStatus('VID-001', 'COMPLETED'))
    getRequirementPreparationStatus.mockImplementation((_, sourceId) => (
      Promise.resolve(preparationStatus(sourceId, 'COMPLETED'))
    ))
    getRequirementEvidenceChunks.mockImplementation((_, sourceId) => Promise.resolve(chunksFor(
      sourceId,
      sourceId.startsWith('DOC') ? 'DOCUMENT' : sourceId.startsWith('AUD') ? 'AUDIO' : 'VIDEO',
    )))
    let snapshot
    render(
      <RequirementsWorkspace
        project={project}
        activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING}
        onPresentationChange={(value) => { snapshot = value }}
      />,
    )

    await waitFor(() => {
      expect(deriveRequirementsWorkflowPresentation(snapshot)[REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING].status).toBe('COMPLETE')
    })
    expect(getRequirementEvidenceChunks).toHaveBeenCalledTimes(3)
  })

  it('hydrates completed W2 detail state on reload and shows neutral zero-source modalities', async () => {
    const documentOnly = [persistedSources[0]]
    listRequirementSources.mockResolvedValue({ data: documentOnly })
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', n2_is_current: true,
      n2_execution: {
        execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'COMPLETE',
        input_sources: documentOnly,
        source_progress: [{
          source_id: 'DOC-001', processing_status: 'COMPLETE', preparation_status: 'COMPLETE', chunk_count: 5,
        }],
      },
    } })
    getRequirementDocumentProcessingStatus.mockResolvedValue(processingStatus('DOC-001', 'COMPLETED'))
    getRequirementPreparationStatus.mockResolvedValue(preparationStatus('DOC-001', 'COMPLETED'))
    getRequirementEvidenceChunks.mockResolvedValue({ data: {
      source_id: 'DOC-001', source_type: 'DOCUMENT',
      chunks: Array.from({ length: 5 }, (_, index) => ({
        chunk_id: `CHK-${String(index + 1).padStart(16, '0')}`,
        content: `Chunk ${index + 1}`,
        provenance: [],
      })),
    } })

    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)

    const documentCard = (await screen.findByText(/requirements\.pdf/)).closest('[data-variant]')
    expect(within(documentCard).getAllByText('Complete')).toHaveLength(2)
    expect(within(documentCard).getByText('5 chunks')).toBeInTheDocument()
    expect(within(documentCard).getByRole('button', { name: 'View Extraction' })).toBeInTheDocument()
    expect(within(documentCard).getByRole('button', { name: 'View Prepared Evidence' })).toBeInTheDocument()
    expect(within(documentCard).queryByRole('button', { name: /Process Document|Reprocess|Prepare Evidence|Reprepare/ })).not.toBeInTheDocument()

    const progress = screen.getByRole('heading', { name: 'N2 Progress' }).parentElement
    expect(within(progress).getByText('1 document source')).toBeInTheDocument()
    expect(within(progress).getByText('1 of 1 source prepared')).toBeInTheDocument()
    expect(within(progress).getByText('No audio sources')).toBeInTheDocument()
    expect(within(progress).getByText('No video sources')).toBeInTheDocument()
    expect(within(progress).getAllByText('No sources')).toHaveLength(2)
    expect(within(progress).queryByText('Not Started')).not.toBeInTheDocument()
  })

  it('refreshes detailed source artifacts when terminal polling reports COMPLETE', async () => {
    const documentOnly = [persistedSources[0]]
    const queued = {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', n2_is_current: true,
      n2_execution: {
        execution_id: 'N2-BBBBBBBBBBBBBBBB-001', status: 'QUEUED',
        input_sources: documentOnly,
        source_progress: [{
          source_id: 'DOC-001', processing_status: 'READY', preparation_status: 'READY', chunk_count: 0,
        }],
      },
    }
    const complete = {
      ...queued,
      n2_execution: {
        ...queued.n2_execution,
        status: 'COMPLETE',
        source_progress: [{
          source_id: 'DOC-001', processing_status: 'COMPLETE', preparation_status: 'COMPLETE', chunk_count: 1,
        }],
      },
    }
    listRequirementSources.mockResolvedValue({ data: documentOnly })
    getRequirementWorkflow
      .mockResolvedValueOnce({ data: queued })
      .mockResolvedValueOnce({ data: complete })
      .mockResolvedValue({ data: complete })
    getRequirementDocumentProcessingStatus
      .mockResolvedValueOnce(processingStatus('DOC-001', 'READY'))
      .mockResolvedValue(processingStatus('DOC-001', 'COMPLETED'))
    getRequirementPreparationStatus
      .mockResolvedValueOnce(preparationStatus('DOC-001', 'READY'))
      .mockResolvedValue(preparationStatus('DOC-001', 'COMPLETED'))
    getRequirementEvidenceChunks.mockResolvedValue(chunksFor('DOC-001'))

    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)

    await screen.findByText(/requirements\.pdf/)
    await waitFor(() => {
      expect(within(screen.getByLabelText('Extraction for requirements.pdf')).getByText('Complete')).toBeInTheDocument()
      expect(within(screen.getByLabelText('Evidence preparation for requirements.pdf')).getByText('Complete')).toBeInTheDocument()
    }, { timeout: 2500 })
    const documentCard = screen.getByText(/requirements\.pdf/).closest('[data-variant]')
    expect(within(documentCard).queryByText('Ready')).not.toBeInTheDocument()
    expect(getRequirementDocumentProcessingStatus).toHaveBeenCalledTimes(2)
    expect(getRequirementPreparationStatus).toHaveBeenCalledTimes(2)
    expect(getRequirementEvidenceChunks).toHaveBeenCalledWith('AGP-001', 'DOC-001')
    expect(continueRequirementN1).not.toHaveBeenCalled()
  })

  it('renders an integrity failure instead of READY when COMPLETE detail artifacts disagree', async () => {
    const documentOnly = [persistedSources[0]]
    listRequirementSources.mockResolvedValue({ data: documentOnly })
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', n2_is_current: true,
      n2_execution: {
        execution_id: 'N2-CCCCCCCCCCCCCCCC-001', status: 'COMPLETE',
        input_sources: documentOnly,
        source_progress: [{
          source_id: 'DOC-001', processing_status: 'COMPLETE', preparation_status: 'COMPLETE', chunk_count: 5,
        }],
      },
    } })

    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)

    expect(await screen.findByText(/Completed N2 processing could not be validated/)).toBeInTheDocument()
    expect(screen.getByText(/Completed N2 preparation could not be validated/)).toBeInTheDocument()
    expect(screen.queryByText('Ready')).not.toBeInTheDocument()
  })

  it('does not mark N2 complete when a persisted chunk result cannot be validated', async () => {
    getRequirementWorkflow.mockResolvedValue({ data: {
      selected_outputs: ['SRS'], n1_state: 'COMPLETE', n2_is_current: true,
      n2_execution: { execution_id: 'N2-AAAAAAAAAAAAAAAA-001', status: 'FAILED' },
    } })
    getRequirementDocumentProcessingStatus.mockResolvedValue(processingStatus('DOC-001', 'COMPLETED'))
    getRequirementAudioProcessingStatus.mockResolvedValue(processingStatus('AUD-001', 'COMPLETED'))
    getRequirementVideoProcessingStatus.mockResolvedValue(processingStatus('VID-001', 'COMPLETED'))
    getRequirementPreparationStatus.mockImplementation((_, sourceId) => (
      Promise.resolve(preparationStatus(sourceId, 'COMPLETED'))
    ))
    getRequirementEvidenceChunks.mockRejectedValue({ status: 404, errors: [{ message: 'Prepared evidence is unavailable.' }] })
    let snapshot
    render(
      <RequirementsWorkspace
        project={project}
        activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING}
        onPresentationChange={(value) => { snapshot = value }}
      />,
    )

    await waitFor(() => {
      expect(deriveRequirementsWorkflowPresentation(snapshot)[REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING].status).toBe('FAILED')
    })
    expect(await screen.findAllByText('Prepared evidence is unavailable.')).toHaveLength(3)
  })

  it('displays extraction and transcript results for every implemented modality', async () => {
    const user = userEvent.setup()
    getRequirementDocumentProcessingStatus.mockResolvedValue(processingStatus('DOC-001', 'COMPLETED'))
    getRequirementAudioProcessingStatus.mockResolvedValue(processingStatus('AUD-001', 'COMPLETED'))
    getRequirementVideoProcessingStatus.mockResolvedValue(processingStatus('VID-001', 'COMPLETED'))
    getRequirementDocumentProcessingResult.mockResolvedValue({ data: { source_id: 'DOC-001', text: 'Extracted client requirement.' } })
    getRequirementAudioProcessingResult.mockResolvedValue({ data: {
      source_id: 'AUD-001', transcript: 'Audio requirement.', detected_language: 'en', language_probability: 0.96,
      segments: [{ start_seconds: 0, end_seconds: 2.4, text: 'Audio requirement.' }],
    } })
    getRequirementVideoProcessingResult.mockResolvedValue({ data: {
      source_id: 'VID-001', transcript: 'Video requirement.', detected_language: 'en', language_probability: 0.94,
      processed_at: '2026-10-20T08:00:00Z', segments: [{ start_seconds: 1, end_seconds: 3.5, text: 'Video requirement.' }],
    } })
    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)
    const documentCard = (await screen.findByText(/DOC-001 · requirements.pdf/)).closest('[data-variant]')
    const audioCard = screen.getByText(/AUD-001 · interview.mp3/).closest('[data-variant]')
    const videoCard = screen.getByText(/VID-001 · workflow.mp4/).closest('[data-variant]')

    await user.click(within(documentCard).getByRole('button', { name: 'View Extraction' }))
    await user.click(within(audioCard).getByRole('button', { name: 'View Transcript' }))
    await user.click(within(videoCard).getByRole('button', { name: 'View Transcript' }))
    expect(await within(documentCard).findByText('Extracted client requirement.')).toBeInTheDocument()
    expect(await within(audioCard).findAllByText('Audio requirement.')).toHaveLength(2)
    expect(within(audioCard).getByText('0:00.00–0:02.40')).toBeInTheDocument()
    expect(await within(videoCard).findAllByText('Video requirement.')).toHaveLength(2)
    expect(within(videoCard).getByText('0:01.00–0:03.50')).toBeInTheDocument()
  })

  it('prepares evidence, persists the action state, and shows chunk provenance', async () => {
    const user = userEvent.setup()
    getRequirementDocumentProcessingStatus.mockResolvedValue(processingStatus('DOC-001', 'COMPLETED'))
    prepareRequirementEvidence.mockResolvedValue(preparationStatus('DOC-001', 'COMPLETED'))
    getRequirementEvidenceChunks.mockResolvedValue(chunksFor('DOC-001', 'DOCUMENT', [{
      parent_start_offset: 10,
      parent_end_offset: 42,
      page_numbers: [2],
      document_blocks: [{ block_index: 3, block_type: 'TABLE' }],
      media_segments: [],
    }]))
    getNormalizedRequirementEvidence.mockResolvedValue({ data: {
      source_id: 'DOC-001', normalized_text: 'The client needs secure access.',
    } })
    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)
    const documentCard = (await screen.findByText(/DOC-001 · requirements.pdf/)).closest('[data-variant]')

    await user.click(within(documentCard).getByRole('button', { name: 'Prepare Evidence' }))
    expect(prepareRequirementEvidence).toHaveBeenCalledWith('AGP-001', 'DOC-001', { force: false })
    expect(await within(documentCard).findByRole('button', { name: 'View Prepared Evidence' })).toBeInTheDocument()
    await user.click(within(documentCard).getByRole('button', { name: 'View Prepared Evidence' }))

    expect(await within(documentCard).findByText('The client needs secure access.')).toBeInTheDocument()
    expect(within(documentCard).getByText(/CHK-DOC001/)).toBeInTheDocument()
    expect(within(documentCard).getByText('Pages')).toBeInTheDocument()
    expect(within(documentCard).getByText('2')).toBeInTheDocument()
    expect(within(documentCard).getByText('3 (Table)')).toBeInTheDocument()
    expect(within(documentCard).getByText('10-42')).toBeInTheDocument()
  })

  it('shows audio/video timestamp provenance from persisted prepared evidence', async () => {
    const user = userEvent.setup()
    getRequirementAudioProcessingStatus.mockResolvedValue(processingStatus('AUD-001', 'COMPLETED'))
    getRequirementPreparationStatus.mockImplementation((_, sourceId) => Promise.resolve(
      preparationStatus(sourceId, sourceId === 'AUD-001' ? 'COMPLETED' : 'READY'),
    ))
    getRequirementEvidenceChunks.mockResolvedValue(chunksFor('AUD-001', 'AUDIO', [{
      parent_start_offset: 0,
      parent_end_offset: 26,
      page_numbers: [],
      document_blocks: [],
      media_segments: [{ segment_index: 0, start_seconds: 4, end_seconds: 7.25 }],
    }]))
    getNormalizedRequirementEvidence.mockResolvedValue({ data: {
      source_id: 'AUD-001', normalized_text: 'Appointment reminders are required.',
    } })
    render(<RequirementsWorkspace project={project} activeSection={REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING} />)
    const audioCard = (await screen.findByText(/AUD-001 · interview.mp3/)).closest('[data-variant]')

    await user.click(await within(audioCard).findByRole('button', { name: 'View Prepared Evidence' }))
    expect(await within(audioCard).findByText('Segments')).toBeInTheDocument()
    expect(within(audioCard).getByText('0:04.00–0:07.25')).toBeInTheDocument()
    expect(within(audioCard).getByText('AUD-001 · Audio')).toBeInTheDocument()
  })
})
