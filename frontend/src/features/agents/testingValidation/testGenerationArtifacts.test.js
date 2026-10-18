import { describe, expect, it } from 'vitest'

import {
  artifactSourceOptions,
  buildTestGenerationFields,
  createArtifact,
  createUploadedArtifact,
  getArtifactGroup,
  hasUsableRequirementsArtifact,
  isUsableArtifact,
  testGenerationArtifactGroups,
  usableArtifactText,
} from './testGenerationArtifacts.js'

const uploadedDocument = (overrides = {}) => createUploadedArtifact({
  input_id: 'INPUT-010',
  artifact_type: 'ACCEPTANCE_CRITERIA',
  source_type: 'DOCUMENT',
  upload_reference: 'SAUP-0123456789abcdef0123456789abcdef',
  original_filename: 'acceptance.pdf',
  mime_type: 'application/pdf',
  processing_status: 'SUCCESS',
  extracted_content: 'AC-001: Email must be unique.',
  ...overrides,
})

const uploadedImage = (overrides = {}) => createUploadedArtifact({
  input_id: 'INPUT-020',
  artifact_type: 'UI_SPECIFICATION',
  source_type: 'IMAGE',
  upload_reference: 'SAUP-fedcba9876543210fedcba9876543210',
  original_filename: 'registration-wireframe.png',
  mime_type: 'image/png',
  processing_status: 'PENDING_ANALYSIS',
  ...overrides,
})

describe('testGenerationArtifactGroups', () => {
  it('maps every artifact type to exactly one frozen TEST_GENERATION field', () => {
    const pairs = testGenerationArtifactGroups.flatMap((group) => group.artifactTypes.map((type) => [type.value, type.field]))
    expect(pairs).toEqual([
      ['REQUIREMENTS', 'requirements'],
      ['USER_STORIES', 'user_stories'],
      ['ACCEPTANCE_CRITERIA', 'acceptance_criteria'],
      ['SRS', 'SRS'],
      ['SYSTEM_ARCHITECTURE', 'system_architecture'],
      ['API_SPECIFICATION', 'api_specification'],
      ['DATABASE_SCHEMA', 'database_schema'],
      ['UI_SPECIFICATION', 'ui_specification'],
      ['TECHNOLOGY_STACK', 'technology_stack'],
      ['EXISTING_SOURCE_CODE', 'existing_source_code'],
    ])
  })

  it('describes provenance without claiming an upstream agent ran', () => {
    const provenance = testGenerationArtifactGroups.map((group) => group.provenance)
    expect(provenance[0]).toMatch(/Normally supplied by Agent 1/)
    expect(provenance[1]).toMatch(/Normally supplied by Agent 2/)
    expect(provenance[2]).toMatch(/Normally supplied by Agent 3/)
    provenance.forEach((text) => expect(text).toMatch(/Manually provided in standalone mode/))
    expect(provenance.join(' ')).not.toMatch(/Imported from/)
  })

  it('looks up groups by id', () => {
    expect(getArtifactGroup('DESIGN').title).toBe('Design & Technical Artifacts')
    expect(getArtifactGroup('NOPE')).toBeNull()
  })

  it('offers TEXT, DOCUMENT, and IMAGE as selectable source types', () => {
    expect(artifactSourceOptions.map((option) => [option.value, option.disabled ?? false])).toEqual([
      ['TEXT', false], ['DOCUMENT', false], ['IMAGE', false],
    ])
  })
})

describe('createArtifact (TEXT)', () => {
  it('builds a ready TEXT artifact with its group and trimmed content', () => {
    expect(createArtifact({ input_id: 'INPUT-001', artifact_type: 'USER_STORIES', label: ' Stories ', content: '  As a patient  ' })).toEqual({
      input_id: 'INPUT-001', group: 'REQUIREMENTS', artifact_type: 'USER_STORIES', source_type: 'TEXT',
      label: 'Stories', content: 'As a patient', processing_status: 'READY',
    })
  })

  it('rejects unknown artifact types', () => {
    expect(() => createArtifact({ input_id: 'INPUT-001', artifact_type: 'FUNCTIONAL_REQUIREMENTS', content: 'x' })).toThrow(/Unknown artifact type/)
  })
})

