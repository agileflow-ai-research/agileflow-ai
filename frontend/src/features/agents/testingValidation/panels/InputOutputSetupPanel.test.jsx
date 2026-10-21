import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createTestingValidationTextSource,
  deleteTestingValidationSource,
  listTestingValidationSources,
  uploadTestingValidationSource,
} from '../testingValidationAgentService.js'
import InputOutputSetupPanel from './InputOutputSetupPanel.jsx'

vi.mock('../testingValidationAgentService.js', () => ({
  createTestingValidationTextSource: vi.fn(),
  deleteTestingValidationSource: vi.fn(),
  listTestingValidationSources: vi.fn(),
  uploadTestingValidationSource: vi.fn(),
}))

const definition = {
  title: 'Input & Output Setup',
  purpose: 'Collect source evidence and later select outputs.',
  futureStages: ['Source collection', 'Output selection', 'Human confirmation'],
}

const textSource = {
  source_id: `A4SRC-${'a'.repeat(32)}`,
  agent_project_id: 'AGP-404',
  artifact_type: 'FUNCTIONAL_REQUIREMENTS',
  source_type: 'TEXT',
  normally_supplied_by: 'AGENT_1',
  supplied_via: 'STANDALONE_MANUAL_INPUT',
  label: 'Transfer rules',
  collection_status: 'READY',
  text_content: 'Customers transfer funds.',
  created_at: '2026-10-21T00:00:00Z',
}

const documentSource = {
  ...textSource,
  source_id: `A4SRC-${'b'.repeat(32)}`,
  artifact_type: 'API_SPECIFICATION',
  source_type: 'DOCUMENT',
  normally_supplied_by: 'AGENT_2',
  label: null,
  collection_status: 'UPLOADED',
  text_content: null,
  original_filename: 'openapi.yaml',
  extension: '.yaml',
  mime_type: 'application/yaml',
  size_bytes: 2048,
  sha256: 'c'.repeat(64),
}

const imageSource = {
  ...documentSource,
  source_id: `A4SRC-${'d'.repeat(32)}`,
  artifact_type: 'UI_FLOW',
  source_type: 'IMAGE',
  label: 'Checkout flow',
  collection_status: 'PENDING_ANALYSIS',
  original_filename: 'checkout.png',
  extension: '.png',
  mime_type: 'image/png',
  size_bytes: 512,
}

function renderPanel() {
  return render(
    <InputOutputSetupPanel
      agentProjectId="AGP-404"
      definition={definition}
      statusLabel="Available - Waiting for Setup"
    />,
  )
}

async function waitForSources() {
  await waitFor(() => expect(listTestingValidationSources).toHaveBeenCalledWith('AGP-404'))
}

