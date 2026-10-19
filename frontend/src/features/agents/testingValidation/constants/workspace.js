// Mode-first workspace configuration for Agent 4. Modes are shown before any mode-specific content.
// Mode labels come from the shared presentation module so every screen names a mode the same way.
import { agentRunModePresentation } from '../../../../utils/agentPresentation.js'

export const AGENT4_MODES = {
  TEST_GENERATION: {
    value: 'TEST_GENERATION',
    label: agentRunModePresentation.TEST_GENERATION.label,
    description: 'Generate test plans and structured test cases from approved requirements and design artifacts. Supports pre-code, tests-first workflows.',
  },
  VALIDATION: {
    value: 'VALIDATION',
    label: agentRunModePresentation.VALIDATION.label,
    description: 'Validate an existing implementation through controlled test execution, coverage, quality and security checks.',
  },
}

export const WORKFLOW_STATUS_LABELS = {
  ACTIVE: 'Active',
  AVAILABLE: 'Available',
  COMING_NEXT: 'Coming next',
  NOT_AVAILABLE: 'Not available yet',
}

// Terminology follows contract v1.1. Only Inputs is functional in this step.
export const TEST_GENERATION_WORKFLOW = [
  { id: 'inputs', label: 'Inputs', status: 'ACTIVE' },
  { id: 'document-extraction', label: 'Document Extraction', status: 'AVAILABLE' },
  { id: 'testability', label: 'Testability', status: 'NOT_AVAILABLE' },
  { id: 'test-case-plan', label: 'Test Case Plan', status: 'NOT_AVAILABLE' },
  { id: 'human-review', label: 'Human Review', status: 'NOT_AVAILABLE' },
  { id: 'test-generation', label: 'Test Generation', status: 'NOT_AVAILABLE' },
  { id: 'results', label: 'Results', status: 'NOT_AVAILABLE' },
]

// VALIDATION is a separate later workflow. Its execution pipeline is not wired into this rebuild.
export const VALIDATION_WORKFLOW = [
  { id: 'source', label: 'Source', status: 'NOT_AVAILABLE' },
  { id: 'build', label: 'Build', status: 'NOT_AVAILABLE' },
  { id: 'test-execution', label: 'Test Execution', status: 'NOT_AVAILABLE' },
  { id: 'coverage', label: 'Coverage', status: 'NOT_AVAILABLE' },
  { id: 'security-quality', label: 'Security / Quality', status: 'NOT_AVAILABLE' },
  { id: 'validation-report', label: 'Validation Report', status: 'NOT_AVAILABLE' },
]
