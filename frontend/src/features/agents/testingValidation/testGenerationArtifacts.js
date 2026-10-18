// Standalone TEST_GENERATION artifact model and compatibility adapter.
//
// In the integrated workflow, approved Agent 1/2/3 outputs feed Agent 4. In standalone
// mode nothing upstream has run, so the user supplies equivalent artifacts manually.
// This module describes that manual input; it never claims an upstream agent ran.
//
// Field names follow the Agent 3 input model where they overlap (input_id, source_type,
// artifact_type, label, content, upload_id as upload_reference, original_filename, mime_type).

export const artifactSourceOptions = Object.freeze([
  { value: 'TEXT', label: 'Text' },
  { value: 'DOCUMENT', label: 'Document' },
  { value: 'IMAGE', label: 'Image' },
])

// Processing states use the server vocabulary. Document statuses come from the shared extraction
// result (SUCCESS, PARTIAL, FAILED). Images have no analysis path, so they stay PENDING_ANALYSIS.
export const processingStatusLabels = Object.freeze({
  READY: 'Ready',
  PENDING_EXTRACTION: 'Pending extraction',
  SUCCESS: 'Extracted',
  PARTIAL: 'Partially Extracted',
  FAILED: 'Extraction failed',
  PENDING_ANALYSIS: 'Pending analysis',
})

// Shown wherever a partially extracted document appears. Plain wording, not an error state.
export const partialExtractionWarning = 'Some content could not be extracted. This artifact is usable, but test generation may have incomplete source coverage.'

const allowedUploadStatuses = Object.freeze({
  DOCUMENT: Object.freeze(['PENDING_EXTRACTION', 'SUCCESS', 'PARTIAL', 'FAILED']),
  IMAGE: Object.freeze(['PENDING_ANALYSIS']),
})

export const testGenerationArtifactGroups = Object.freeze([
  {
    id: 'REQUIREMENTS',
    title: 'Requirements Artifacts',
    provenance: 'Normally supplied by Agent 1 — Requirements Elicitation and Quality Engineering. Manually provided in standalone mode.',
    artifactTypes: [
      { value: 'REQUIREMENTS', label: 'Requirements', field: 'requirements' },
      { value: 'USER_STORIES', label: 'User Stories', field: 'user_stories' },
      { value: 'ACCEPTANCE_CRITERIA', label: 'Acceptance Criteria', field: 'acceptance_criteria' },
      { value: 'SRS', label: 'Software Requirements Specification (SRS)', field: 'SRS' },
    ],
  },
  {
    id: 'DESIGN',
    title: 'Design & Technical Artifacts',
    provenance: 'Normally supplied by Agent 2 — Design, Planning, and Agile Project Management. Manually provided in standalone mode.',
    artifactTypes: [
      { value: 'SYSTEM_ARCHITECTURE', label: 'System Architecture', field: 'system_architecture' },
      { value: 'API_SPECIFICATION', label: 'API Specification', field: 'api_specification' },
      { value: 'DATABASE_SCHEMA', label: 'Database Schema', field: 'database_schema' },
      { value: 'UI_SPECIFICATION', label: 'UI / Wireframe Specification', field: 'ui_specification' },
      { value: 'TECHNOLOGY_STACK', label: 'Technology Stack', field: 'technology_stack' },
    ],
  },
  {
    id: 'IMPLEMENTATION',
    title: 'Implementation Context',
    provenance: 'Normally supplied by Agent 3 — Code Generation and Execution. Manually provided in standalone mode.',
    artifactTypes: [
      { value: 'EXISTING_SOURCE_CODE', label: 'Existing Source Code / Implementation Context', field: 'existing_source_code' },
    ],
  },
])

const artifactTypeIndex = new Map(
  testGenerationArtifactGroups.flatMap((group) => group.artifactTypes.map((type) => [type.value, { ...type, group: group.id }])),
)

export function getArtifactGroup(groupId) {
  return testGenerationArtifactGroups.find((group) => group.id === groupId) ?? null
}

export function artifactTypeLabel(value) {
  return artifactTypeIndex.get(value)?.label ?? value
}

export function artifactSourceLabel(value) {
  return artifactSourceOptions.find((option) => option.value === value)?.label ?? value
}

export function processingStatusLabel(value) {
  return processingStatusLabels[value] ?? value
}

