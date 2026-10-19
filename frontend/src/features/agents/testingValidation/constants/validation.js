// VALIDATION output vocabulary, exactly as frozen in AGENT_4_TESTING_VALIDATION_CONTRACT.md v1.1.
// Must never be merged with the TEST_GENERATION vocabulary in constants/testGeneration.js.
export const VALIDATION_OUTPUTS = [
  { value: 'TEST_EXECUTION_REPORT', label: 'Test Execution Report', description: 'Actual command evidence, failures, and skipped work.' },
  { value: 'COVERAGE_REPORT', label: 'Coverage Report', description: 'Measured coverage only when a coverage tool runs.' },
  { value: 'BUG_REPORTS', label: 'Bug Reports', description: 'Structured defects grounded in validation evidence.' },
  { value: 'SECURITY_FINDINGS', label: 'Security Findings', description: 'Scanner findings clearly separated from suggestions.' },
  { value: 'CODE_QUALITY_REPORT', label: 'Code Quality Report', description: 'Static quality tool findings and scope.' },
  { value: 'ACCEPTANCE_CRITERIA_VALIDATION', label: 'Acceptance Criteria Validation', description: 'Criterion-level evidence or inability to validate.' },
  { value: 'FINAL_VALIDATION_REPORT', label: 'Final Validation Report', description: 'Consolidated readiness, evidence, and limitations.' },
]

export const VALIDATION_OUTPUT_CODES = VALIDATION_OUTPUTS.map((option) => option.value)
