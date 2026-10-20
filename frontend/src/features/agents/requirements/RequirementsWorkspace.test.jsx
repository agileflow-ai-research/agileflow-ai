import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteRequirementSource,
  listRequirementSources,
  runRequirementsAgent,
  uploadRequirementSource,
} from './requirementsAgentService.js'
import RequirementsWorkspace from './RequirementsWorkspace.jsx'

vi.mock('./requirementsAgentService.js', () => ({
  deleteRequirementSource: vi.fn(),
  listRequirementSources: vi.fn(),
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
    expect(screen.getAllByText('Ready')).toHaveLength(3)
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
})