export function isPartialArtifact(artifact) {
  return artifact.source_type === 'DOCUMENT' && artifact.processing_status === 'PARTIAL'
}

// Returns the text that may be used as Agent 4 context, or an empty string.
// TEXT and DOCUMENT with SUCCESS or PARTIAL extraction contribute when non-empty. PARTIAL is usable
// but incomplete, matching Agent 3's readiness rule. Pending, failed, and image artifacts never do.
export function usableArtifactText(artifact) {
  if (artifact.source_type === 'TEXT') return (artifact.content ?? '').trim()
  if (artifact.source_type === 'DOCUMENT' && ['SUCCESS', 'PARTIAL'].includes(artifact.processing_status)) {
    return (artifact.extracted_content ?? '').trim()
  }
  return ''
}

export function isUsableArtifact(artifact) {
  return usableArtifactText(artifact).length > 0
}

export function createArtifact({ input_id, artifact_type, label = '', content }) {
  const type = artifactTypeIndex.get(artifact_type)
  if (!type) throw new Error(`Unknown artifact type: ${artifact_type}`)
  return {
    input_id,
    group: type.group,
    artifact_type,
    source_type: 'TEXT',
    label: label.trim(),
    content: content.trim(),
    processing_status: 'READY',
  }
}

// Model entry point for DOCUMENT/IMAGE artifacts. The file itself is never stored here: only
// an opaque upload reference, the browser-independent filename and MIME metadata returned by
// trusted upload validation, and the processing state. No upload producer exists yet.
export function createUploadedArtifact({
  input_id,
  artifact_type,
  source_type,
  upload_reference,
  original_filename,
  mime_type,
  processing_status,
  extracted_content = null,
  label = '',
}) {
  const type = artifactTypeIndex.get(artifact_type)
  if (!type) throw new Error(`Unknown artifact type: ${artifact_type}`)
  if (!allowedUploadStatuses[source_type]) throw new Error(`Unsupported uploaded source type: ${source_type}`)
  if (!allowedUploadStatuses[source_type].includes(processing_status)) {
    throw new Error(`Invalid ${source_type} processing status: ${processing_status}`)
  }
  if (!upload_reference) throw new Error('An uploaded artifact requires an upload reference.')
  return {
    input_id,
    group: type.group,
    artifact_type,
    source_type,
    label: label.trim(),
    content: null,
    upload_reference,
    original_filename,
    mime_type,
    processing_status,
    extracted_content: extracted_content?.trim() || null,
  }
}

export function previewText(value, limit = 240) {
  const text = value.trim()
  return text.length > limit ? `${text.slice(0, limit).trimEnd()}…` : text
}

// Provenance lines for a DOCUMENT artifact. The status comes straight from the server, and a
// partial extraction carries an explicit warning line so the limitation survives into the payload.
function documentProvenanceLines(artifact) {
  const lines = []
  if (artifact.original_filename) lines.push(`File: ${artifact.original_filename}`)
  lines.push(`Extraction Status: ${artifact.processing_status}`)
  if (isPartialArtifact(artifact)) lines.push('Warning: Partial extraction')
  return lines
}

// Adapter: collapses collected artifacts into the frozen TEST_GENERATION fields accepted by
// the existing run endpoint. Only usable text enters a field. Each artifact keeps a provenance
// boundary with its ID, type, source, and status, and artifacts for one field are joined in
// insertion order. Temporary glue until Step 2 normalized context.
export function buildTestGenerationFields(artifacts) {
  const fields = {}
  artifacts.forEach((artifact) => {
    const text = usableArtifactText(artifact)
    const field = artifactTypeIndex.get(artifact.artifact_type)?.field
    if (!text || !field) return
    const provenance = artifact.source_type === 'DOCUMENT'
      ? documentProvenanceLines(artifact)
      : (artifact.original_filename ? [`File: ${artifact.original_filename}`] : [])
    const header = `--- Artifact: ${artifact.artifact_type} / ${artifact.source_type} / ${artifact.input_id} ---`
    const block = [header, ...provenance, text].join('\n')
    fields[field] = fields[field] ? `${fields[field]}\n\n${block}` : block
  })
  return fields
}

export function hasUsableRequirementsArtifact(artifacts) {
  return artifacts.some((artifact) => artifact.group === 'REQUIREMENTS' && isUsableArtifact(artifact))
}