describe('InputOutputSetupPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTestingValidationSources.mockResolvedValue({ data: [] })
    deleteTestingValidationSource.mockResolvedValue({ data: {} })
  })

  it('loads existing sources and renders truthful independent source cards', async () => {
    listTestingValidationSources.mockResolvedValue({ data: [textSource, documentSource, imageSource] })
    renderPanel()

    expect(screen.getByText('Loading sources…')).toBeInTheDocument()
    expect(await screen.findByText('3 sources')).toBeInTheDocument()
    expect(screen.getByText('Transfer rules')).toBeInTheDocument()
    expect(screen.getByText('openapi.yaml · 2.0 KB')).toBeInTheDocument()
    expect(screen.getByText('Checkout flow')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Uploaded')).toBeInTheDocument()
    expect(screen.getByText('Pending Analysis')).toBeInTheDocument()
    expect(screen.getAllByText(/Manually supplied in standalone Agent 4/)).toHaveLength(3)
    expect(screen.getByText(/Normally supplied by Agent 1/)).toBeInTheDocument()
    expect(screen.getAllByText(/Normally supplied by Agent 2/)).toHaveLength(2)
  })

  it('shows the empty source state and keeps N1 incomplete with N2 locked', async () => {
    renderPanel()
    expect(await screen.findByText('No Test Generation sources collected yet.')).toBeInTheDocument()
    expect(screen.getByText(/N1 remains Waiting for Human and N2 remains locked/)).toBeInTheDocument()
    expect(screen.getByText('Output selection · Coming next')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Confirm|Continue/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Extract|Normalize|Chunk|Analyze|Run/ })).not.toBeInTheDocument()
  })

  it('filters artifact types by group and exposes IMAGE only for visual artifacts', async () => {
    const user = userEvent.setup()
    renderPanel()
    await waitForSources()

    expect(screen.getByRole('option', { name: 'Functional Requirements' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'System Architecture' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Artifact group'), 'DESIGN_TECHNICAL')
    expect(screen.getByRole('option', { name: 'System Architecture' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Functional Requirements' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Artifact type'), 'API_SPECIFICATION')
    expect(screen.queryByRole('option', { name: 'IMAGE' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Artifact type'), 'SYSTEM_ARCHITECTURE')
    expect(screen.getByRole('option', { name: 'IMAGE' })).toBeInTheDocument()
  })

  it('switches between TEXT editor and DOCUMENT/IMAGE file pickers', async () => {
    const user = userEvent.setup()
    renderPanel()
    await waitForSources()
    await user.selectOptions(screen.getByLabelText('Artifact group'), 'DESIGN_TECHNICAL')
    await user.selectOptions(screen.getByLabelText('Artifact type'), 'SYSTEM_ARCHITECTURE')

    expect(screen.getByLabelText('Source text')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Source type'), 'DOCUMENT')
    expect(screen.getByLabelText('DOCUMENT file')).toHaveAttribute('accept', '.pdf,.docx,.txt,.md,.json,.yaml,.yml')
    expect(screen.queryByLabelText('Source text')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Source type'), 'IMAGE')
    expect(screen.getByLabelText('IMAGE file')).toHaveAttribute('accept', '.png,.jpg,.jpeg,.webp')
  })

  it('asks for origin only when USER_STORIES is ambiguous', async () => {
    const user = userEvent.setup()
    renderPanel()
    await waitForSources()

    await user.selectOptions(screen.getByLabelText('Artifact type'), 'FUNCTIONAL_REQUIREMENTS')
    expect(screen.queryByLabelText('Normally supplied by')).not.toBeInTheDocument()
    expect(screen.getByText('Agent 1')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Artifact type'), 'USER_STORIES')
    expect(screen.getByLabelText('Normally supplied by')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Agent 1' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Agent 2' })).toBeInTheDocument()
  })

  it('validates blank TEXT locally and adds a valid TEXT source', async () => {
    const user = userEvent.setup()
    createTestingValidationTextSource.mockResolvedValue({ data: textSource })
    renderPanel()
    await waitForSources()
    await user.selectOptions(screen.getByLabelText('Artifact type'), 'FUNCTIONAL_REQUIREMENTS')
    await user.click(screen.getByRole('button', { name: 'Add Source' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter non-blank source text.')
    expect(createTestingValidationTextSource).not.toHaveBeenCalled()

    await user.type(screen.getByLabelText('Label (optional)'), 'Transfer rules')
    await user.type(screen.getByLabelText('Source text'), 'Customers transfer funds.')
    await user.click(screen.getByRole('button', { name: 'Add Source' }))
    await waitFor(() => expect(createTestingValidationTextSource).toHaveBeenCalledWith('AGP-404', {
      artifact_type: 'FUNCTIONAL_REQUIREMENTS',
      normally_supplied_by: 'AGENT_1',
      label: 'Transfer rules',
      content: 'Customers transfer funds.',
    }))
    expect(await screen.findByText('Transfer rules')).toBeInTheDocument()
  })

  it.each([
    ['DOCUMENT', 'API_SPECIFICATION', new File(['openapi: 3.0.0'], 'openapi.yaml', { type: 'application/yaml' }), documentSource],
    ['IMAGE', 'SYSTEM_ARCHITECTURE', new File(['png'], 'architecture.png', { type: 'image/png' }), imageSource],
  ])('uploads a %s source without invoking processing', async (sourceType, artifactType, file, responseSource) => {
    const user = userEvent.setup()
    uploadTestingValidationSource.mockResolvedValue({ data: responseSource })
    renderPanel()
    await waitForSources()
    await user.selectOptions(screen.getByLabelText('Artifact group'), 'DESIGN_TECHNICAL')
    await user.selectOptions(screen.getByLabelText('Artifact type'), artifactType)
    await user.selectOptions(screen.getByLabelText('Source type'), sourceType)
    await user.upload(screen.getByLabelText(`${sourceType} file`), file)
    await user.click(screen.getByRole('button', { name: 'Add Source' }))

    await waitFor(() => expect(uploadTestingValidationSource).toHaveBeenCalledWith(
      'AGP-404',
      {
        artifact_type: artifactType,
        normally_supplied_by: 'AGENT_2',
        label: '',
        source_type: sourceType,
      },
      file,
    ))
    expect(await screen.findByTitle(responseSource.original_filename)).toBeInTheDocument()
  })

  it('removes one source without collapsing other same-artifact sources', async () => {
    const user = userEvent.setup()
    const secondText = { ...textSource, source_id: `A4SRC-${'e'.repeat(32)}`, label: 'Second evidence' }
    listTestingValidationSources.mockResolvedValue({ data: [textSource, secondText] })
    renderPanel()
    expect(await screen.findByText('2 sources')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Remove' })[0])
    await waitFor(() => expect(deleteTestingValidationSource).toHaveBeenCalledWith('AGP-404', textSource.source_id))
    expect(screen.queryByText('Transfer rules')).not.toBeInTheDocument()
    expect(screen.getByText('Second evidence')).toBeInTheDocument()
  })

  it('shows safe mutation errors while preserving loaded sources', async () => {
    const user = userEvent.setup()
    listTestingValidationSources.mockResolvedValue({ data: [textSource] })
    deleteTestingValidationSource.mockRejectedValue({
      status: 503,
      errors: [{ message: 'The source could not be removed' }],
    })
    renderPanel()
    expect(await screen.findByText('Transfer rules')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The source could not be removed')
    expect(screen.getByText('Transfer rules')).toBeInTheDocument()
  })
})
