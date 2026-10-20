import { render, screen } from '@testing-library/react'
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

const testGenerationProject = {
  ...project,
  agent_stage: 'TEST_GENERATION',
}

describe('TestingValidationWorkspace', () => {
  beforeEach(() => vi.clearAllMocks())

  it('requires an explicit mode choice before showing any wizard', () => {
    render(<TestingValidationWorkspace project={project} />)
    expect(screen.getByRole('button', { name: /Test Case Generation/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Testing & Validation/ })).toBeInTheDocument()
    expect(screen.queryByLabelText('Requirements')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Source Code or Project')).not.toBeInTheDocument()
  })

  it('keeps configured Test Generation projects out of the legacy direct-run wizard', () => {
    render(<TestingValidationWorkspace project={testGenerationProject} />)
    expect(screen.getByText(/six-node Test Generation canvas/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Requirements')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Test Case Generation/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Testing & Validation/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Change mode' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
  })

  it('does not expose Stage 2 controls for a configured Validation stage', () => {
    render(<TestingValidationWorkspace project={{ ...project, agent_stage: 'VALIDATION' }} />)
    expect(screen.getByText(/Coming Soon/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Source Code or Project')).not.toBeInTheDocument()
  })

  it('runs TEST_GENERATION with only generation inputs and outputs', async () => {
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
    await user.click(screen.getByRole('button', { name: /Test Case Generation/ }))
    expect(screen.getByLabelText('Requirements')).toBeInTheDocument()
    expect(screen.queryByLabelText('Source Code or Project')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Requirements'), 'Customers transfer funds')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('checkbox', { name: 'Unit Test Cases' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Coverage Report' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Unit Test Cases' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Run Agent' }))
    expect(runTestingValidationAgent).toHaveBeenCalledWith('AGP-004', {
      run_mode: 'TEST_GENERATION', requirements: 'Customers transfer funds',
      selected_outputs: ['UNIT_TEST_CASES'],
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
    expect(screen.queryByLabelText('Existing Source Code')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Source Code or Project'), 'def transfer(): return False')
    await user.selectOptions(screen.getByLabelText('Validation profile'), 'PYTHON_PYTEST')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('checkbox', { name: 'Test Execution Report' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Unit Test Cases' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Test Execution Report' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
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
    await user.click(screen.getByRole('button', { name: /Test Case Generation/ }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('requirements, user stories, acceptance criteria, or SRS')
    await user.click(screen.getByRole('button', { name: 'Change mode' }))
    await user.click(screen.getByRole('button', { name: /Testing & Validation/ }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Source code or project is required')
  })
})
