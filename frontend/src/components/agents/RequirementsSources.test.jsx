import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runRequirementsAgent } from '../../services/requirementsAgentService.js'
import {
  deleteRequirementSource,
  getRequirementSources,
  uploadRequirementSources,
  processRequirementSources,
} from '../../services/requirementSourcesService.js'
import RequirementsWorkspace from './RequirementsWorkspace.jsx'

vi.mock('../../services/requirementsAgentService.js', () => ({
  runRequirementsAgent: vi.fn(),
}))

vi.mock('../../services/requirementSourcesService.js', () => ({
  getRequirementSources: vi.fn(),
  uploadRequirementSources: vi.fn(),
  deleteRequirementSource: vi.fn(),
  processRequirementSources: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-001',
  agent_type: 'REQUIREMENTS',
  name: 'BookEase',
  domain: 'Library',
}

const mockSources = [
  {
    source_id: 'DOC-001',
    agent_project_id: 'AGP-001',
    source_type: 'DOCUMENT',
    original_filename: 'requirements.pdf',
    file_size: 10240,
    processing_status: 'READY',
    created_at: '2026-10-17T12:00:00Z',
  },
  {
    source_id: 'DOC-002',
    agent_project_id: 'AGP-001',
    source_type: 'DOCUMENT',
    original_filename: 'existing-process.docx',
    file_size: 20480,
    processing_status: 'READY',
    created_at: '2026-10-17T12:01:00Z',
  },
  {
    source_id: 'AUD-001',
    agent_project_id: 'AGP-001',
    source_type: 'AUDIO',
    original_filename: 'client-interview.mp3',
    file_size: 512000,
    processing_status: 'READY',
    created_at: '2026-10-17T12:02:00Z',
  },
  {
    source_id: 'VID-001',
    agent_project_id: 'AGP-001',
    source_type: 'VIDEO',
    original_filename: 'booking-workflow.mp4',
    file_size: 1048576,
    processing_status: 'READY',
    created_at: '2026-10-17T12:03:00Z',
  },
]

describe('RequirementsWorkspace - Client Requirement Sources (Step 1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRequirementSources.mockResolvedValue({ data: [] })
    uploadRequirementSources.mockResolvedValue({ data: [] })
    deleteRequirementSource.mockResolvedValue({ data: null })
    processRequirementSources.mockResolvedValue({ data: [] })
  })

  it('1: Client Requirement Sources section renders', async () => {
    render(<RequirementsWorkspace project={project} />)
    expect(
      await screen.findByRole('heading', { name: 'Client Requirement Sources' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('At least one requirement source is required.'),
    ).toBeInTheDocument()
  })

  it('2, 3 & 4: Document, Audio, and Video upload options exist with proper file types', async () => {
    render(<RequirementsWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Client Requirement Sources' })

    expect(screen.getByRole('button', { name: 'Add Documents' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Audio' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Video' })).toBeInTheDocument()

    const docInput = screen.getByTestId('document-file-input')
    const audioInput = screen.getByTestId('audio-file-input')
    const videoInput = screen.getByTestId('video-file-input')

    expect(docInput).toHaveAttribute('accept', '.pdf,.docx,.txt')
    expect(audioInput).toHaveAttribute('accept', '.mp3,.wav,.m4a')
    expect(videoInput).toHaveAttribute('accept', '.mp4,.mov,.webm')
  })

  it('5, 6 & 7: Multiple sources and mixed types are rendered with ID, type, filename, and status', async () => {
    getRequirementSources.mockResolvedValue({ data: mockSources })
    render(<RequirementsWorkspace project={project} />)

    expect(await screen.findByText('DOC-001')).toBeInTheDocument()
    expect(screen.getByText('DOC-002')).toBeInTheDocument()
    expect(screen.getByText('AUD-001')).toBeInTheDocument()
    expect(screen.getByText('VID-001')).toBeInTheDocument()

    expect(screen.getByText('requirements.pdf')).toBeInTheDocument()
    expect(screen.getByText('existing-process.docx')).toBeInTheDocument()
    expect(screen.getByText('client-interview.mp3')).toBeInTheDocument()
    expect(screen.getByText('booking-workflow.mp4')).toBeInTheDocument()

    expect(screen.getAllByText('Document').length).toBe(2)
    expect(screen.getByText('Audio')).toBeInTheDocument()
    expect(screen.getByText('Video')).toBeInTheDocument()

    const readyBadges = screen.getAllByText('Ready')
    expect(readyBadges.length).toBe(4)
  })

  it('8: At least one source is required to continue', async () => {
    const user = userEvent.setup()
    getRequirementSources.mockResolvedValue({ data: [] })
    render(<RequirementsWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Client Requirement Sources' })

    // When empty, clicking Next shows validation errors and prevents advancing
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getAllByText('At least one requirement source is required.').length).toBeGreaterThan(0)
    expect(screen.queryByRole('checkbox', { name: /functional requirements/i })).not.toBeInTheDocument()

    // Now upload a source
    uploadRequirementSources.mockResolvedValue({
      data: [{ ...mockSources[0], processing_status: 'COMPLETED' }],
    })
    const docInput = screen.getByTestId('document-file-input')
    const file = new File(['content'], 'requirements.pdf', { type: 'application/pdf' })
    await user.upload(docInput, file)

    expect(await screen.findByText('DOC-001')).toBeInTheDocument()

    // Now clicking Next successfully advances to Select Outputs step
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Select outputs')).toBeInTheDocument()
  })

  it('9: User can add more inputs and upload files via action buttons', async () => {
    const user = userEvent.setup()
    getRequirementSources.mockResolvedValue({ data: [mockSources[0]] })
    uploadRequirementSources.mockResolvedValue({
      data: [mockSources[2]], // AUD-001
    })

    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('DOC-001')).toBeInTheDocument()

    // "Add More" button exists when sources exist
    expect(screen.getByRole('button', { name: 'Add More' })).toBeInTheDocument()

    // Upload audio file
    const audioInput = screen.getByTestId('audio-file-input')
    const audioFile = new File(['audio'], 'client-interview.mp3', { type: 'audio/mpeg' })
    await user.upload(audioInput, audioFile)

    expect(uploadRequirementSources).toHaveBeenCalledWith(
      'AGP-001',
      [audioFile],
      'AUDIO',
    )
    expect(await screen.findByText('AUD-001')).toBeInTheDocument()
  })

  it('10: Existing sources remain visible after reload through getRequirementSources', async () => {
    getRequirementSources.mockResolvedValue({ data: mockSources })
    const { unmount } = render(<RequirementsWorkspace project={project} />)

    expect(await screen.findByText('DOC-001')).toBeInTheDocument()
    expect(getRequirementSources).toHaveBeenCalledWith('AGP-001')

    unmount()

    // Simulate page reload
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('DOC-001')).toBeInTheDocument()
    expect(screen.getByText('VID-001')).toBeInTheDocument()
    expect(getRequirementSources).toHaveBeenCalledTimes(2)
  })

  it('11: Uploading sources does NOT call the Agent 1 /run endpoint', async () => {
    const user = userEvent.setup()
    getRequirementSources.mockResolvedValue({ data: [] })
    uploadRequirementSources.mockResolvedValue({ data: [mockSources[0]] })

    render(<RequirementsWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Client Requirement Sources' })

    const docInput = screen.getByTestId('document-file-input')
    const file = new File(['doc'], 'requirements.pdf', { type: 'application/pdf' })
    await user.upload(docInput, file)

    expect(await screen.findByText('DOC-001')).toBeInTheDocument()
    expect(runRequirementsAgent).not.toHaveBeenCalled()
  })

  it('12: Removing a source calls deleteRequirementSource and updates UI', async () => {
    const user = userEvent.setup()
    getRequirementSources.mockResolvedValue({ data: [mockSources[0]] })
    deleteRequirementSource.mockResolvedValue({ data: null })

    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('DOC-001')).toBeInTheDocument()

    const removeBtn = screen.getByRole('button', { name: 'Remove source DOC-001' })
    await user.click(removeBtn)

    expect(deleteRequirementSource).toHaveBeenCalledWith('AGP-001', 'DOC-001')
    await waitFor(() => {
      expect(screen.queryByText('DOC-001')).not.toBeInTheDocument()
    })
    expect(screen.getByText('At least one requirement source is required.')).toBeInTheDocument()
  })

  it('processes sources without calling the Agent 1 run endpoint and reloads completed state', async () => {
    const user = userEvent.setup()
    getRequirementSources
      .mockResolvedValueOnce({ data: [mockSources[0]] })
      .mockResolvedValueOnce({
        data: [{ ...mockSources[0], processing_status: 'COMPLETED' }],
      })
    processRequirementSources.mockResolvedValue({ data: [] })

    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('Ready')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Process Sources' }))

    await waitFor(() => {
      expect(processRequirementSources).toHaveBeenCalledWith('AGP-001')
      expect(screen.getByText('Completed')).toBeInTheDocument()
    })
    expect(getRequirementSources).toHaveBeenCalledTimes(2)
    expect(runRequirementsAgent).not.toHaveBeenCalled()
  })

  it('renders a persisted safe source processing failure', async () => {
    getRequirementSources.mockResolvedValue({
      data: [{
        ...mockSources[0],
        processing_status: 'FAILED',
        processing_error_code: 'NO_EXTRACTABLE_TEXT',
        processing_error_message: 'No usable text could be extracted.',
      }],
    })
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('No usable text could be extracted.')).toBeInTheDocument()
  })

  it('renders Audio Completed after processing', async () => {
    getRequirementSources.mockResolvedValue({
      data: [{ ...mockSources[2], processing_status: 'COMPLETED' }],
    })
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('Audio')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })

  it('renders a safe Audio Failed message', async () => {
    getRequirementSources.mockResolvedValue({
      data: [{
        ...mockSources[2],
        processing_status: 'FAILED',
        processing_error_code: 'AUDIO_TRANSCRIPTION_FAILED',
        processing_error_message: 'The audio source could not be transcribed.',
      }],
    })
    render(<RequirementsWorkspace project={project} />)
    expect(await screen.findByText('Audio')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('The audio source could not be transcribed.')).toBeInTheDocument()
  })
})
