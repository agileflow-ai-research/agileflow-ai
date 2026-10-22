export function extractionSummary(result) {
  return {
    status: result.status,
    document_type: result.document_type,
    metrics: result.metrics,
    warnings: result.warnings,
    extracted_at: result.extracted_at,
    extractor_version: result.extractor_version,
  }
}

export const USER_FACING_STATUS_LABELS = Object.freeze({
  NOT_STARTED: 'Not started',
  QUEUED: 'Preparing to start',
  RUNNING: 'In progress',
  WAITING_FOR_HUMAN: 'Needs review',
  NEEDS_ATTENTION: 'Needs attention',
  BLOCKED: 'Cannot continue',
  COMPLETE: 'Complete',
  COMPLETED: 'Complete',
  FAILED: 'Could not complete',
  INTERRUPTED: 'Interrupted — retry available',
  READY: 'Ready',
  READY_WITH_WARNINGS: 'Ready with warnings',
  LOCKED: 'Locked',
  NOT_APPLICABLE: 'Not required',
  RESERVED: 'Reserved — future development',
  NOT_IMPLEMENTED: 'Reserved — future development',
})

export const ARTIFACT_TYPE_LABELS = Object.freeze({
  SRS: 'Software Requirements Specification (SRS)',
  FUNCTIONAL_REQUIREMENTS: 'Functional Requirements',
  NON_FUNCTIONAL_REQUIREMENTS: 'Non-Functional Requirements',
  USER_STORIES: 'User Stories',
  ACCEPTANCE_CRITERIA: 'Acceptance Criteria',
  SYSTEM_ARCHITECTURE: 'System Architecture',
  UML_DIAGRAMS: 'UML Diagrams',
  DATABASE_SCHEMA: 'Database Schema',
  API_SPECIFICATION: 'API Specification',
  UI_WIREFRAMES: 'UI Wireframes',
  UI_FLOW: 'UI Flow',
  TECHNOLOGY_STACK: 'Technology Stack',
  TECHNICAL_CONSTRAINTS: 'Technical Constraints',
  IMPLEMENTATION_TASKS: 'Implementation Tasks',
  PRODUCT_BACKLOG: 'Product Backlog',
  TEST_CASES: 'Test Cases',
  UNIT_TEST_CASES: 'Unit Test Cases',
  API_TEST_CASES: 'API Test Cases',
  INTEGRATION_TEST_CASES: 'Integration Test Cases',
  FUNCTIONAL_TEST_CASES: 'Functional Test Cases',
  E2E_TEST_CASES: 'End-to-End Test Cases',
  SECURITY_TEST_CASES: 'Security Test Cases',
  ACCEPTANCE_TEST_CASES: 'Acceptance Test Cases',
  TEST_TRACEABILITY: 'Test Traceability',
  OTHER_CONTEXT: 'Supporting Context',
})

export const TECHNICAL_TERM_LABELS = Object.freeze({
  CANONICAL: 'Verified structured specification',
  DETERMINISTIC: 'Rule-based extraction',
  SEMANTIC: 'Grounded AI suggestion',
  HYBRID: 'Combined analysis',
  ZERO_SHOT: 'AI classification',
  CONSOLIDATION: 'Combine trusted sources',
  CHUNK: 'Source section',
  CANDIDATE: 'Suggested value',
  ARTIFACT: 'Specification item',
  FINGERPRINT: 'Version identifier',
  DIGEST: 'Saved version/checksum',
  READINESS_POLICY: 'Readiness rules',
  'READINESS POLICY': 'Readiness rules',
})

export function humanizePresentationValue(value, fallback = 'Not available') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
    .trim()
    .replace(/([a-z0-9])([A-Z])/gu, '$1 $2')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\s+/gu, ' ')
    .toLowerCase()
    .replace(/(^|\s)\S/gu, (letter) => letter.toUpperCase())
}

export function workflowStatusLabel(status, { approvalRequired = false, reserved = false } = {}) {
  if (reserved) return USER_FACING_STATUS_LABELS.RESERVED
  if (status === 'WAITING_FOR_HUMAN' && approvalRequired) return 'Needs approval'
  return USER_FACING_STATUS_LABELS[status] ?? humanizePresentationValue(status)
}

export function artifactTypeLabel(value) {
  return ARTIFACT_TYPE_LABELS[value] ?? humanizePresentationValue(value)
}

export function technicalTermLabel(value) {
  return TECHNICAL_TERM_LABELS[value] ?? humanizePresentationValue(value)
}


export function chunkSource(chunk) {
  const source = chunk.provenance
  if (source.structured_path) return `Source path: ${source.structured_path}`
  if (source.page_start) {
    return source.page_start === source.page_end
      ? `Source: page ${source.page_start}`
      : `Source: pages ${source.page_start}\u2013${source.page_end}`
  }
  if (source.block_start) {
    return source.block_start === source.block_end
      ? `Source: block ${source.block_start}`
      : `Source: blocks ${source.block_start}\u2013${source.block_end}`
  }
  if (source.line_start) {
    return source.line_start === source.line_end
      ? `Source: line ${source.line_start}`
      : `Source: lines ${source.line_start}\u2013${source.line_end}`
  }
  return `Source: ${source.original_filename}`
}


export function detectionLabel(value) {
  const exactLabels = {
    API_SPECIFICATION: 'API Specification',
    UI_FLOW: 'UI Flow',
    OTHER_CONTEXT: 'Other Context',
  }
  if (exactLabels[value]) return exactLabels[value]
  return humanizePresentationValue(value)
}


export function canonicalStatusLabel(status) {
  if (status === 'UNRESOLVED') return 'Needs Semantic Extraction'
  return detectionLabel(status)
}

export function canonicalSourceLabel(source) {
  const location = source.structured_path
    ? `Path ${source.structured_path}`
    : source.line_start
      ? `Lines ${source.line_start}${source.line_end && source.line_end !== source.line_start ? `–${source.line_end}` : ''}`
      : source.page_start
        ? `Pages ${source.page_start}${source.page_end && source.page_end !== source.page_start ? `–${source.page_end}` : ''}`
        : source.block_start !== null && source.block_start !== undefined
          ? `Blocks ${source.block_start}${source.block_end !== null && source.block_end !== source.block_start ? `–${source.block_end}` : ''}`
          : 'Document source'
  return `${source.original_filename} · ${location} · Chunk ${source.chunk_id}`
}

