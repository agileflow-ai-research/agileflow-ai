// TEST_GENERATION input configuration (contract v1.1 §2.4–2.8).
// The backend is the authority for every rule. These lists only shape the form and the copy.

export const ARTIFACT_GROUPS = [
  {
    id: 'REQUIREMENTS_AND_QUALITY',
    label: 'Requirements & Quality Artifacts',
    origin: 'Normally supplied by Agent 1',
    artifacts: [
      { value: 'FUNCTIONAL_REQUIREMENTS', label: 'Functional Requirements', origin: 'AGENT_1', imageEligible: false },
      { value: 'NON_FUNCTIONAL_REQUIREMENTS', label: 'Non-Functional Requirements', origin: 'AGENT_1', imageEligible: false },
      { value: 'USER_STORIES', label: 'User Stories', origin: 'AGENT_1_OR_AGENT_2', imageEligible: false },
      { value: 'ACCEPTANCE_CRITERIA', label: 'Acceptance Criteria', origin: 'AGENT_1', imageEligible: false },
      { value: 'PERSONAS', label: 'Personas', origin: 'AGENT_1', imageEligible: false },
      { value: 'QUALITY_FINDINGS', label: 'Quality Findings', origin: 'AGENT_1', imageEligible: false },
      { value: 'CLARIFICATION_QUESTIONS', label: 'Clarification Questions', origin: 'AGENT_1', imageEligible: false },
      { value: 'SRS', label: 'Software Requirements Specification (SRS)', origin: 'AGENT_1', imageEligible: false },
    ],
  },
  {
    id: 'DESIGN_AND_TECHNICAL',
    label: 'Design & Technical Artifacts',
    origin: 'Normally supplied by Agent 2',
    artifacts: [
      { value: 'SYSTEM_ARCHITECTURE', label: 'System Architecture', origin: 'AGENT_2', imageEligible: true },
      { value: 'UML_DIAGRAMS', label: 'UML Diagrams', origin: 'AGENT_2', imageEligible: true },
      { value: 'DATABASE_SCHEMA', label: 'Database Schema', origin: 'AGENT_2', imageEligible: true },
      { value: 'API_SPECIFICATION', label: 'API Specification', origin: 'AGENT_2', imageEligible: false },
      { value: 'WIREFRAMES', label: 'Wireframes', origin: 'AGENT_2', imageEligible: true },
      { value: 'UI_FLOW', label: 'UI Flow', origin: 'AGENT_2', imageEligible: true },
      { value: 'FEATURES', label: 'Features', origin: 'AGENT_2', imageEligible: false },
    ],
  },
]

export const ARTIFACT_LABELS = Object.fromEntries(
  ARTIFACT_GROUPS.flatMap((group) => group.artifacts.map((artifact) => [artifact.value, artifact.label])),
)

export const SOURCE_TYPE_OPTIONS = [
  { value: 'TEXT', label: 'Text', description: 'Type or paste the content directly.' },
  { value: 'DOCUMENT', label: 'Document', description: 'Upload PDF, DOCX, TXT, MD, JSON, or YAML.' },
  { value: 'IMAGE', label: 'Image', description: 'Upload a PNG, JPEG, or WEBP image. Images stay pending analysis.' },
]

export const SOURCE_TYPE_LABELS = Object.fromEntries(SOURCE_TYPE_OPTIONS.map((option) => [option.value, option.label]))

export const ORIGIN_OPTIONS = [
  { value: 'AGENT_1', label: 'Agent 1 (Requirements)' },
  { value: 'AGENT_2', label: 'Agent 2 (Design & Planning)' },
]

export const PROCESSING_STATUS_LABELS = {
  COLLECTED: 'Collected',
  UPLOADED: 'Uploaded',
  PENDING_ANALYSIS: 'Pending analysis',
}

export const DOCUMENT_ACCEPT = '.pdf,.docx,.txt,.md,.json,.yaml,.yml'
export const IMAGE_ACCEPT = '.png,.jpg,.jpeg,.webp'
export const MAX_TEXT_SOURCE_CHARACTERS = 200_000
export const MAX_SOURCES_PER_PROJECT = 100

export function findArtifact(value) {
  for (const group of ARTIFACT_GROUPS) {
    const artifact = group.artifacts.find((item) => item.value === value)
    if (artifact) return { group, artifact }
  }
  return null
}
