// Mode A (TEST_GENERATION) output vocabulary, frozen by AGENT_4_TESTING_VALIDATION_CONTRACT.md v1.1.
// Must never be merged with the VALIDATION vocabulary in constants/validation.js.
export const TEST_GENERATION_OUTPUTS = [
  { value: 'UNIT_TEST_CASES', label: 'Unit Test Cases', description: 'Unit-level structured test specifications.' },
  { value: 'API_TEST_CASES', label: 'API Test Cases', description: 'Endpoint and contract test specifications.' },
  { value: 'INTEGRATION_TEST_CASES', label: 'Integration Test Cases', description: 'Component-boundary test specifications.' },
  { value: 'FUNCTIONAL_TEST_CASES', label: 'Functional Test Cases', description: 'Behavior-oriented functional scenarios.' },
  { value: 'E2E_TEST_CASES', label: 'End-to-End Test Cases', description: 'Complete user journey scenarios.' },
  { value: 'REGRESSION_TEST_CASES', label: 'Regression Test Cases', description: 'Tests protecting established behavior.' },
  { value: 'SECURITY_TEST_CASES', label: 'Security Test Cases', description: 'Safe security validation specifications.' },
  { value: 'ACCEPTANCE_TEST_CASES', label: 'Acceptance Test Cases', description: 'Business acceptance scenarios.' },
  { value: 'TEST_TRACEABILITY', label: 'Test Traceability', description: 'Local source-to-generated-test mapping; no integrated writes.' },
]

export const TEST_GENERATION_OUTPUT_CODES = TEST_GENERATION_OUTPUTS.map((option) => option.value)
