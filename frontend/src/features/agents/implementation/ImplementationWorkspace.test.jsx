import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  connectGitHub,
  createGitHubRepository,
  deleteImplementationInputFile,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentExtraction,
  getGitHubRepository,
  uploadImplementationInputFile,
} from './implementationAgentService.js'
import { navigateToGitHub } from './githubNavigation.js'
import ImplementationWorkspace from './ImplementationWorkspace.jsx'

vi.mock('./implementationAgentService.js', () => ({
  uploadImplementationInputFile: vi.fn(),
  deleteImplementationInputFile: vi.fn(),
  extractImplementationDocument: vi.fn(),
  getImplementationDocumentExtraction: vi.fn(),
  connectGitHub: vi.fn(),
  createGitHubRepository: vi.fn(),
  getGitHubConnection: vi.fn(),
  getGitHubRepository: vi.fn(),
}))
vi.mock('./githubNavigation.js', () => ({ navigateToGitHub: vi.fn() }))

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

function connectedGitHub() {
  return {
    connected: true,
    github_user_id: 123,
    github_login: 'octocat',
    avatar_url: 'https://avatars.example/octocat.png',
    installation_id: 456,
    account_type: 'User',
  }
}

function repositoryMetadata(overrides = {}) {
  return {
    created: true,
    repository_id: 789,
    owner: 'octocat',
    name: 'quickbook',
    full_name: 'octocat/quickbook',
    html_url: 'https://github.com/octocat/quickbook',
    visibility: 'PRIVATE',
    private: true,
    default_branch: 'main',
    is_empty: true,
    created_at: '2026-10-16T08:00:00Z',
    ...overrides,
  }
}

