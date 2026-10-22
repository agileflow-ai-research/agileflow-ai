export const TEST_GENERATION_OUTPUT_OPTIONS = Object.freeze([
  {
    value: 'UNIT_TEST_CASES',
    label: 'Unit Test Cases',
    description: 'Unit-level test specifications for isolated behavior.',
  },
  {
    value: 'API_TEST_CASES',
    label: 'API Test Cases',
    description: 'API request, response, and contract test specifications.',
  },
  {
    value: 'INTEGRATION_TEST_CASES',
    label: 'Integration Test Cases',
    description: 'Test specifications for component and service boundaries.',
  },
  {
    value: 'FUNCTIONAL_TEST_CASES',
    label: 'Functional Test Cases',
    description: 'Behavior-oriented functional scenarios.',
  },
  {
    value: 'E2E_TEST_CASES',
    label: 'End-to-End Test Cases',
    description: 'End-to-end user-flow scenarios.',
  },
  {
    value: 'REGRESSION_TEST_CASES',
    label: 'Regression Test Cases',
    description: 'Test specifications that protect established behavior.',
  },
  {
    value: 'SECURITY_TEST_CASES',
    label: 'Security Test Cases',
    description: 'Security-oriented test specifications.',
  },
  {
    value: 'ACCEPTANCE_TEST_CASES',
    label: 'Acceptance Test Cases',
    description: 'Business acceptance scenarios and expected outcomes.',
  },
  {
    value: 'TEST_TRACEABILITY',
    label: 'Test Traceability',
    description: 'Requirement-to-plan-to-test traceability.',
  },
])

export function canonicalTestGenerationOutputs(values) {
  const selected = new Set(values ?? [])
  return TEST_GENERATION_OUTPUT_OPTIONS
    .filter((option) => selected.has(option.value))
    .map((option) => option.value)
}
