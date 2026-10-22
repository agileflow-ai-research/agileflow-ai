export const REQUIREMENT_OUTPUT_CODES = Object.freeze({
  FUNCTIONAL_REQUIREMENTS: 'FUNCTIONAL_REQUIREMENTS',
  NON_FUNCTIONAL_REQUIREMENTS: 'NON_FUNCTIONAL_REQUIREMENTS',
  USER_STORIES: 'USER_STORIES',
  ACCEPTANCE_CRITERIA: 'ACCEPTANCE_CRITERIA',
  PERSONAS: 'PERSONAS',
  SRS: 'SRS',
})

export const REQUIREMENT_OUTPUT_OPTIONS = Object.freeze([
  { value: REQUIREMENT_OUTPUT_CODES.FUNCTIONAL_REQUIREMENTS, label: 'Functional Requirements', description: 'Structured functional capabilities and behaviors.' },
  { value: REQUIREMENT_OUTPUT_CODES.NON_FUNCTIONAL_REQUIREMENTS, label: 'Non-Functional Requirements', description: 'Quality attributes and operational constraints.' },
  { value: REQUIREMENT_OUTPUT_CODES.USER_STORIES, label: 'User Stories', description: 'User-centered requirements in story form.' },
  { value: REQUIREMENT_OUTPUT_CODES.ACCEPTANCE_CRITERIA, label: 'Acceptance Criteria', description: 'Verifiable conditions for requirement acceptance.' },
  { value: REQUIREMENT_OUTPUT_CODES.PERSONAS, label: 'Personas', description: 'Representative users and their goals.' },
  { value: REQUIREMENT_OUTPUT_CODES.SRS, label: 'Software Requirements Specification', description: 'A consolidated requirements specification.' },
])
