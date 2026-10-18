import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runTestingValidationAgent } from './testingValidationAgentService.js'
import TestingValidationWorkspace from './TestingValidationWorkspace.jsx'

vi.mock('./testingValidationAgentService.js', () => ({
  runTestingValidationAgent: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-004', agent_type: 'TESTING_VALIDATION',
  name: 'Quality Gate', domain: 'Fintech',
}

const nineGenerationOutputs = [
  'Unit Test Cases', 'API Test Cases', 'Integration Test Cases', 'Functional Test Cases',
  'End-to-End Test Cases', 'Regression Test Cases', 'Security Test Cases',
  'Acceptance Test Cases', 'Test Traceability',
]

const requirementTypeLabels = ['Requirements', 'User Stories', 'Acceptance Criteria', 'Software Requirements Specification (SRS)']
const designTypeLabels = ['System Architecture', 'API Specification', 'Database Schema', 'UI / Wireframe Specification', 'Technology Stack']
const implementationTypeLabels = ['Existing Source Code / Implementation Context']

async function chooseGeneration(user) {
  await user.click(screen.getByRole('button', { name: /Test Case Generation/ }))
}

async function next(user) {
  await user.click(screen.getByRole('button', { name: 'Next' }))
}

async function addArtifact(user, { type, text, label }) {
  if (type) await user.selectOptions(screen.getByLabelText('Artifact Type'), type)
  if (label) await user.type(screen.getByLabelText('Label (optional)'), label)
  await user.type(screen.getByLabelText('Artifact text'), text)
  await user.click(screen.getByRole('button', { name: 'Add Artifact' }))
}

// Requirements → Design → Implementation → Select Outputs
async function goToOutputs(user) {
  await next(user)
  await next(user)
  await next(user)
}

function artifactTypeOptionLabels() {
  return within(screen.getByLabelText('Artifact Type')).getAllByRole('option').map((option) => option.textContent)
}

function wizardStepNames() {
  return within(screen.getByRole('list', { name: 'Agent input steps' }))
    .getAllByRole('listitem')
    .map((item) => item.textContent.replace(/^\d+\./, ''))
}

function sectionFor(heading) {
  return screen.getByRole('heading', { name: heading }).parentElement
}

describe('TestingValidationWorkspace', () => {
  beforeEach(() => vi.clearAllMocks())

  it('requires an explicit mode choice before showing any wizard', () => {
    render(<TestingValidationWorkspace project={project} />)
    expect(screen.getByRole('button', { name: /Test Case Generation/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Testing & Validation/ })).toBeInTheDocument()
    expect(screen.queryByLabelText('Artifact Type')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Source Code or Project')).not.toBeInTheDocument()
  })

  it('runs TEST_GENERATION with artifacts adapted into the frozen payload fields', async () => {
    const user = userEvent.setup()
    runTestingValidationAgent.mockResolvedValue({ data: {
      run_id: 'RUN-401', status: 'COMPLETED', run_mode: 'TEST_GENERATION', warnings: [], errors: [],
      outputs: { UNIT_TEST_CASES: [{
        id: 'TEST-001', title: 'Transfer funds', purpose: 'Verify transfer', preconditions: [],
        test_data: ['valid account'], steps: ['Submit transfer'], expected_result: 'Transfer succeeds',
        source_refs: ['SRC-001'], representation: 'SPECIFICATION', executable: false,
        framework: null, code: null, execution_status: 'NOT_EXECUTED',
      }] },
    } })
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addArtifact(user, { type: 'REQUIREMENTS', text: 'Customers transfer funds' })
    await goToOutputs(user)
    expect(screen.getByRole('checkbox', { name: 'Unit Test Cases' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Coverage Report' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))
    expect(runTestingValidationAgent).toHaveBeenCalledWith('AGP-004', {
      run_mode: 'TEST_GENERATION',
      selected_outputs: ['UNIT_TEST_CASES'],
      requirements: '--- Artifact: REQUIREMENTS / TEXT / INPUT-001 ---\nCustomers transfer funds',
    })
    expect(await screen.findByRole('heading', { name: 'Generated test results' })).toBeInTheDocument()
    expect(screen.getByText('Test specification · Not executable')).toBeInTheDocument()
    expect(screen.getByText('Execution: NOT_EXECUTED')).toBeInTheDocument()
  })

  it('runs VALIDATION with validation-only inputs and evidence outputs', async () => {
    const user = userEvent.setup()
    runTestingValidationAgent.mockResolvedValue({ data: {
      run_id: 'RUN-402', status: 'COMPLETED', run_mode: 'VALIDATION', warnings: [], errors: [],
      outputs: { TEST_EXECUTION_REPORT: {
        status: 'FAILED', environment: 'Controlled temporary workspace',
        evidence: { evidence_type: 'ACTUAL_SANDBOX_EXECUTION', command: ['python', '-m', 'pytest'], exit_code: 1 },
        failures: [{ id: 'BUG-001' }], test_cases_supplied: true,
      } },
    } })
    render(<TestingValidationWorkspace project={project} />)
    await user.click(screen.getByRole('button', { name: /Testing & Validation/ }))
    expect(screen.getByLabelText('Source Code or Project')).toBeInTheDocument()
    expect(screen.queryByLabelText('Artifact Type')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Source Code or Project'), 'def transfer(): return False')
    await user.selectOptions(screen.getByLabelText('Validation profile'), 'PYTHON_PYTEST')
    await next(user)
    expect(screen.getByRole('checkbox', { name: 'Test Execution Report' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Unit Test Cases' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Test Execution Report' }))
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))
    expect(runTestingValidationAgent).toHaveBeenCalledWith('AGP-004', {
      run_mode: 'VALIDATION', source_code_or_project: 'def transfer(): return False',
      validation_profile: 'PYTHON_PYTEST', selected_outputs: ['TEST_EXECUTION_REPORT'],
    })
    expect(await screen.findByRole('heading', { name: 'Testing and validation evidence' })).toBeInTheDocument()
    expect(screen.getByText(/ACTUAL_SANDBOX_EXECUTION/)).toBeInTheDocument()
  })

  it('validates each mode without leaking the other mode requirements', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await next(user)
    expect(screen.getByRole('alert')).toHaveTextContent('Add at least one requirements artifact with text content')
    await user.click(screen.getByRole('button', { name: 'Change mode' }))
    await user.click(screen.getByRole('button', { name: /Testing & Validation/ }))
    await next(user)
    expect(screen.getByRole('alert')).toHaveTextContent('Source code or project is required')
  })

  describe('TEST_GENERATION five-step structure', () => {
    it('shows exactly the five artifact-oriented steps in order', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      expect(wizardStepNames()).toEqual([
        'Requirements Artifacts', 'Design & Technical Artifacts', 'Implementation Context', 'Select Outputs', 'Review',
      ])
    })
  })

  describe('Requirements Artifacts (Agent 1 equivalent)', () => {
    it('explains the Agent 1 origin and offers the four requirement artifact types', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      expect(screen.getByRole('heading', { name: 'Requirements Artifacts' })).toBeInTheDocument()
      expect(screen.getByText(/Normally supplied by Agent 1/)).toBeInTheDocument()
      expect(screen.getByText(/Manually provided in standalone mode/)).toBeInTheDocument()
      expect(artifactTypeOptionLabels()).toEqual(requirementTypeLabels)
    })

    it('offers Text, Document, and Image as selectable sources', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      const source = within(screen.getByLabelText('Input Source'))
      expect(source.getByRole('option', { name: 'Text' })).not.toBeDisabled()
      expect(source.getByRole('option', { name: 'Document' })).not.toBeDisabled()
      expect(source.getByRole('option', { name: 'Image' })).not.toBeDisabled()
    })

    it('offers the same TEXT, DOCUMENT, and IMAGE source choices in every artifact group', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      const sourceOptionNames = () => within(screen.getByLabelText('Input Source')).getAllByRole('option').map((option) => option.textContent)
      expect(sourceOptionNames()).toHaveLength(3)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Context' })
      await next(user)
      expect(sourceOptionNames()).toHaveLength(3)
      await next(user)
      expect(sourceOptionNames()).toHaveLength(3)
    })

    it('keeps Add Artifact disabled until text content is entered, so whitespace cannot be added', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      const add = screen.getByRole('button', { name: 'Add Artifact' })
      expect(add).toBeDisabled()
      await user.type(screen.getByLabelText('Artifact text'), '   ')
      expect(add).toBeDisabled()
    })

    it('allows multiple requirement artifacts, including several of the same type', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Requirement one' })
      await addArtifact(user, { type: 'USER_STORIES', text: 'As a patient I book', label: 'Booking stories' })
      await addArtifact(user, { type: 'ACCEPTANCE_CRITERIA', text: 'Criterion A' })
      await addArtifact(user, { type: 'ACCEPTANCE_CRITERIA', text: 'Criterion B' })
      await addArtifact(user, { type: 'SRS', text: 'SRS body' })
      const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
      expect(within(list).getAllByRole('listitem')).toHaveLength(5)
      expect(within(list).getAllByText(/\d\. Acceptance Criteria$/)).toHaveLength(2)
      expect(within(list).getByText('Source: Text · Booking stories')).toBeInTheDocument()
      expect(within(list).getByText('INPUT-002')).toBeInTheDocument()
    })

    it.each([
      ['REQUIREMENTS', 'Requirements'],
      ['USER_STORIES', 'User Stories'],
      ['ACCEPTANCE_CRITERIA', 'Acceptance Criteria'],
      ['SRS', 'SRS'],
    ])('accepts a single usable %s artifact as sufficient requirements context', async (type) => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type, text: 'Usable context' })
      await next(user)
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Design & Technical Artifacts' })).toBeInTheDocument()
    })

    it('blocks progress when no usable requirements artifact has been added', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await next(user)
      expect(screen.getByRole('alert')).toHaveTextContent('Add at least one requirements artifact with text content before continuing.')
      expect(screen.getByRole('heading', { name: 'Requirements Artifacts' })).toBeInTheDocument()
    })
  })

  describe('Design & Technical Artifacts (Agent 2 equivalent)', () => {
    it('explains the Agent 2 origin and offers exactly the five design artifact types', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Context' })
      await next(user)
      expect(screen.getByRole('heading', { name: 'Design & Technical Artifacts' })).toBeInTheDocument()
      expect(screen.getByText(/Normally supplied by Agent 2/)).toBeInTheDocument()
      expect(artifactTypeOptionLabels()).toEqual(designTypeLabels)
    })

    it('treats design artifacts as optional and allows multiple of them', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Context' })
      await next(user)
      expect(screen.getByText(/Optional\. Technical artifacts help Agent 4/)).toBeInTheDocument()
      await addArtifact(user, { type: 'API_SPECIFICATION', text: 'POST /transfers' })
      await addArtifact(user, { type: 'DATABASE_SCHEMA', text: 'accounts(id)' })
      await addArtifact(user, { type: 'DATABASE_SCHEMA', text: 'transfers(id)' })
      const list = screen.getByRole('list', { name: 'Design & Technical Artifacts added' })
      expect(within(list).getAllByRole('listitem')).toHaveLength(3)
      await next(user)
      expect(screen.getByRole('heading', { name: 'Implementation Context' })).toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  describe('Implementation Context (Agent 3 equivalent)', () => {
    it('explains the Agent 3 origin, the optional nature, and offers only existing source code', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Context' })
      await next(user)
      await next(user)
      expect(screen.getByRole('heading', { name: 'Implementation Context' })).toBeInTheDocument()
      expect(screen.getByText(/Normally supplied by Agent 3/)).toBeInTheDocument()
      expect(screen.getByText('No implementation context is required when generating test specifications before implementation.')).toBeInTheDocument()
      expect(screen.getByText('Providing sufficient implementation and technical context may later allow Agent 4 to generate executable test code.')).toBeInTheDocument()
      expect(screen.getByText('Generated test specifications are not execution evidence.')).toBeInTheDocument()
      expect(artifactTypeOptionLabels()).toEqual(implementationTypeLabels)
    })

    it('keeps implementation context optional and exposes no repository fields', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Context' })
      await goToOutputs(user)
      expect(screen.getByRole('checkbox', { name: 'Unit Test Cases' })).toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(screen.queryByLabelText(/repository/i)).not.toBeInTheDocument()
    })
  })

  describe('artifact editing and removal', () => {
    it('removes an added artifact', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'First' })
      await addArtifact(user, { type: 'USER_STORIES', text: 'Second' })
      const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
      await user.click(within(within(list).getAllByRole('listitem')[0]).getByRole('button', { name: 'Remove' }))
      expect(within(list).getAllByRole('listitem')).toHaveLength(1)
      expect(within(list).getByText('1. User Stories')).toBeInTheDocument()
      expect(within(list).queryByText(/Requirements$/)).not.toBeInTheDocument()
    })

    it('edits a text artifact in place and keeps its identifier', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'USER_STORIES', text: 'Old story' })
      const list = screen.getByRole('list', { name: 'Requirements Artifacts added' })
      await user.click(within(list).getByRole('button', { name: 'Edit' }))
      expect(screen.getByLabelText('Artifact text')).toHaveValue('Old story')
      await user.clear(screen.getByLabelText('Artifact text'))
      await user.type(screen.getByLabelText('Artifact text'), 'New story')
      await user.click(screen.getByRole('button', { name: 'Save artifact' }))
      expect(within(list).getByText('New story')).toBeInTheDocument()
      expect(within(list).queryByText('Old story')).not.toBeInTheDocument()
      expect(within(list).getByText('INPUT-001')).toBeInTheDocument()
    })

    it('adds exactly one artifact when Add Artifact is clicked repeatedly', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await user.type(screen.getByLabelText('Artifact text'), 'Only once')
      await user.dblClick(screen.getByRole('button', { name: 'Add Artifact' }))
      expect(screen.getByRole('list', { name: 'Requirements Artifacts added' }).children).toHaveLength(1)
    })
  })

  describe('navigation and output selection', () => {
    it('preserves artifacts and output selections when moving backward and forward', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Customers transfer funds' })
      await next(user)
      await addArtifact(user, { type: 'API_SPECIFICATION', text: 'POST /transfers' })
      await next(user)
      await addArtifact(user, { type: 'EXISTING_SOURCE_CODE', text: 'def transfer(): ...' })
      await next(user)
      await user.click(screen.getByRole('checkbox', { name: 'API Test Cases' }))
      await user.click(screen.getByRole('checkbox', { name: 'Security Test Cases' }))
      await next(user)
      await user.click(screen.getByRole('button', { name: 'Back' }))
      expect(screen.getByRole('checkbox', { name: 'API Test Cases' })).toBeChecked()
      expect(screen.getByRole('checkbox', { name: 'Security Test Cases' })).toBeChecked()
      expect(screen.getByRole('checkbox', { name: 'Unit Test Cases' })).not.toBeChecked()
      await user.click(screen.getByRole('button', { name: 'Back' }))
      expect(within(screen.getByRole('list', { name: 'Implementation Context added' })).getByText('def transfer(): ...')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Back' }))
      expect(within(screen.getByRole('list', { name: 'Design & Technical Artifacts added' })).getByText('POST /transfers')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Back' }))
      expect(within(screen.getByRole('list', { name: 'Requirements Artifacts added' })).getByText('Customers transfer funds')).toBeInTheDocument()
    })

    it('keeps entered artifacts when the same mode is chosen again after Back to mode selection', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Kept requirement' })
      await user.click(screen.getByRole('button', { name: 'Back' }))
      await chooseGeneration(user)
      expect(screen.getByRole('list', { name: 'Requirements Artifacts added' })).toHaveTextContent('Kept requirement')
    })

    it('shows exactly the nine frozen output options with friendly labels', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Context' })
      await goToOutputs(user)
      expect(screen.getAllByRole('checkbox').map((box) => box.getAttribute('aria-label'))).toEqual(nineGenerationOutputs)
    })

    it('requires at least one output before Review', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Context' })
      await goToOutputs(user)
      await next(user)
      expect(screen.getByRole('alert')).toHaveTextContent('Select at least one output.')
      expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
    })
  })

  describe('Review', () => {
    it('groups artifacts under their logical sections with type, source, preview, and friendly output labels', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Customers transfer funds' })
      await addArtifact(user, { type: 'SRS', text: 'SRS body' })
      await next(user)
      await addArtifact(user, { type: 'DATABASE_SCHEMA', text: 'accounts table' })
      await next(user)
      await addArtifact(user, { type: 'EXISTING_SOURCE_CODE', text: 'def transfer(): ...', label: 'service' })
      await next(user)
      await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
      await user.click(screen.getByRole('checkbox', { name: 'Test Traceability' }))
      await next(user)

      expect(screen.getByRole('heading', { name: 'Quality Gate' })).toBeInTheDocument()
      expect(screen.getByText('Fintech')).toBeInTheDocument()
      expect(screen.getByText('Test Case Generation')).toBeInTheDocument()

      const requirements = sectionFor('Requirements Artifacts')
      expect(within(requirements).getByText(/Normally supplied by Agent 1/)).toBeInTheDocument()
      expect(within(requirements).getByText('1. Requirements')).toBeInTheDocument()
      expect(within(requirements).getByText('2. Software Requirements Specification (SRS)')).toBeInTheDocument()
      expect(within(requirements).getByText('Customers transfer funds')).toBeInTheDocument()
      expect(within(requirements).getAllByText(/Source: Text/)).toHaveLength(2)
      expect(within(requirements).queryByText('User Stories')).not.toBeInTheDocument()

      const design = sectionFor('Design & Technical Artifacts')
      expect(within(design).getByText(/Normally supplied by Agent 2/)).toBeInTheDocument()
      expect(within(design).getByText('1. Database Schema')).toBeInTheDocument()
      expect(within(design).getByText('accounts table')).toBeInTheDocument()

      const implementation = sectionFor('Implementation Context')
      expect(within(implementation).getByText(/Normally supplied by Agent 3/)).toBeInTheDocument()
      expect(within(implementation).getByText(/Source: Text · service/)).toBeInTheDocument()
      expect(within(implementation).getByText('def transfer(): ...')).toBeInTheDocument()

      const selected = screen.getByRole('list', { name: 'Selected outputs' })
      expect(within(selected).getByText('Unit Test Cases')).toBeInTheDocument()
      expect(within(selected).getByText('Test Traceability')).toBeInTheDocument()
      expect(within(selected).queryByText('UNIT_TEST_CASES')).not.toBeInTheDocument()
    })

    it('hides Review sections for artifact groups with no artifacts', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Only requirements' })
      await goToOutputs(user)
      await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
      await next(user)
      expect(screen.getByRole('heading', { name: 'Requirements Artifacts' })).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Design & Technical Artifacts' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Implementation Context' })).not.toBeInTheDocument()
    })

    it('lets the user edit artifacts and selections from Review and returns to it', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'First version' })
      await goToOutputs(user)
      await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
      await next(user)
      await user.click(screen.getByRole('button', { name: 'Back' }))
      await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
      await user.click(screen.getByRole('checkbox', { name: 'End-to-End Test Cases' }))
      await next(user)
      const selected = screen.getByRole('list', { name: 'Selected outputs' })
      expect(within(selected).getByText('End-to-End Test Cases')).toBeInTheDocument()
      expect(within(selected).queryByText('Unit Test Cases')).not.toBeInTheDocument()
    })

    it('reaching Review does not call the run service or show results', async () => {
      const user = userEvent.setup()
      render(<TestingValidationWorkspace project={project} />)
      await chooseGeneration(user)
      await addArtifact(user, { type: 'REQUIREMENTS', text: 'Customers transfer funds' })
      await goToOutputs(user)
      await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
      await next(user)
      expect(screen.getByRole('button', { name: 'Run Agent' })).toBeInTheDocument()
      expect(runTestingValidationAgent).not.toHaveBeenCalled()
      expect(screen.queryByRole('heading', { name: 'Generated test results' })).not.toBeInTheDocument()
      expect(screen.queryByText('Generating test specifications')).not.toBeInTheDocument()
    })
  })

  it('sends deterministic adapter fields when several artifacts of one type are collected', async () => {
    const user = userEvent.setup()
    runTestingValidationAgent.mockResolvedValue({ data: { run_id: 'RUN-501', status: 'COMPLETED', run_mode: 'TEST_GENERATION', warnings: [], errors: [], outputs: {} } })
    render(<TestingValidationWorkspace project={project} />)
    await chooseGeneration(user)
    await addArtifact(user, { type: 'ACCEPTANCE_CRITERIA', text: 'Criterion A' })
    await addArtifact(user, { type: 'ACCEPTANCE_CRITERIA', text: 'Criterion B' })
    await addArtifact(user, { type: 'REQUIREMENTS', text: 'Requirement' })
    await goToOutputs(user)
    await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))
    expect(runTestingValidationAgent).toHaveBeenCalledWith('AGP-004', {
      run_mode: 'TEST_GENERATION',
      selected_outputs: ['UNIT_TEST_CASES'],
      requirements: '--- Artifact: REQUIREMENTS / TEXT / INPUT-003 ---\nRequirement',
      acceptance_criteria: '--- Artifact: ACCEPTANCE_CRITERIA / TEXT / INPUT-001 ---\nCriterion A\n\n--- Artifact: ACCEPTANCE_CRITERIA / TEXT / INPUT-002 ---\nCriterion B',
    })
  })
})
