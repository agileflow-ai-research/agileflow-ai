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

function renderPanel(props = {}) {
  return render(
    <InputOutputSetupPanel
      agentProjectId="AGP-404"
      definition={definition}
      statusLabel="Available - Waiting for Setup"
      {...props}
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
    expect(screen.getByText(/editable draft setup until the human confirmation gate/)).toBeInTheDocument()
    expect(screen.getByText('0 outputs selected')).toBeInTheDocument()
    expect(screen.getByText(/Confirm this input and output setup/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm Inputs & Outputs' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Continue' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Extract|Normalize|Chunk|Analyze|Run/ })).not.toBeInTheDocument()
  })

  it('renders all nine desired output choices with readable descriptions', async () => {
    renderPanel()
    await waitForSources()

    const choices = [
      ['Unit Test Cases', /Unit-level test specifications/],
      ['API Test Cases', /API request, response, and contract/],
      ['Integration Test Cases', /component and service boundaries/],
      ['Functional Test Cases', /Behavior-oriented functional scenarios/],
      ['End-to-End Test Cases', /End-to-end user-flow scenarios/],
      ['Regression Test Cases', /protect established behavior/],
      ['Security Test Cases', /Security-oriented test specifications/],
      ['Acceptance Test Cases', /Business acceptance scenarios/],
      ['Test Traceability', /Requirement-to-plan-to-test traceability/],
    ]
    choices.forEach(([label, description]) => {
      expect(screen.getByRole('checkbox', { name: label })).toBeInTheDocument()
      expect(screen.getByText(description)).toBeInTheDocument()
    })
    expect(screen.queryByText(/supported|feasible/i)).not.toBeInTheDocument()
  })

  it('tracks local output edits and explicitly saves a canonical selection', async () => {
    const user = userEvent.setup()
    const onSaveOutputs = vi.fn().mockResolvedValue({
      selected_outputs: ['UNIT_TEST_CASES', 'API_TEST_CASES'],
    })
    const { rerender } = renderPanel({
      selectedOutputs: ['API_TEST_CASES'], selectionRevision: 1, onSaveOutputs,
    })
    await waitForSources()

    expect(screen.getByRole('checkbox', { name: 'API Test Cases' })).toBeChecked()
    expect(screen.getByText('1 output selected')).toBeInTheDocument()
    expect(screen.getByText('Saved revision 1')).toBeInTheDocument()
    const save = screen.getByRole('button', { name: 'Save Output Selection' })
    expect(save).toBeDisabled()

    await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
    expect(screen.getByText('2 outputs selected')).toBeInTheDocument()
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
    await user.click(save)

    expect(onSaveOutputs).toHaveBeenCalledWith(['UNIT_TEST_CASES', 'API_TEST_CASES'])
    rerender(
      <InputOutputSetupPanel
        agentProjectId="AGP-404"
        definition={definition}
        statusLabel="Available - Waiting for Setup"
        selectedOutputs={['UNIT_TEST_CASES', 'API_TEST_CASES']}
        selectionRevision={2}
        onSaveOutputs={onSaveOutputs}
      />,
    )
    await waitFor(() => expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument())
  })

  it('supports deselecting and clearing the output draft without autosaving', async () => {
    const user = userEvent.setup()
    const onSaveOutputs = vi.fn()
    renderPanel({ selectedOutputs: ['SECURITY_TEST_CASES'], selectionRevision: 2, onSaveOutputs })
    await waitForSources()

    await user.click(screen.getByRole('checkbox', { name: 'Security Test Cases' }))
    expect(screen.getByText('0 outputs selected')).toBeInTheDocument()
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
    expect(onSaveOutputs).not.toHaveBeenCalled()
  })

  it('shows output save loading and safe errors without affecting sources', async () => {
    listTestingValidationSources.mockResolvedValue({ data: [textSource] })
    const { rerender } = renderPanel({
      selectedOutputs: ['UNIT_TEST_CASES'],
      outputSaving: true,
      onSaveOutputs: vi.fn(),
    })
    expect(await screen.findByText('Transfer rules')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Saving output selection' })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: 'Unit Test Cases' })).toBeDisabled()

    rerender(
      <InputOutputSetupPanel
        agentProjectId="AGP-404"
        definition={definition}
        statusLabel="Available - Waiting for Setup"
        selectedOutputs={['UNIT_TEST_CASES']}
        outputSaveError="The desired outputs could not be saved"
        onSaveOutputs={vi.fn()}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('The desired outputs could not be saved')
    expect(screen.getByText('Transfer rules')).toBeInTheDocument()
  })

  it('renders deterministic confirmation checklist failures and a valid state', async () => {
    const { rerender } = renderPanel({ selectedOutputs: [] })
    await waitForSources()
    const confirm = screen.getByRole('button', { name: 'Confirm Inputs & Outputs' })
    expect(screen.getByText('○ At least one source collected')).toBeInTheDocument()
    expect(screen.getByText('○ Primary functional artifact present')).toBeInTheDocument()
    expect(screen.getByText('○ 0 saved outputs')).toBeInTheDocument()
    expect(confirm).toBeDisabled()

    listTestingValidationSources.mockResolvedValue({ data: [documentSource] })
    rerender(
      <InputOutputSetupPanel
        agentProjectId="AGP-405"
        definition={definition}
        statusLabel="Available - Waiting for Setup"
        selectedOutputs={['API_TEST_CASES']}
      />,
    )
    await waitFor(() => expect(listTestingValidationSources).toHaveBeenCalledWith('AGP-405'))
    expect(screen.getByText('✓ At least one source collected')).toBeInTheDocument()
    expect(screen.getByText('○ Primary functional artifact present')).toBeInTheDocument()
    expect(screen.getByText('✓ 1 saved output')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm Inputs & Outputs' })).toBeDisabled()
  })

  it('confirms only a valid saved setup and shows a safe loading state', async () => {
    const user = userEvent.setup()
    const onConfirmN1 = vi.fn().mockResolvedValue({})
    listTestingValidationSources.mockResolvedValue({ data: [textSource] })
    const { rerender } = renderPanel({
      selectedOutputs: ['UNIT_TEST_CASES'],
      selectionRevision: 1,
      onConfirmN1,
    })
    expect(await screen.findByText('✓ Primary functional artifact present')).toBeInTheDocument()
    const confirm = screen.getByRole('button', { name: 'Confirm Inputs & Outputs' })
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    expect(onConfirmN1).toHaveBeenCalledOnce()

    rerender(
      <InputOutputSetupPanel
        agentProjectId="AGP-404"
        definition={definition}
        statusLabel="Available - Waiting for Setup"
        selectedOutputs={['UNIT_TEST_CASES']}
        selectionRevision={1}
        confirmationSubmitting
        onConfirmN1={onConfirmN1}
      />,
    )
    expect(screen.getByRole('button', { name: 'Confirming inputs and outputs' })).toBeDisabled()
  })

  it('blocks confirmation for unsaved outputs and active source/output mutations', async () => {
    const user = userEvent.setup()
    listTestingValidationSources.mockResolvedValue({ data: [textSource] })
    deleteTestingValidationSource.mockReturnValue(new Promise(() => {}))
    const { rerender } = renderPanel({
      selectedOutputs: ['UNIT_TEST_CASES'], selectionRevision: 1,
    })
    await screen.findByText('Transfer rules')

    await user.click(screen.getByRole('checkbox', { name: 'API Test Cases' }))
    expect(screen.getByText('Save output selection before confirming.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm Inputs & Outputs' })).toBeDisabled()

    rerender(
      <InputOutputSetupPanel
        agentProjectId="AGP-404"
        definition={definition}
        statusLabel="Available - Waiting for Setup"
        selectedOutputs={['UNIT_TEST_CASES']}
        selectionRevision={1}
        outputSaving
      />,
    )
    expect(screen.getByRole('button', { name: 'Confirm Inputs & Outputs' })).toBeDisabled()

    rerender(
      <InputOutputSetupPanel
        agentProjectId="AGP-404"
        definition={definition}
        statusLabel="Available - Waiting for Setup"
        selectedOutputs={['UNIT_TEST_CASES']}
        selectionRevision={1}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    expect(screen.getByRole('button', { name: 'Confirm Inputs & Outputs' })).toBeDisabled()
  })

  it('shows safe confirmation errors without readiness claims', async () => {
    listTestingValidationSources.mockResolvedValue({ data: [textSource] })
    renderPanel({
      selectedOutputs: ['UNIT_TEST_CASES'],
      selectionRevision: 1,
      confirmationError: 'The setup could not be confirmed',
    })
    expect(await screen.findByRole('alert')).toHaveTextContent('The setup could not be confirmed')
    expect(screen.queryByText(/Supported|Feasible/)).not.toBeInTheDocument()
  })

  it('renders confirmed evidence and freezes all N1 controls', async () => {
    listTestingValidationSources.mockResolvedValue({ data: [textSource] })
    renderPanel({
      selectedOutputs: ['UNIT_TEST_CASES', 'API_TEST_CASES'],
      selectionRevision: 2,
      pipelineStatus: 'RUNNING',
      workflowNodeStatus: 'COMPLETED',
      n1Confirmation: {
        confirmation_id: `A4N1C-${'a'.repeat(32)}`,
        source_count: 1,
        selected_output_count: 2,
        confirmed_at: '2026-10-21T02:00:00Z',
      },
    })

    expect(await screen.findByText('Setup Confirmed')).toBeInTheDocument()
    expect(screen.getByText('Sources: 1')).toBeInTheDocument()
    expect(screen.getByText('Outputs: 2')).toBeInTheDocument()
    expect(screen.getByText(/Confirmed at:/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Source' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: 'Unit Test Cases' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save Output Selection' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Change Setup/)).not.toBeInTheDocument()
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