describe('createUploadedArtifact (DOCUMENT / IMAGE model)', () => {
  it('keeps an opaque upload reference and filename metadata with no filesystem path', () => {
    const artifact = uploadedDocument()
    expect(artifact).toMatchObject({
      group: 'REQUIREMENTS', source_type: 'DOCUMENT', upload_reference: 'SAUP-0123456789abcdef0123456789abcdef',
      original_filename: 'acceptance.pdf', mime_type: 'application/pdf', processing_status: 'SUCCESS',
    })
    expect(Object.keys(artifact).join(' ')).not.toMatch(/path|storage|root/i)
  })

  it('accepts only server statuses valid for the source type', () => {
    expect(() => uploadedDocument({ processing_status: 'PENDING_ANALYSIS' })).toThrow(/Invalid DOCUMENT processing status/)
    expect(() => uploadedImage({ processing_status: 'SUCCESS' })).toThrow(/Invalid IMAGE processing status/)
    expect(() => createUploadedArtifact({ ...uploadedDocument(), source_type: 'TEXT' })).toThrow(/Unsupported uploaded source type/)
  })

  it('requires an upload reference and a known artifact type', () => {
    expect(() => uploadedDocument({ upload_reference: '' })).toThrow(/upload reference/)
    expect(() => uploadedDocument({ artifact_type: 'NOPE' })).toThrow(/Unknown artifact type/)
  })

  it('admits PARTIAL and FAILED document statuses so they can be shown honestly', () => {
    expect(uploadedDocument({ processing_status: 'PARTIAL' }).processing_status).toBe('PARTIAL')
    expect(uploadedDocument({ processing_status: 'FAILED', extracted_content: null }).processing_status).toBe('FAILED')
  })
})

describe('usableArtifactText', () => {
  it('returns TEXT content only when non-whitespace', () => {
    expect(usableArtifactText(createArtifact({ input_id: 'INPUT-001', artifact_type: 'SRS', content: '  spec  ' }))).toBe('spec')
    expect(usableArtifactText({ source_type: 'TEXT', content: ' \n ', processing_status: 'READY' })).toBe('')
  })

  it('returns document text for SUCCESS and for PARTIAL extraction with non-empty content', () => {
    expect(usableArtifactText(uploadedDocument())).toBe('AC-001: Email must be unique.')
    expect(usableArtifactText(uploadedDocument({ processing_status: 'PARTIAL', extracted_content: 'half the pages' }))).toBe('half the pages')
  })

  it('returns nothing for PARTIAL extraction with empty content, pending, or failed documents', () => {
    expect(usableArtifactText(uploadedDocument({ processing_status: 'PARTIAL', extracted_content: null }))).toBe('')
    expect(usableArtifactText(uploadedDocument({ processing_status: 'PENDING_EXTRACTION', extracted_content: null }))).toBe('')
    expect(usableArtifactText(uploadedDocument({ processing_status: 'FAILED', extracted_content: null }))).toBe('')
  })

  it('never returns image content, even if a client supplies extracted text', () => {
    expect(usableArtifactText(uploadedImage())).toBe('')
    expect(usableArtifactText(uploadedImage({ extracted_content: null }))).toBe('')
    expect(isUsableArtifact(uploadedImage())).toBe(false)
  })
})

describe('isUsableArtifact and the requirements gate', () => {
  it('rejects empty or whitespace-only TEXT artifacts', () => {
    expect(isUsableArtifact({ source_type: 'TEXT', content: '', processing_status: 'READY' })).toBe(false)
    expect(isUsableArtifact({ source_type: 'TEXT', content: ' \t ', processing_status: 'READY' })).toBe(false)
  })

  it('accepts a successfully extracted DOCUMENT as requirements context', () => {
    expect(hasUsableRequirementsArtifact([uploadedDocument({ artifact_type: 'SRS', input_id: 'INPUT-002' })])).toBe(true)
  })

  it('counts a PARTIAL requirements document with content, but not a pending or failed one', () => {
    expect(hasUsableRequirementsArtifact([uploadedDocument({ artifact_type: 'SRS', processing_status: 'PARTIAL', extracted_content: 'REQ-001 Login' })])).toBe(true)
    expect(hasUsableRequirementsArtifact([uploadedDocument({ artifact_type: 'SRS', processing_status: 'PENDING_EXTRACTION', extracted_content: null })])).toBe(false)
    expect(hasUsableRequirementsArtifact([uploadedDocument({ artifact_type: 'SRS', processing_status: 'FAILED', extracted_content: null })])).toBe(false)
    expect(hasUsableRequirementsArtifact([uploadedDocument({ artifact_type: 'SRS', processing_status: 'PARTIAL', extracted_content: '  ' })])).toBe(false)
  })

  it('lets a PARTIAL design document contribute context', () => {
    const partialDesign = uploadedDocument({ artifact_type: 'API_SPECIFICATION', processing_status: 'PARTIAL', extracted_content: 'POST /transfers' })
    expect(usableArtifactText(partialDesign)).toBe('POST /transfers')
    expect(buildTestGenerationFields([partialDesign]).api_specification).toContain('POST /transfers')
  })

  it('does not count a pending IMAGE, even as a requirements-group artifact', () => {
    expect(hasUsableRequirementsArtifact([uploadedImage({ artifact_type: 'REQUIREMENTS' })])).toBe(false)
  })

  it('does not count design artifacts or other groups as requirements', () => {
    expect(hasUsableRequirementsArtifact([createArtifact({ input_id: 'INPUT-001', artifact_type: 'API_SPECIFICATION', content: 'POST /x' })])).toBe(false)
  })
})

