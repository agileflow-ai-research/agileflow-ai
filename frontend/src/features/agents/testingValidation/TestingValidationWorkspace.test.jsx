import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TEST_GENERATION_OUTPUT_CODES } from './constants/testGeneration.js'
import { VALIDATION_OUTPUT_CODES } from './constants/validation.js'
import {
  createTestGenerationTextInput,
  deleteTestGenerationInput,
  listTestGenerationInputs,
  runTestingValidationAgent,
  uploadTestGenerationInputFile,
} from './services/testingValidationAgentService.js'
import TestingValidationWorkspace from './TestingValidationWorkspace.jsx'

vi.mock('./services/testingValidationAgentService.js', () => ({
  runTestingValidationAgent: vi.fn(),
  listTestGenerationInputs: vi.fn(),
  createTestGenerationTextInput: vi.fn(),
  uploadTestGenerationInputFile: vi.fn(),
  deleteTestGenerationInput: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-004', agent_type: 'TESTING_VALIDATION',
  name: 'Quality Gate', domain: 'Fintech',
}

const testGenerationButton = () => screen.getByRole('button', { name: /^Test Case Generation/ })
const validationButton = () => screen.getByRole('button', { name: /^Testing & Validation/ })

describe('TestingValidationWorkspace', () => {
  let fetchMock

  beforeEach(() => {
    vi.clearAllMocks()
    listTestGenerationInputs.mockResolvedValue({ data: [] })
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows project name and domain from the AgentProject without asking for them again', () => {
    render(<TestingValidationWorkspace project={project} />)

    expect(screen.getByText('Quality Gate')).toBeInTheDocument()
    expect(screen.getByText('Fintech')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('shows the mode chooser first and no mode-specific content', () => {
    render(<TestingValidationWorkspace project={project} />)

    expect(testGenerationButton()).toBeInTheDocument()
    expect(validationButton()).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: /workflow preview/ })).not.toBeInTheDocument()
    expect(listTestGenerationInputs).not.toHaveBeenCalled()
  })

  it('opens the TEST_GENERATION Inputs stage without starting a run or any direct fetch', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)

    await user.click(testGenerationButton())

    const preview = screen.getByRole('list', { name: 'Test Case Generation workflow preview' })
    expect(within(preview).getAllByRole('listitem')).toHaveLength(7)
    expect(within(preview).getByText('Active')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Add Source' })).toBeInTheDocument()
    expect(listTestGenerationInputs).toHaveBeenCalledWith('AGP-004')
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the VALIDATION workflow preview separately and starts no execution or input collection', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)

    await user.click(validationButton())

    const preview = screen.getByRole('list', { name: 'Testing & Validation workflow preview' })
    expect(within(preview).getAllByRole('listitem')).toHaveLength(6)
    expect(within(preview).getByText('Test Execution')).toBeInTheDocument()
    expect(within(preview).queryByText('Test Case Plan')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add Source' })).not.toBeInTheDocument()
    expect(listTestGenerationInputs).not.toHaveBeenCalled()
    expect(runTestingValidationAgent).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('lets the user change mode safely back to the chooser', async () => {
    const user = userEvent.setup()
    render(<TestingValidationWorkspace project={project} />)

    await user.click(testGenerationButton())
    await user.click(screen.getByRole('button', { name: 'Change mode' }))

    expect(testGenerationButton()).toBeInTheDocument()
    expect(validationButton()).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: /workflow preview/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add Source' })).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('keeps the TEST_GENERATION and VALIDATION output vocabularies separate and exact', () => {
    expect(TEST_GENERATION_OUTPUT_CODES).toEqual([
      'UNIT_TEST_CASES', 'API_TEST_CASES', 'INTEGRATION_TEST_CASES',
      'FUNCTIONAL_TEST_CASES', 'E2E_TEST_CASES', 'REGRESSION_TEST_CASES',
      'SECURITY_TEST_CASES', 'ACCEPTANCE_TEST_CASES', 'TEST_TRACEABILITY',
    ])
    expect(VALIDATION_OUTPUT_CODES).toEqual([
      'TEST_EXECUTION_REPORT', 'COVERAGE_REPORT', 'BUG_REPORTS', 'SECURITY_FINDINGS',
      'CODE_QUALITY_REPORT', 'ACCEPTANCE_CRITERIA_VALIDATION', 'FINAL_VALIDATION_REPORT',
    ])
    expect(TEST_GENERATION_OUTPUT_CODES.filter((code) => VALIDATION_OUTPUT_CODES.includes(code))).toEqual([])
    expect(uploadTestGenerationInputFile).not.toHaveBeenCalled()
    expect(createTestGenerationTextInput).not.toHaveBeenCalled()
    expect(deleteTestGenerationInput).not.toHaveBeenCalled()
  })
})
