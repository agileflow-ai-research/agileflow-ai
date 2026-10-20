import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteRequirementSource,
  getRequirementAudioProcessingResult,
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingResult,
  getRequirementDocumentProcessingStatus,
  getRequirementVideoProcessingResult,
  getRequirementVideoProcessingStatus,
  listRequirementSources,
  processRequirementDocument,
  processRequirementAudio,
  processRequirementVideo,
  runRequirementsAgent,
  uploadRequirementSource,
} from './requirementsAgentService.js'
import RequirementsWorkspace from './RequirementsWorkspace.jsx'

vi.mock('./requirementsAgentService.js', () => ({
  deleteRequirementSource: vi.fn(),
  getRequirementAudioProcessingResult: vi.fn(),
  getRequirementAudioProcessingStatus: vi.fn(),
  getRequirementDocumentProcessingResult: vi.fn(),
  getRequirementDocumentProcessingStatus: vi.fn(),
  getRequirementVideoProcessingResult: vi.fn(),
  getRequirementVideoProcessingStatus: vi.fn(),
  listRequirementSources: vi.fn(),
  processRequirementDocument: vi.fn(),
  processRequirementAudio: vi.fn(),
  processRequirementVideo: vi.fn(),
  runRequirementsAgent: vi.fn(),
  uploadRequirementSource: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-001', agent_type: 'REQUIREMENTS', name: 'BookEase', domain: 'Library',
}
const persistedSources = [
  { source_id: 'DOC-001', source_type: 'DOCUMENT', original_filename: 'requirements.pdf', status: 'READY' },
  { source_id: 'AUD-001', source_type: 'AUDIO', original_filename: 'interview.mp3', status: 'READY' },
  { source_id: 'VID-001', source_type: 'VIDEO', original_filename: 'workflow.mp4', status: 'READY' },
]

describe('RequirementsWorkspace Node 1', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRequirementSources.mockResolvedValue({ data: persistedSources })
    getRequirementDocumentProcessingStatus.mockResolvedValue({ data: {
      source_id: 'DOC-001', status: 'READY', error: null,
    } })
    getRequirementAudioProcessingStatus.mockResolvedValue({ data: {
      source_id: 'AUD-001', status: 'READY', error: null,
    } })
    getRequirementVideoProcessingStatus.mockResolvedValue({ data: {
      source_id: 'VID-001', status: 'READY', error: null,
    } })
  })

  it('renders actions and persisted IDs, types, filenames, and statuses', async () => {
    render(<RequirementsWorkspace project={project} />)
    expect(screen.getByRole('heading', { name: 'Client Requirement Sources' })).toBeInTheDocument()
    ;['Add Documents', 'Add Audio', 'Add Video'].forEach((label) => {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    })
    expect(await screen.findByText('DOC-001')).toBeInTheDocument()
    ;['AUD-001', 'VID-001', 'Document', 'Audio', 'Video', 'requirements.pdf', 'interview.mp3', 'workflow.mp4'].forEach((text) => {
      expect(screen.getByText(text)).toBeInTheDocument()
    })
    expect(screen.getAllByText('Ready').length).toBeGreaterThanOrEqual(3)
    expect(listRequirementSources).toHaveBeenCalledWith('AGP-001')
    expect(runRequirementsAgent).not.toHaveBeenCalled()
  })

  it('uploads multiple files and mixed source types without calling a run endpoint', async () => {
    const user = userEvent.setup()
    listRequirementSources.mockResolvedValue({ data: [] })
    uploadRequirementSource
      .mockResolvedValueOnce({ data: { source_id: 'DOC-001', source_type: 'DOCUMENT', original_filename: 'one.pdf', status: 'READY' } })
      .mockResolvedValueOnce({ data: { source_id: 'DOC-002', source_type: 'DOCUMENT', original_filename: 'two.txt', status: 'READY' } })
      .mockResolvedValueOnce({ data: { source_id: 'AUD-001', source_type: 'AUDIO', original_filename: 'call.mp3', status: 'READY' } })
    render(<RequirementsWorkspace project={project} />)
    await screen.findByText('No requirement sources uploaded yet.')
    const one = new File(['pdf'], 'one.pdf', { type: 'application/pdf' })
    const two = new File(['notes'], 'two.txt', { type: 'text/plain' })
    await user.upload(screen.getByLabelText('Document files'), [one, two])
    const audio = new File(['audio'], 'call.mp3', { type: 'audio/mpeg' })
    await user.upload(screen.getByLabelText('Audio files'), audio)

    await waitFor(() => expect(uploadRequirementSource).toHaveBeenCalledTimes(3))
    expect(uploadRequirementSource).toHaveBeenNthCalledWith(1, 'AGP-001', 'DOCUMENT', one)
    expect(uploadRequirementSource).toHaveBeenNthCalledWith(2, 'AGP-001', 'DOCUMENT', two)
    expect(uploadRequirementSource).toHaveBeenNthCalledWith(3, 'AGP-001', 'AUDIO', audio)
    expect(await screen.findByText('DOC-002')).toBeInTheDocument()
    expect(screen.getByText('AUD-001')).toBeInTheDocument()
    expect(runRequirementsAgent).not.toHaveBeenCalled()
  })

  it('removes a source and reloads persisted sources when remounted', async () => {
    const user = userEvent.setup()
    deleteRequirementSource.mockResolvedValue({ data: { source_id: 'DOC-001' } })
    const firstView = render(<RequirementsWorkspace project={project} />)
    await screen.findByText('DOC-001')
    await user.click(screen.getAllByRole('button', { name: 'Remove' })[0])
    await waitFor(() => expect(screen.queryByText('DOC-001')).not.toBeInTheDocument())
    expect(deleteRequirementSource).toHaveBeenCalledWith('AGP-001', 'DOC-001')
    firstView.unmount()

    listRequirementSources.mockResolvedValue({ data: persistedSources.slice(1) })
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('AUD-001')).toBeInTheDocument()
    expect(screen.queryByText('DOC-001')).not.toBeInTheDocument()
    expect(listRequirementSources).toHaveBeenCalledTimes(2)
  })

  it('shows persisted processing state after reload and loads the extracted result', async () => {
    const user = userEvent.setup()
    getRequirementDocumentProcessingStatus.mockResolvedValue({ data: {
      source_id: 'DOC-001', status: 'COMPLETED', error: null,
    } })
    getRequirementDocumentProcessingResult.mockResolvedValue({ data: {
      source_id: 'DOC-001', document_type: 'PDF', text: 'Persisted extracted requirement',
    } })
    render(<RequirementsWorkspace project={project} />)

    expect(await screen.findByText('Completed')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'View Result' }))

    expect(await screen.findByText('Persisted extracted requirement')).toBeInTheDocument()
    expect(getRequirementDocumentProcessingResult).toHaveBeenCalledWith('AGP-001', 'DOC-001')
  })

  it('shows processing immediately and completes document processing', async () => {
    const user = userEvent.setup()
    let finishProcessing
    processRequirementDocument.mockReturnValue(new Promise((resolve) => { finishProcessing = resolve }))
    render(<RequirementsWorkspace project={project} />)
    await screen.findByRole('button', { name: 'Process Document' })

    await user.click(screen.getByRole('button', { name: 'Process Document' }))
    expect(screen.getByText('Processing')).toBeInTheDocument()
    finishProcessing({ data: { source_id: 'DOC-001', status: 'COMPLETED', error: null } })

    expect(await screen.findByText('Completed')).toBeInTheDocument()
    expect(processRequirementDocument).toHaveBeenCalledWith('AGP-001', 'DOC-001', { force: false })
    expect(runRequirementsAgent).not.toHaveBeenCalled()
  })

  it('shows safe failure details and retries with force', async () => {
    const user = userEvent.setup()
    getRequirementDocumentProcessingStatus.mockResolvedValue({ data: {
      source_id: 'DOC-001', status: 'FAILED',
      error: { code: 'NO_MACHINE_READABLE_TEXT', message: 'OCR is not available in N2A.' },
    } })
    processRequirementDocument.mockResolvedValue({ data: {
      source_id: 'DOC-001', status: 'COMPLETED', error: null,
    } })
    render(<RequirementsWorkspace project={project} />)

    expect(await screen.findByText('Failed')).toBeInTheDocument()
    expect(screen.getByText(/NO_MACHINE_READABLE_TEXT/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry Processing' }))

    expect(processRequirementDocument).toHaveBeenCalledWith('AGP-001', 'DOC-001', { force: true })
    expect(await screen.findByText('Completed')).toBeInTheDocument()
  })

  it('reloads audio state, reprocesses, and displays transcript metadata and segments', async () => {
    const user = userEvent.setup()
    getRequirementAudioProcessingStatus.mockResolvedValue({ data: {
      source_id: 'AUD-001', status: 'COMPLETED', error: null,
    } })
    getRequirementAudioProcessingResult.mockResolvedValue({ data: {
      source_id: 'AUD-001',
      transcript: 'The client needs appointment reminders.',
      detected_language: 'en',
      language_probability: 0.96,
      segments: [
        { start_seconds: 0, end_seconds: 2.4, text: 'The client needs appointment reminders.' },
      ],
    } })
    processRequirementAudio.mockResolvedValue({ data: {
      source_id: 'AUD-001', status: 'COMPLETED', error: null,
    } })
    render(<RequirementsWorkspace project={project} />)

    const audioCard = (await screen.findByText('AUD-001')).closest('[data-variant]')
    expect(within(audioCard).getByText('Completed')).toBeInTheDocument()
    await user.click(within(audioCard).getByRole('button', { name: 'View Transcript' }))

    await waitFor(() => {
      expect(within(audioCard).getAllByText('The client needs appointment reminders.')).toHaveLength(2)
    })
    expect(within(audioCard).getByText('Detected language: en (96%)')).toBeInTheDocument()
    expect(within(audioCard).getByText('0:00.00–0:02.40')).toBeInTheDocument()
    expect(getRequirementAudioProcessingResult).toHaveBeenCalledWith('AGP-001', 'AUD-001')

    await user.click(within(audioCard).getByRole('button', { name: 'Reprocess' }))
    expect(processRequirementAudio).toHaveBeenCalledWith('AGP-001', 'AUD-001', { force: true })
    expect(runRequirementsAgent).not.toHaveBeenCalled()
  })

  it('shows audio failure and retries using the audio processor', async () => {
    const user = userEvent.setup()
    getRequirementAudioProcessingStatus.mockResolvedValue({ data: {
      source_id: 'AUD-001', status: 'FAILED',
      error: { code: 'AUDIO_UNREADABLE', message: 'The audio source could not be decoded safely.' },
    } })
    processRequirementAudio.mockResolvedValue({ data: {
      source_id: 'AUD-001', status: 'COMPLETED', error: null,
    } })
    render(<RequirementsWorkspace project={project} />)

    const audioCard = (await screen.findByText('AUD-001')).closest('[data-variant]')
    expect(within(audioCard).getByText(/AUDIO_UNREADABLE/)).toBeInTheDocument()
    await user.click(within(audioCard).getByRole('button', { name: 'Retry' }))

    expect(processRequirementAudio).toHaveBeenCalledWith('AGP-001', 'AUD-001', { force: true })
    expect(await within(audioCard).findByText('Completed')).toBeInTheDocument()
  })

  it('shows audio processing immediately before the request completes', async () => {
    const user = userEvent.setup()
    let finishProcessing
    processRequirementAudio.mockReturnValue(new Promise((resolve) => { finishProcessing = resolve }))
    render(<RequirementsWorkspace project={project} />)

    const audioCard = (await screen.findByText('AUD-001')).closest('[data-variant]')
    await user.click(within(audioCard).getByRole('button', { name: 'Process Audio' }))
    expect(within(audioCard).getByText('Processing')).toBeInTheDocument()

    finishProcessing({ data: { source_id: 'AUD-001', status: 'COMPLETED', error: null } })
    expect(await within(audioCard).findByText('Completed')).toBeInTheDocument()
    expect(processRequirementAudio).toHaveBeenCalledWith('AGP-001', 'AUD-001', { force: false })
  })

  it('shows video processing immediately before the request completes', async () => {
    const user = userEvent.setup()
    let finishProcessing
    processRequirementVideo.mockReturnValue(new Promise((resolve) => { finishProcessing = resolve }))
    render(<RequirementsWorkspace project={project} />)

    const videoCard = (await screen.findByText('VID-001')).closest('[data-variant]')
    await user.click(within(videoCard).getByRole('button', { name: 'Process Video' }))
    expect(within(videoCard).getByText('Processing')).toBeInTheDocument()

    finishProcessing({ data: { source_id: 'VID-001', status: 'COMPLETED', error: null } })
    expect(await within(videoCard).findByText('Completed')).toBeInTheDocument()
    expect(processRequirementVideo).toHaveBeenCalledWith('AGP-001', 'VID-001', { force: false })
  })

  it('reloads completed video state and displays the persisted transcript result', async () => {
    const user = userEvent.setup()
    getRequirementVideoProcessingStatus.mockResolvedValue({ data: {
      source_id: 'VID-001', status: 'COMPLETED', error: null,
    } })
    getRequirementVideoProcessingResult.mockResolvedValue({ data: {
      source_id: 'VID-001',
      transcript: 'The workflow demonstration includes approval.',
      detected_language: 'en',
      language_probability: 0.94,
      processed_at: '2026-10-20T08:00:00Z',
      segments: [
        { start_seconds: 0, end_seconds: 1, text: 'The workflow demonstration' },
        { start_seconds: 1, end_seconds: 2.5, text: ' includes approval.' },
      ],
    } })
    processRequirementVideo.mockResolvedValue({ data: {
      source_id: 'VID-001', status: 'COMPLETED', error: null,
    } })
    render(<RequirementsWorkspace project={project} />)

    const videoCard = (await screen.findByText('VID-001')).closest('[data-variant]')
    expect(within(videoCard).getByText('Completed')).toBeInTheDocument()
    await user.click(within(videoCard).getByRole('button', { name: 'View Transcript' }))

    expect(await within(videoCard).findByText('The workflow demonstration includes approval.')).toBeInTheDocument()
    expect(within(videoCard).getByText('Detected language: en (94%)')).toBeInTheDocument()
    expect(within(videoCard).getByText(/2 timestamped segments/)).toBeInTheDocument()
    expect(getRequirementVideoProcessingResult).toHaveBeenCalledWith('AGP-001', 'VID-001')
    await user.click(within(videoCard).getByRole('button', { name: 'Reprocess' }))
    expect(processRequirementVideo).toHaveBeenCalledWith('AGP-001', 'VID-001', { force: true })
  })

  it('shows video failure and retries through the shared processing API', async () => {
    const user = userEvent.setup()
    getRequirementVideoProcessingStatus.mockResolvedValue({ data: {
      source_id: 'VID-001', status: 'FAILED',
      error: { code: 'VIDEO_NO_AUDIO_TRACK', message: 'The video does not contain a usable audio track.' },
    } })
    processRequirementVideo.mockResolvedValue({ data: {
      source_id: 'VID-001', status: 'COMPLETED', error: null,
    } })
    render(<RequirementsWorkspace project={project} />)

    const videoCard = (await screen.findByText('VID-001')).closest('[data-variant]')
    expect(within(videoCard).getByText(/VIDEO_NO_AUDIO_TRACK/)).toBeInTheDocument()
    await user.click(within(videoCard).getByRole('button', { name: 'Retry' }))

    expect(processRequirementVideo).toHaveBeenCalledWith('AGP-001', 'VID-001', { force: true })
    expect(await within(videoCard).findByText('Completed')).toBeInTheDocument()
  })
})