function extractionResult(overrides = {}) {
  return {
    upload_id: metadata().upload_id,
    agent_project_id: 'AGP-003',
    artifact_type: 'API_SPECIFICATION',
    original_filename: 'bookease-api.pdf',
    document_type: 'PDF',
    status: 'SUCCESS',
    extractor_version: '1',
    source_sha256: 'a'.repeat(64),
    content: {
      pages: [{ page_number: 1, text: 'POST /bookings creates a booking.' }],
      combined_text: 'POST /bookings creates a booking.',
    },
    metrics: {
      page_count: 1,
      processed_page_count: 1,
      pages_with_text: 1,
      pages_without_text: 0,
      extracted_character_count: 33,
    },
    warnings: [],
    extracted_at: '2026-10-16T10:00:00Z',
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
  beforeEach(() => {
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')
    getGitHubConnection.mockResolvedValue({ data: { connected: false } })
    getGitHubRepository.mockResolvedValue({ data: { created: false } })
    extractImplementationDocument.mockResolvedValue({ data: extractionResult() })
    getImplementationDocumentExtraction.mockResolvedValue({ data: extractionResult() })
  })

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

    if (sourceType === 'DOCUMENT') await screen.findByText('Complete')
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

  it('automatically extracts a document and shows the extracting state', async () => {
    const user = userEvent.setup()
    let resolveExtraction
    extractImplementationDocument.mockReturnValue(new Promise((resolve) => { resolveExtraction = resolve }))
    uploadImplementationInputFile.mockResolvedValue({ data: metadata() })
    render(<ImplementationWorkspace project={project} />)
    await chooseSource(user, 'DOCUMENT')
    await user.upload(
      screen.getByLabelText(/Document file/),
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
    )
    await user.click(screen.getByRole('button', { name: 'Attach File' }))
    expect(await screen.findByText('Extracting...')).toBeInTheDocument()
    expect(extractImplementationDocument).toHaveBeenCalledWith(
      'AGP-003', metadata().upload_id, { force: false },
    )
    resolveExtraction({ data: extractionResult() })
    expect(await screen.findByText('Complete')).toBeInTheDocument()
  })

  it.each([
    ['PARTIAL', 'Partial', 'Some pages did not contain text.'],
    ['FAILED', 'Failed', 'No reliable textual content could be extracted from this document.'],
  ])('shows %s extraction with warnings and offers retry', async (status, label, warning) => {
    const user = userEvent.setup()
    extractImplementationDocument.mockResolvedValueOnce({
      data: extractionResult({
        status,
        warnings: [{ code: 'NO_EXTRACTABLE_TEXT', message: warning, location: null }],
      }),
    }).mockResolvedValueOnce({ data: extractionResult() })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByText('Warnings: 1')).toBeInTheDocument()
    expect(screen.getByText(warning)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry Extraction' }))
    await waitFor(() => expect(extractImplementationDocument).toHaveBeenLastCalledWith(
      'AGP-003', metadata().upload_id, { force: true },
    ))
  })

  it('reports extraction API failure honestly and allows retry', async () => {
    const user = userEvent.setup()
    extractImplementationDocument.mockRejectedValueOnce({
      errors: [{ message: 'Document extraction is temporarily unavailable' }],
    }).mockResolvedValueOnce({ data: extractionResult() })
    render(<ImplementationWorkspace project={project} />)
    uploadImplementationInputFile.mockResolvedValue({ data: metadata() })
    await chooseSource(user, 'DOCUMENT')
    await user.upload(
      screen.getByLabelText(/Document file/),
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
    )
    await user.click(screen.getByRole('button', { name: 'Attach File' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('temporarily unavailable')
    expect(screen.getByText('Extraction request failed')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry Extraction' }))
    expect(await screen.findByText('Complete')).toBeInTheDocument()
  })

  it.each([
    ['PDF', { pages: [{ page_number: 2, text: 'Page two API details' }], combined_text: 'Page two API details' }, 'Page 2', 'Page two API details'],
    ['DOCX', { blocks: [
      { block_index: 0, type: 'HEADING', level: 1, text: 'API Specification', rows: null },
      { block_index: 1, type: 'PARAGRAPH', level: null, text: 'Create booking', rows: null },
      { block_index: 2, type: 'TABLE', level: null, text: null, rows: [['Method', 'Path'], ['POST', '/bookings']] },
    ], combined_text: 'API Specification\nCreate booking' }, 'API Specification', '/bookings'],
    ['TXT', { text: 'Plain requirements', combined_text: 'Plain requirements' }, 'Plain requirements', null],
    ['MD', { markdown: '# Requirements\n- Booking', combined_text: '# Requirements\n- Booking' }, '# Requirements', null],
    ['JSON', { structured_content: { api: 'bookings' }, normalized_text: '{\n  "api": "bookings"\n}' }, '"api": "bookings"', null],
    ['YAML', { structured_content: { api: 'bookings' }, normalized_text: '{\n  "api": "bookings"\n}' }, '"api": "bookings"', null],
  ])('reviews safe structured %s extraction content', async (documentType, content, expected, secondary) => {
    const user = userEvent.setup()
    const result = extractionResult({ document_type: documentType, content })
    extractImplementationDocument.mockResolvedValue({ data: result })
    getImplementationDocumentExtraction.mockResolvedValue({ data: result })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['document'], `input.${documentType.toLowerCase()}`, { type: 'application/octet-stream' }),
      metadata({ original_filename: `input.${documentType.toLowerCase()}` }),
    )
    await user.click(screen.getByRole('button', { name: 'Review Extracted Content' }))
    expect(await screen.findByRole('heading', { name: 'Extracted Document Content' })).toBeInTheDocument()
    const review = within(screen.getByLabelText('Extracted Document Content'))
    expect(review.getByText(/implementation readiness has not yet been validated/i)).toBeInTheDocument()
    expect(review.getByText(expected, { exact: false })).toBeInTheDocument()
    if (secondary) expect(review.getByText(secondary, { exact: false })).toBeInTheDocument()
  })

  it('keeps IMAGE upload-only and never starts document extraction', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'IMAGE',
      new File(['png'], 'wireframe.png', { type: 'image/png' }),
      metadata({
        source_type: 'IMAGE', artifact_type: 'UI_WIREFRAMES', original_filename: 'wireframe.png',
        mime_type: 'image/png', extension: '.png', size_bytes: 1024,
      }),
    )
    expect(extractImplementationDocument).not.toHaveBeenCalled()
    expect(screen.queryByText('Extraction')).not.toBeInTheDocument()
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

  it('validates incomplete inputs and offers real GitHub connection', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await chooseSource(user, 'IMAGE')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('attach a file')
    expect(await screen.findByRole('button', { name: 'Connect GitHub' })).toBeEnabled()
  })

  it('starts GitHub connection through the backend and redirects to its URL', async () => {
    const user = userEvent.setup()
    connectGitHub.mockResolvedValue({
      data: { installation_url: 'https://github.com/apps/agileflow/installations/new?state=safe' },
    })
    render(<ImplementationWorkspace project={project} />)
    await user.click(await screen.findByRole('button', { name: 'Connect GitHub' }))
    expect(connectGitHub).toHaveBeenCalledWith('AGP-003')
    expect(navigateToGitHub).toHaveBeenCalledWith(
      'https://github.com/apps/agileflow/installations/new?state=safe',
    )
  })

  it('shows a verified personal connection with new-repository setup only', async () => {
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('@octocat')).toBeInTheDocument()
    expect(screen.getByText('Personal')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Repository Setup' })).toBeInTheDocument()
    expect(screen.queryByText(/existing repositor/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Repository' })).toBeEnabled()
  })

  it('trusts backend status, not the connected callback query alone', async () => {
    window.history.replaceState({}, '', '/agent-projects/AGP-003?github=connected')
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('no verified connection')
    expect(screen.queryByText('GitHub account connected successfully.')).not.toBeInTheDocument()
  })

  it('shows callback success only with verified status and handles callback errors', async () => {
    getGitHubConnection.mockResolvedValue({ data: { ...connectedGitHub(), avatar_url: null } })
    window.history.replaceState({}, '', '/agent-projects/AGP-003?github=connected')
    const view = render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('status')).toHaveTextContent('connected successfully')
    view.unmount()

    getGitHubConnection.mockResolvedValue({ data: { connected: false } })
    window.history.replaceState({}, '', '/agent-projects/AGP-003?github=error&reason=authorization_failed')
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('was not completed')
  })

  it('validates repository names before calling the backend', async () => {
    const user = userEvent.setup()
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Repository Setup' })
    await user.type(screen.getByLabelText(/Repository Name/), 'owner/repo')
    await user.click(screen.getByRole('button', { name: 'Create Repository' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/repository name/i)
    expect(createGitHubRepository).not.toHaveBeenCalled()
  })

  it('creates a private or public repository once and disables while pending', async () => {
    const user = userEvent.setup()
    let resolveCreate
    createGitHubRepository.mockReturnValue(new Promise((resolve) => { resolveCreate = resolve }))
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Repository Setup' })
    await user.type(screen.getByLabelText(/Repository Name/), 'quickbook')
    await user.type(screen.getByLabelText('Description'), 'Booking system')
    await user.selectOptions(screen.getByLabelText(/Visibility/), 'PUBLIC')
    await user.click(screen.getByRole('button', { name: 'Create Repository' }))
    expect(screen.getByRole('button', { name: 'Creating repository' })).toBeDisabled()
    expect(createGitHubRepository).toHaveBeenCalledWith('AGP-003', {
      name: 'quickbook', description: 'Booking system', visibility: 'PUBLIC',
    })
    resolveCreate({ data: repositoryMetadata({ visibility: 'PUBLIC', private: false }) })
    expect(await screen.findByText('octocat/quickbook')).toBeInTheDocument()
  })

  it('shows persisted empty repository metadata and no duplicate or Git controls', async () => {
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    getGitHubRepository.mockResolvedValue({ data: repositoryMetadata() })
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByText('octocat/quickbook')).toBeInTheDocument()
    expect(screen.getByText('Empty')).toBeInTheDocument()
    expect(screen.getByText('Not created yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open on GitHub' })).toHaveAttribute(
      'href', 'https://github.com/octocat/quickbook',
    )
    expect(screen.queryByRole('button', { name: 'Create Repository' })).not.toBeInTheDocument()
    expect(screen.queryByText(/existing repository|create branch|clone|commit|pull request/i)).not.toBeInTheDocument()
  })

  it('reports repository API failure without claiming creation', async () => {
    const user = userEvent.setup()
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    createGitHubRepository.mockRejectedValue({
      errors: [{ message: 'A repository with this name already exists' }],
    })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Repository Setup' })
    await user.type(screen.getByLabelText(/Repository Name/), 'quickbook')
    await user.click(screen.getByRole('button', { name: 'Create Repository' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
    expect(screen.queryByText('octocat/quickbook')).not.toBeInTheDocument()
  })

  it('includes the persisted empty repository in workspace review', async () => {
    const user = userEvent.setup()
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    getGitHubRepository.mockResolvedValue({ data: repositoryMetadata() })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByText('octocat/quickbook')
    await user.type(screen.getByLabelText(/Content/), 'Build booking.')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Backend Code' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    expect(screen.getAllByText(/Repository: octocat\/quickbook/).length).toBeGreaterThan(0)
    expect(screen.getByText('Repository state: Empty')).toBeInTheDocument()
    expect(screen.queryByText(/code pushed|branch created|build successful/i)).not.toBeInTheDocument()
  })

  it('reports backend connection status failures without claiming connection', async () => {
    getGitHubConnection.mockRejectedValue({
      errors: [{ message: 'GitHub connection storage is unavailable' }],
    })
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('storage is unavailable')
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Connect GitHub' })).toBeEnabled()
  })
})
