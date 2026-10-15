import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteImplementationInputFile,
  uploadImplementationInputFile,
} from './implementationAgentService.js'
import ImplementationWorkspace from './ImplementationWorkspace.jsx'

vi.mock('./implementationAgentService.js', () => ({
  uploadImplementationInputFile: vi.fn(),
  deleteImplementationInputFile: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-003', agent_type: 'IMPLEMENTATION',
  name: 'BookEase Builder', domain: 'Hospitality',
}

const outputLabels = [
  'Project Structure', 'Frontend Code', 'Backend Code',
  'Database Implementation', 'API Implementation', 'Configuration Files',
  'Container Configuration', 'Git Summary',
]

function metadata(overrides = {}) {
  return {
    upload_id: 'A3UP-0123456789abcdef0123456789abcdef',
    source_type: 'DOCUMENT',
    artifact_type: 'API_SPECIFICATION',
    label: 'Booking API',
    original_filename: 'bookease-api.pdf',
    mime_type: 'application/pdf',
    extension: '.pdf',
    size_bytes: 250880,
    sha256: 'a'.repeat(64),
    created_at: '2026-10-15T10:00:00Z',
    ...overrides,
  }
}

async function chooseSource(user, sourceType) {
  await user.selectOptions(screen.getByLabelText(/Input Source/), sourceType)
}

async function attachFile(user, sourceType, file, responseMetadata) {
  uploadImplementationInputFile.mockResolvedValue({ data: responseMetadata })
  await chooseSource(user, sourceType)
  const picker = screen.getByLabelText(sourceType === 'DOCUMENT' ? /Document file/ : /Image file/)
  await user.upload(picker, file)
  await user.click(screen.getByRole('button', { name: 'Attach File' }))
  await screen.findByText('Uploaded / Attached')
}

describe('ImplementationWorkspace', () => {
  beforeEach(() => vi.clearAllMocks())

  it('preserves TEXT input, exact outputs, review, and no execution behavior', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await user.type(screen.getByLabelText(/Content/), '  Build a booking API.  ')
    await user.click(screen.getByRole('button', { name: 'Next' }))

    outputLabels.forEach((label) => {
      expect(screen.getByRole('checkbox', { name: label })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('checkbox', { name: 'Backend Code' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    expect(screen.getByText('BookEase Builder')).toBeInTheDocument()
    expect(screen.getByText('Hospitality')).toBeInTheDocument()
    expect(screen.getByText('Build a booking API.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Workspace Ready' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
    expect(uploadImplementationInputFile).not.toHaveBeenCalled()
  })

  it('enables DOCUMENT and IMAGE with their controlled accept lists', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    const source = screen.getByLabelText(/Input Source/)
    expect(within(source).getByRole('option', { name: 'Document' })).toBeEnabled()
    expect(within(source).getByRole('option', { name: 'Image' })).toBeEnabled()

    await chooseSource(user, 'DOCUMENT')
    expect(screen.getByLabelText(/Document file/)).toHaveAttribute(
      'accept', '.pdf,.docx,.txt,.md,.json,.yaml,.yml',
    )
    await chooseSource(user, 'IMAGE')
    expect(screen.getByLabelText(/Image file/)).toHaveAttribute(
      'accept', '.png,.jpg,.jpeg,.webp',
    )
  })

  it.each([
    {
      sourceType: 'DOCUMENT',
      artifact: 'API_SPECIFICATION',
      file: new File(['%PDF-test'], 'bookease-api.pdf', { type: 'application/pdf' }),
      result: metadata(),
    },
    {
      sourceType: 'IMAGE',
      artifact: 'UI_WIREFRAMES',
      file: new File(['png'], 'booking.png', { type: 'image/png' }),
      result: metadata({
        source_type: 'IMAGE', artifact_type: 'UI_WIREFRAMES',
        original_filename: 'booking.png', mime_type: 'image/png',
        extension: '.png', size_bytes: 2048,
      }),
    },
  ])('uploads and reviews real $sourceType metadata', async ({ sourceType, artifact, file, result }) => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await user.selectOptions(screen.getByLabelText(/Artifact Type/), artifact)
    await user.type(screen.getByLabelText('Label (optional)'), 'Booking API')
    await attachFile(user, sourceType, file, result)

    expect(uploadImplementationInputFile).toHaveBeenCalledWith('AGP-003', {
      source_type: sourceType,
      artifact_type: artifact,
      label: 'Booking API',
      file,
    })
    expect(screen.getByText(result.original_filename)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(result.mime_type))).toBeInTheDocument()
    expect(screen.getByLabelText(/Input Source/)).toBeDisabled()
    expect(screen.getByText(/Remove this uploaded input before changing/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Project Structure' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    expect(screen.getByText(new RegExp(`Uploaded / Attached — ${result.original_filename}`))).toBeInTheDocument()
    expect(screen.queryByText(/Analyzed|Processed by AI|Understood/)).not.toBeInTheDocument()
  })

  it('shows upload loading and backend validation failures honestly', async () => {
    const user = userEvent.setup()
    let rejectUpload
    uploadImplementationInputFile.mockReturnValue(new Promise((_, reject) => { rejectUpload = reject }))
    render(<ImplementationWorkspace project={project} />)
    await chooseSource(user, 'DOCUMENT')
    await user.upload(
      screen.getByLabelText(/Document file/),
      new File(['large'], 'large.pdf', { type: 'application/pdf' }),
    )
    await user.click(screen.getByRole('button', { name: 'Attach File' }))
    expect(screen.getByRole('button', { name: 'Uploading file' })).toBeDisabled()
    rejectUpload({ errors: [{ message: 'DOCUMENT files must not exceed 10 MB' }] })
    expect(await screen.findByRole('alert')).toHaveTextContent('must not exceed 10 MB')
    expect(screen.queryByText('Uploaded / Attached')).not.toBeInTheDocument()
  })

  it('deletes an uploaded file before removing it locally', async () => {
    const user = userEvent.setup()
    deleteImplementationInputFile.mockResolvedValue({ data: { upload_id: metadata().upload_id } })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    await user.click(screen.getByRole('button', { name: 'Remove Input' }))
    expect(deleteImplementationInputFile).toHaveBeenCalledWith('AGP-003', metadata().upload_id)
    expect(screen.queryByText('bookease-api.pdf')).not.toBeInTheDocument()
  })

  it('retains an uploaded input and reports an error when deletion fails', async () => {
    const user = userEvent.setup()
    deleteImplementationInputFile.mockRejectedValue({
      errors: [{ message: 'Staged upload could not be deleted' }],
    })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    await user.click(screen.getByRole('button', { name: 'Remove Input' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be deleted')
    expect(screen.getByText('bookease-api.pdf')).toBeInTheDocument()
    expect(screen.getByLabelText(/Input Source/)).toBeDisabled()
  })

  it('validates incomplete inputs and keeps GitHub disabled', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await chooseSource(user, 'IMAGE')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('attach a file')
    expect(screen.getByRole('button', { name: 'Connect GitHub' })).toBeDisabled()
    expect(screen.getByText(/GitHub account connection will be enabled/i)).toBeInTheDocument()
  })
})