describe('buildTestGenerationFields (compatibility adapter)', () => {
  it('returns no fields for an empty collection', () => {
    expect(buildTestGenerationFields([])).toEqual({})
  })

  it('maps each TEXT artifact type to its frozen field with a provenance header', () => {
    const fields = buildTestGenerationFields([
      createArtifact({ input_id: 'INPUT-001', artifact_type: 'REQUIREMENTS', content: 'Req' }),
      createArtifact({ input_id: 'INPUT-002', artifact_type: 'SRS', content: 'SRS body' }),
      createArtifact({ input_id: 'INPUT-003', artifact_type: 'API_SPECIFICATION', content: 'POST /x' }),
      createArtifact({ input_id: 'INPUT-004', artifact_type: 'EXISTING_SOURCE_CODE', content: 'code()' }),
    ])
    expect(fields).toEqual({
      requirements: '--- Artifact: REQUIREMENTS / TEXT / INPUT-001 ---\nReq',
      SRS: '--- Artifact: SRS / TEXT / INPUT-002 ---\nSRS body',
      api_specification: '--- Artifact: API_SPECIFICATION / TEXT / INPUT-003 ---\nPOST /x',
      existing_source_code: '--- Artifact: EXISTING_SOURCE_CODE / TEXT / INPUT-004 ---\ncode()',
    })
  })

  it('combines several same-type artifacts deterministically in insertion order', () => {
    const artifacts = [
      createArtifact({ input_id: 'INPUT-002', artifact_type: 'ACCEPTANCE_CRITERIA', content: 'Second added first' }),
      createArtifact({ input_id: 'INPUT-001', artifact_type: 'ACCEPTANCE_CRITERIA', content: 'First listed second' }),
    ]
    const first = buildTestGenerationFields(artifacts)
    expect(first).toEqual(buildTestGenerationFields([...artifacts]))
    expect(first.acceptance_criteria).toBe(
      '--- Artifact: ACCEPTANCE_CRITERIA / TEXT / INPUT-002 ---\nSecond added first\n\n--- Artifact: ACCEPTANCE_CRITERIA / TEXT / INPUT-001 ---\nFirst listed second',
    )
  })

  it('includes extracted DOCUMENT content with filename and status provenance, mixed with TEXT', () => {
    const fields = buildTestGenerationFields([
      createArtifact({ input_id: 'INPUT-001', artifact_type: 'ACCEPTANCE_CRITERIA', content: 'Refund rules' }),
      uploadedDocument({ input_id: 'INPUT-002' }),
    ])
    expect(fields.acceptance_criteria).toBe(
      '--- Artifact: ACCEPTANCE_CRITERIA / TEXT / INPUT-001 ---\nRefund rules\n\n'
      + '--- Artifact: ACCEPTANCE_CRITERIA / DOCUMENT / INPUT-002 ---\nFile: acceptance.pdf\nExtraction Status: SUCCESS\nAC-001: Email must be unique.',
    )
  })

  it('keeps PARTIAL status and the partial warning in the artifact boundary', () => {
    const fields = buildTestGenerationFields([
      uploadedDocument({ input_id: 'INPUT-005', artifact_type: 'SRS', processing_status: 'PARTIAL', extracted_content: 'REQ-001 Login' }),
    ])
    expect(fields.SRS).toBe(
      '--- Artifact: SRS / DOCUMENT / INPUT-005 ---\nFile: acceptance.pdf\nExtraction Status: PARTIAL\nWarning: Partial extraction\nREQ-001 Login',
    )
  })

  it('never inserts pending, failed, empty-partial, or image content into the flattened payload', () => {
    const fields = buildTestGenerationFields([
      createArtifact({ input_id: 'INPUT-001', artifact_type: 'REQUIREMENTS', content: 'Usable requirement' }),
      uploadedDocument({ input_id: 'INPUT-002', artifact_type: 'SRS', processing_status: 'PENDING_EXTRACTION', extracted_content: 'stale text must not leak' }),
      uploadedDocument({ input_id: 'INPUT-004', artifact_type: 'USER_STORIES', processing_status: 'FAILED', extracted_content: 'failed must not leak' }),
      uploadedDocument({ input_id: 'INPUT-006', artifact_type: 'SYSTEM_ARCHITECTURE', processing_status: 'PARTIAL', extracted_content: '   ' }),
      uploadedImage({ input_id: 'INPUT-003' }),
    ])
    expect(fields).toEqual({ requirements: '--- Artifact: REQUIREMENTS / TEXT / INPUT-001 ---\nUsable requirement' })
    expect(JSON.stringify(fields)).not.toMatch(/stale text|failed must|registration-wireframe|ui_specification|user_stories|system_architecture|SRS/)
  })
})
