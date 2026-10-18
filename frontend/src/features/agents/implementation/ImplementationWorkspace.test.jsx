import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  buildImplementationCanonicalArtifacts,
  buildImplementationSemanticArtifacts,
  buildImplementationHybridDetections,
  connectGitHub,
  createGitHubRepository,
  deleteImplementationInputFile,
  evaluateImplementationReadiness,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentChunks,
  getImplementationDocumentExtraction,
  getImplementationRuleDetections,
  getImplementationZeroShotDetections,
  getImplementationHybridDetections,
  getImplementationHumanReviews,
  getImplementationCanonicalArtifacts,
  getImplementationSemanticArtifacts,
  getGitHubRepository,
  prepareImplementationDocumentChunks,
  runImplementationRuleDetector,
  runImplementationZeroShotClassifier,
  saveImplementationHumanReview,
  uploadImplementationInputFile,
} from './services/implementationAgentService.js'
import { navigateToGitHub } from './utils/githubNavigation.js'
import ImplementationWorkspace from './ImplementationWorkspace.jsx'

vi.mock('./services/implementationAgentService.js', () => ({
  buildImplementationCanonicalArtifacts: vi.fn(),
  buildImplementationSemanticArtifacts: vi.fn(),
  buildImplementationHybridDetections: vi.fn(),
  getImplementationHybridDetections: vi.fn(),
  getImplementationHumanReviews: vi.fn(),
  getImplementationCanonicalArtifacts: vi.fn(),
  getImplementationSemanticArtifacts: vi.fn(),
  saveImplementationHumanReview: vi.fn(),
  uploadImplementationInputFile: vi.fn(),
  deleteImplementationInputFile: vi.fn(),
  evaluateImplementationReadiness: vi.fn(),
  extractImplementationDocument: vi.fn(),
  getImplementationDocumentExtraction: vi.fn(),
  getImplementationDocumentChunks: vi.fn(),
  prepareImplementationDocumentChunks: vi.fn(),
  getImplementationRuleDetections: vi.fn(),
  runImplementationRuleDetector: vi.fn(),
  getImplementationZeroShotDetections: vi.fn(),
  runImplementationZeroShotClassifier: vi.fn(),
  connectGitHub: vi.fn(),
  createGitHubRepository: vi.fn(),
  getGitHubConnection: vi.fn(),
  getGitHubRepository: vi.fn(),
}))
vi.mock('./utils/githubNavigation.js', () => ({ navigateToGitHub: vi.fn() }))

const project = {
  agent_project_id: 'AGP-003', agent_type: 'IMPLEMENTATION',
  name: 'BookEase Builder', domain: 'Hospitality',
}

const outputLabels = [
  'Project Structure', 'Frontend Code', 'Backend Code',
  'Database Implementation', 'API Implementation', 'Configuration Files',
  'Container Configuration', 'Git Summary',
]

function metadata(overrides = {}) {
  return {
    upload_id: 'A3UP-0123456789abcdef0123456789abcdef',
    source_type: 'DOCUMENT',
    artifact_type: 'API_SPECIFICATION',
    label: 'Booking API',
    original_filename: 'bookease-api.pdf',
    mime_type: 'application/pdf',
    extension: '.pdf',
    size_bytes: 250880,
    sha256: 'a'.repeat(64),
    created_at: '2026-10-15T10:00:00Z',
    ...overrides,
  }
}

function connectedGitHub() {
  return {
    connected: true,
    github_user_id: 123,
    github_login: 'octocat',
    avatar_url: 'https://avatars.example/octocat.png',
    installation_id: 456,
    account_type: 'User',
  }
}

function repositoryMetadata(overrides = {}) {
  return {
    created: true,
    repository_id: 789,
    owner: 'octocat',
    name: 'quickbook',
    full_name: 'octocat/quickbook',
    html_url: 'https://github.com/octocat/quickbook',
    visibility: 'PRIVATE',
    private: true,
    default_branch: 'main',
    is_empty: true,
    created_at: '2026-10-16T08:00:00Z',
    ...overrides,
  }
}

function extractionResult(overrides = {}) {
  return {
    upload_id: metadata().upload_id,
    agent_project_id: 'AGP-003',
    artifact_type: 'API_SPECIFICATION',
    original_filename: 'bookease-api.pdf',
    document_type: 'PDF',
    status: 'SUCCESS',
    extractor_version: '1',
    source_sha256: 'a'.repeat(64),
    content: {
      pages: [{ page_number: 1, text: 'POST /bookings creates a booking.' }],
      combined_text: 'POST /bookings creates a booking.',
    },
    metrics: {
      page_count: 1,
      processed_page_count: 1,
      pages_with_text: 1,
      pages_without_text: 0,
      extracted_character_count: 33,
    },
    warnings: [],
    extracted_at: '2026-10-16T10:00:00Z',
    ...overrides,
  }
}

function chunkResult(overrides = {}) {
  return {
    upload_id: metadata().upload_id,
    agent_project_id: 'AGP-003',
    source_sha256: 'a'.repeat(64),
    document_type: 'PDF',
    extraction_version: '1',
    chunker_version: '1',
    status: 'SUCCESS',
    metrics: {
      chunk_count: 1, total_lexical_tokens: 7, average_chunk_tokens: 7,
      min_chunk_tokens: 7, max_chunk_tokens: 7,
    },
    warnings: [],
    chunks: [{
      chunk_id: 'CHK-0123456789ABCDEF0123', chunk_index: 0,
      text: 'POST /bookings creates a booking.', text_hash: 'b'.repeat(64),
      token_count: 7, character_count: 33,
      context: {
        heading_path: ['API Design'], section_title: 'API Design', heading_depth: 1,
        structure_type: 'PARAGRAPH', structural_warning: null,
      },
      provenance: {
        upload_id: metadata().upload_id, agent_project_id: 'AGP-003',
        original_filename: 'bookease-api.pdf', source_sha256: 'a'.repeat(64),
        document_type: 'PDF', page_start: 3, page_end: 4,
        block_start: null, block_end: null, line_start: null, line_end: null,
        structured_path: null,
      },
    }],
    created_at: '2026-10-18T10:00:00Z',
    ...overrides,
  }
}

function ruleDetectionResult(overrides = {}) {
  return {
    upload_id: metadata().upload_id,
    agent_project_id: 'AGP-003',
    original_filename: 'bookease-api.pdf',
    source_sha256: 'a'.repeat(64),
    document_type: 'PDF',
    extraction_version: '1',
    chunker_version: '1',
    rule_detector_version: '1',
    metrics: {
      chunk_count: 1, classified_chunk_count: 1, other_context_chunk_count: 0,
      prediction_count: 2,
      per_label_counts: { API_SPECIFICATION: 1, ACCEPTANCE_CRITERIA: 1 },
      strong_prediction_count: 1, moderate_prediction_count: 1, weak_prediction_count: 0,
    },
    detections: [{
      chunk_id: chunkResult().chunks[0].chunk_id,
      text_hash: chunkResult().chunks[0].text_hash,
      unclassified: false,
      predictions: [{
        label: 'API_SPECIFICATION', rule_score: 0.96, strength: 'STRONG',
        evidence: [{ rule_id: 'API_HTTP_METHOD_PATH', matched_text: 'POST /bookings', source: 'TEXT' }],
      }, {
        label: 'ACCEPTANCE_CRITERIA', rule_score: 0.62, strength: 'MODERATE',
        evidence: [{ rule_id: 'AC_EXPECTED_RESULT', matched_text: 'Expected Result:', source: 'TEXT' }],
      }],
    }],
    created_at: '2026-10-18T11:00:00Z',
    ...overrides,
  }
}

function hybridDetectionResult(overrides = {}) {
  return {
    upload_id: metadata().upload_id,
    agent_project_id: 'AGP-003',
    metrics: {
      chunk_count: 1, auto_candidate_count: 1, review_required_count: 1,
      rejected_count: 1, rule_and_model_count: 1, rule_only_count: 0,
      model_only_count: 1, disagreement_count: 0, insufficient_evidence_count: 1,
      label_explosion_chunk_count: 1, ambiguous_chunk_count: 1,
      per_label_candidate_counts: {},
    },
    chunks: [{
      chunk_id: chunkResult().chunks[0].chunk_id,
      text_hash: chunkResult().chunks[0].text_hash,
      diagnostics: {
        model_label_explosion: true, model_ambiguous: true, top_model_margin: 0.02,
        top_model_scores: [
          { label: 'API_SPECIFICATION', score: 0.91 },
          { label: 'DATABASE_SCHEMA', score: 0.89 },
        ],
      },
      candidates: [{
        label: 'API_SPECIFICATION', evidence_state: 'RULE_AND_MODEL', decision: 'AUTO_CANDIDATE',
        rule: { matched: true, score: 0.94, strength: 'STRONG', evidence: [{ rule_id: 'HTTP_METHOD_PATH', matched_text: 'POST /bookings', source: 'TEXT' }] },
        model: { score: 0.91 }, reason_codes: ['RULE_MODEL_AGREEMENT'],
      }, {
        label: 'DATABASE_SCHEMA', evidence_state: 'MODEL_ONLY', decision: 'REVIEW_REQUIRED',
        rule: { matched: false, score: null, strength: null, evidence: [] },
        model: { score: 0.89 }, reason_codes: ['MODEL_ONLY_REQUIRES_REVIEW', 'MODEL_LABEL_EXPLOSION'],
      }, {
        label: 'OTHER_CONTEXT', evidence_state: 'INSUFFICIENT_EVIDENCE', decision: 'REJECTED',
        rule: { matched: false, score: null, strength: null, evidence: [] },
        model: { score: 0.1 }, reason_codes: ['WEAK_EVIDENCE'],
      }],
    }],
    ...overrides,
  }
}

function humanReviewState({ complete = false, stale = false } = {}) {
  const chunk = chunkResult().chunks[0]
  const candidate = hybridDetectionResult().chunks[0].candidates[0]
  const decision = {
    action: 'ACCEPT', source_candidate_label: candidate.label,
    final_label: candidate.label, note: 'Verified against source.',
    reviewer_owner_id: 'USR-001', reviewed_at: '2026-10-18T12:00:00Z',
  }
  const chunkReview = {
    chunk_id: chunk.chunk_id, chunk_index: chunk.chunk_index,
    text_hash: chunk.text_hash, provenance: chunk.provenance,
    machine_snapshot: { hybrid_result_digest: 'c'.repeat(64), candidate_labels: [candidate.label] },
    decisions: complete ? [decision] : [],
    verified_labels: complete ? [candidate.label] : [],
    review_status: complete ? 'VERIFIED' : 'UNREVIEWED',
    reviewed_at: complete ? '2026-10-18T12:00:00Z' : null,
  }
  return {
    review: {
      upload_id: metadata().upload_id, agent_project_id: 'AGP-003',
      original_filename: metadata().original_filename, source_sha256: 'a'.repeat(64),
      document_type: 'PDF', pipeline: {}, rule_result_digest: 'a'.repeat(64),
      zero_shot_result_digest: 'b'.repeat(64), hybrid_result_digest: 'c'.repeat(64),
      review_fingerprint: 'd'.repeat(64), reviewer_owner_id: complete ? 'USR-001' : null,
      review_status: complete ? 'COMPLETE' : 'NOT_STARTED', chunks: [chunkReview],
      metrics: {
        total_chunks: 1, verified_chunks: complete ? 1 : 0,
        remaining_chunks: complete ? 0 : 1,
        accepted_candidate_count: complete ? 1 : 0,
        relabeled_candidate_count: 0, excluded_candidate_count: 0,
        added_label_count: 0, review_completion_percentage: complete ? 100 : 0,
      },
      created_at: complete ? '2026-10-18T12:00:00Z' : null,
      updated_at: complete ? '2026-10-18T12:00:00Z' : null,
    },
    review_queue: [{
      priority: 1, chunk,
      rule: ruleDetectionResult().detections[0],
      model: zeroShotResult().chunks[0],
      hybrid: { ...hybridDetectionResult().chunks[0], candidates: [candidate] },
      review: chunkReview,
    }],
    stale,
    stale_message: stale ? 'Artifact analysis changed. Human verification must be performed again.' : null,
  }
}

function canonicalArtifactResult() {
  const chunk = chunkResult().chunks[0]
  return {
    upload_id: metadata().upload_id, agent_project_id: 'AGP-003',
    source_sha256: 'a'.repeat(64), human_review_fingerprint: 'd'.repeat(64),
    canonical_schema_version: '1', extractor_version: '1', status: 'PARTIAL',
    artifacts: [{
      artifact_id: 'CA-0123456789ABCDEF01234567', artifact_type: 'API_SPECIFICATION',
      extraction_method: 'DETERMINISTIC', status: 'PARTIAL',
      data: { endpoints: [{ id: null, method: 'POST', path: '/bookings', description: null, request_fields: [], response_statuses: [], source_refs: [] }] },
      source_refs: [{
        upload_id: metadata().upload_id, chunk_id: chunk.chunk_id, text_hash: chunk.text_hash,
        original_filename: metadata().original_filename, page_start: 3, page_end: 4,
        block_start: null, block_end: null, line_start: null, line_end: null, structured_path: null,
      }],
      unresolved_items: [{ reason: 'API_REQUEST_STRUCTURE_NOT_EXPLICIT', source_ref: null }],
      canonical_schema_version: '1', extractor_version: '1', created_at: '2026-10-18T13:00:00Z',
    }, {
      artifact_id: 'CA-UNRESOLVED000000000000', artifact_type: 'DATABASE_SCHEMA',
      extraction_method: 'DETERMINISTIC', status: 'UNRESOLVED', data: { entities: [] },
      source_refs: [{ upload_id: metadata().upload_id, chunk_id: chunk.chunk_id, text_hash: chunk.text_hash,
        original_filename: metadata().original_filename, page_start: 3, page_end: 4,
        block_start: null, block_end: null, line_start: null, line_end: null, structured_path: null }],
      unresolved_items: [{ reason: 'NO_EXPLICIT_DATABASE_STRUCTURE', source_ref: null }],
      canonical_schema_version: '1', extractor_version: '1', created_at: '2026-10-18T13:00:00Z',
    }],
    metrics: { verified_chunk_count: 1, canonical_artifact_count: 2, complete_artifact_count: 0,
      partial_artifact_count: 1, unresolved_artifact_count: 1,
      per_artifact_type_counts: { API_SPECIFICATION: 1, DATABASE_SCHEMA: 1 } },
    warnings: ['NO_EXPLICIT_DATABASE_STRUCTURE'], created_at: '2026-10-18T13:00:00Z',
  }
}

function semanticArtifactResult() {
  return {
    upload_id: metadata().upload_id, agent_project_id: 'AGP-003',
    model_id: 'Qwen/Qwen3-1.7B', model_revision: '7'.repeat(40),
    results: [{
      artifact_id: 'CA-0123456789ABCDEF01234567', artifact_type: 'API_SPECIFICATION',
      deterministic_status: 'PARTIAL', status: 'HUMAN_REVIEW_REQUIRED',
      model: { model_id: 'Qwen/Qwen3-1.7B', revision: '7'.repeat(40), device: 'cpu' },
      generation: { attempt_count: 1, input_token_count: 100, output_token_count: 30, generation_ms: 20, first_model_load_ms: 200 },
      semantic_proposal: { artifact_type: 'API_SPECIFICATION', endpoints: [{ method: null, path: null, request_fields: ['name'], response_statuses: [] }] },
      validation: {
        proposal_status: 'HUMAN_REVIEW_REQUIRED', accepted_facts: 1,
        rejected_facts: 1, conflict_count: 1,
        rejections: [{ code: 'UNSUPPORTED_BY_SOURCE', field_path: 'endpoints[0].method', proposed_value: 'POST', reason: 'No valid source evidence' }],
        conflicts: [{ code: 'SEMANTIC_DETERMINISTIC_CONFLICT', field_path: 'endpoints[0].method', deterministic_value: 'POST', semantic_value: 'PUT', semantic_evidence: [{ quote: 'PUT /bookings', chunk_id: chunkResult().chunks[0].chunk_id }] }],
      },
      merged_preview: {
        data: { endpoints: [{ method: 'POST', path: '/bookings', request_fields: ['name'] }] },
        field_provenance: [{ field_path: 'endpoints[0].request_fields[0]', origin: 'SEMANTIC', source_refs: [], evidence: [{ quote: 'Create a booking using name.', chunk_id: chunkResult().chunks[0].chunk_id }] }],
        conflicts: [],
      },
    }],
    metrics: {
      artifact_count: 2, target_artifact_count: 1, skipped_complete_count: 1,
      grounded_count: 0, partially_grounded_count: 0,
      human_review_required_count: 1, rejected_count: 0,
      model_output_invalid_count: 0, model_error_count: 0,
      accepted_fact_count: 1, rejected_fact_count: 1, conflict_count: 1,
      total_attempt_count: 1, total_generation_ms: 20, first_model_load_ms: 200,
    },
  }
}

function zeroShotResult(overrides = {}) {
  const labels = [
    'FUNCTIONAL_REQUIREMENTS', 'NON_FUNCTIONAL_REQUIREMENTS', 'USER_STORIES',
    'ACCEPTANCE_CRITERIA', 'SYSTEM_ARCHITECTURE', 'DATABASE_SCHEMA',
    'API_SPECIFICATION', 'UI_FLOW', 'TECHNOLOGY_STACK', 'TECHNICAL_CONSTRAINTS',
    'IMPLEMENTATION_TASKS', 'TEST_CASES', 'OTHER_CONTEXT',
  ]
  return {
    upload_id: metadata().upload_id,
    agent_project_id: 'AGP-003',
    original_filename: 'bookease-api.pdf',
    source_sha256: 'a'.repeat(64),
    document_type: 'PDF',
    extraction_version: '1',
    chunker_version: '1',
    classifier_type: 'ZERO_SHOT_NLI',
    classifier_version: '1',
    score_semantics: 'ZERO_SHOT_NLI_NOT_DOMAIN_CALIBRATED',
    model: {
      model_id: 'MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli',
      revision: '6f5cf0a2b59cabb106aca4c287eed12e357e90eb',
      task: 'zero-shot-classification',
      hypothesis_template: 'This software-engineering text describes {}.',
      multi_label: true, label_map_version: '1', template_version: '1', device: 'cpu',
    },
    status: 'SUCCESS',
    chunks: [{
      chunk_id: chunkResult().chunks[0].chunk_id,
      text_hash: chunkResult().chunks[0].text_hash,
      provenance: chunkResult().chunks[0].provenance,
      model_token_count: 42, model_max_length: 512, input_truncated: false,
      classification_succeeded: true, inference_ms: 80,
      scores: labels.map((label, index) => ({
        label, score: index === 6 ? 0.94 : index === 3 ? 0.73 : 0.1,
      })),
      display_predictions: [
        { label: 'API_SPECIFICATION', score: 0.94 },
        { label: 'ACCEPTANCE_CRITERIA', score: 0.73 },
      ],
    }],
    metrics: {
      chunk_count: 1, classified_chunk_count: 1, truncated_chunk_count: 0,
      failed_chunk_count: 0, average_inference_ms_per_chunk: 80,
      total_inference_ms: 80, top_label_counts: { API_SPECIFICATION: 1 },
    },
    warnings: [],
    created_at: '2026-10-18T12:00:00Z',
    ...overrides,
  }
}

function readinessResult(overrides = {}) {
  return {
    status: 'READY_WITH_WARNINGS',
    input_fingerprint: 'b'.repeat(64),
    summary: { errors: 0, warnings: 1, info: 1 },
    coverage: {
      requirements: true, design: false, implementation: false,
      tests: false, visual_context_pending: false,
    },
    selected_outputs: ['BACKEND_CODE'],
    output_readiness: [{ output: 'BACKEND_CODE', ready: true, findings: ['RF-1111111111111111'] }],
    effective_stack: {
      frontend: 'React + Vite', styling: 'Plain CSS', backend: 'Node.js + Express.js',
      database: 'MySQL', language: 'JavaScript', api_style: 'REST',
    },
    artifact_manifest: [],
    findings: [{
      finding_id: 'RF-1111111111111111', code: 'PRECODE_TEST_CONTEXT_MISSING',
      severity: 'WARNING', title: 'Pre-code test context is missing',
      message: 'No pre-code test artifacts were supplied.', affected_outputs: ['BACKEND_CODE'],
      sources: [], requires_human_decision: false, allowed_resolutions: [],
      category: null, provided_value: null, supported_value: null,
      resolved: false, resolution: null,
    }, {
      finding_id: 'RF-2222222222222222', code: 'NON_FUNCTIONAL_CONTEXT_MISSING',
      severity: 'INFO', title: 'Non-functional context is missing',
      message: 'No non-functional requirements were supplied.', affected_outputs: ['BACKEND_CODE'],
      sources: [], requires_human_decision: false, allowed_resolutions: [],
      category: null, provided_value: null, supported_value: null,
      resolved: false, resolution: null,
    }],
    human_resolutions: [],
    evaluated_at: '2026-10-17T08:00:00Z',
    ...overrides,
  }
}

async function reachWorkspaceReview(user, output = 'Backend Code') {
  await user.type(screen.getByLabelText(/Content/), 'Users can create bookings.')
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await user.click(screen.getByRole('checkbox', { name: output }))
  await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
}

async function chooseSource(user, sourceType) {
  await user.selectOptions(screen.getByLabelText(/Input Source/), sourceType)
}

async function attachFile(user, sourceType, file, responseMetadata) {
  uploadImplementationInputFile.mockResolvedValue({ data: responseMetadata })
  await chooseSource(user, sourceType)
  const picker = screen.getByLabelText(sourceType === 'DOCUMENT' ? /Document file/ : /Image file/)
  await user.upload(picker, file)
  await user.click(screen.getByRole('button', { name: 'Attach File' }))
  await screen.findByText('Uploaded / Attached')
}

async function attachAndPrepareDocument(user) {
  await attachFile(
    user,
    'DOCUMENT',
    new File(['document'], 'bookease-api.pdf', { type: 'application/pdf' }),
    metadata(),
  )
  await user.click(await screen.findByRole('button', { name: 'Prepare Semantic Chunks' }))
  await screen.findByText('\u2713 Prepared')
}

describe('ImplementationWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')
    getGitHubConnection.mockResolvedValue({ data: { connected: false } })
    getGitHubRepository.mockResolvedValue({ data: { created: false } })
    extractImplementationDocument.mockResolvedValue({ data: extractionResult() })
    getImplementationDocumentExtraction.mockResolvedValue({ data: extractionResult() })
    prepareImplementationDocumentChunks.mockResolvedValue({ data: chunkResult() })
    getImplementationDocumentChunks.mockResolvedValue({ data: chunkResult() })
    runImplementationRuleDetector.mockResolvedValue({ data: ruleDetectionResult() })
    getImplementationRuleDetections.mockResolvedValue({ data: ruleDetectionResult() })
    runImplementationZeroShotClassifier.mockResolvedValue({ data: zeroShotResult() })
    getImplementationZeroShotDetections.mockResolvedValue({ data: zeroShotResult() })
    buildImplementationHybridDetections.mockResolvedValue({ data: hybridDetectionResult() })
    getImplementationHybridDetections.mockResolvedValue({ data: hybridDetectionResult() })
    getImplementationHumanReviews.mockResolvedValue({ data: humanReviewState() })
    saveImplementationHumanReview.mockResolvedValue({ data: humanReviewState({ complete: true }) })
    buildImplementationCanonicalArtifacts.mockResolvedValue({ data: canonicalArtifactResult() })
    getImplementationCanonicalArtifacts.mockResolvedValue({ data: canonicalArtifactResult() })
    buildImplementationSemanticArtifacts.mockResolvedValue({ data: semanticArtifactResult() })
    getImplementationSemanticArtifacts.mockResolvedValue({ data: semanticArtifactResult() })
    evaluateImplementationReadiness.mockResolvedValue({ data: readinessResult() })
  })

  it('prepares, summarizes, reviews, and force-rebuilds semantic chunks', async () => {
    const user = userEvent.setup()
    let resolvePreparation
    prepareImplementationDocumentChunks.mockReturnValueOnce(new Promise((resolve) => { resolvePreparation = resolve }))
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['document'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    expect(await screen.findByText('Not prepared')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Prepare Semantic Chunks' }))
    expect(screen.getByText('Preparing...')).toBeInTheDocument()
    resolvePreparation({ data: chunkResult() })
    expect(await screen.findByText('\u2713 Prepared')).toBeInTheDocument()
    expect(screen.getByText('Chunks: 1')).toBeInTheDocument()
    expect(screen.getByText('Average size: 7 tokens')).toBeInTheDocument()
    expect(screen.getByText('Chunker: v1')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Review Chunks' }))
    expect(await screen.findByRole('heading', { name: 'Chunk 1' })).toBeInTheDocument()
    expect(screen.getByText('Section: API Design')).toBeInTheDocument()
    expect(screen.getByText('Source: pages 3\u20134')).toBeInTheDocument()
    expect(screen.getByText('POST /bookings creates a booking.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Rebuild' }))
    await waitFor(() => expect(prepareImplementationDocumentChunks).toHaveBeenLastCalledWith(
      'AGP-003', metadata().upload_id, { force: true },
    ))
  })

  it.each([
    ['PARTIAL', 'Prepared with warnings'],
    ['FAILED', 'Preparation failed'],
  ])('renders %s semantic preparation truthfully', async (status, label) => {
    const user = userEvent.setup()
    prepareImplementationDocumentChunks.mockResolvedValue({ data: chunkResult({ status }) })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(user, 'DOCUMENT', new File(['doc'], 'input.txt'), metadata({ original_filename: 'input.txt' }))
    await user.click(screen.getByRole('button', { name: 'Prepare Semantic Chunks' }))
    expect(await screen.findByText(label)).toBeInTheDocument()
  })

  it('shows structured source paths as plain text and no semantic action for images', async () => {
    const user = userEvent.setup()
    const structured = chunkResult({
      document_type: 'JSON',
      chunks: [{
        ...chunkResult().chunks[0],
        text: '{"id":"uuid"}',
        context: { ...chunkResult().chunks[0].context, section_title: null, heading_path: [] },
        provenance: {
          ...chunkResult().chunks[0].provenance,
          document_type: 'JSON', page_start: null, page_end: null,
          structured_path: '$.tables.bookings',
        },
      }],
    })
    prepareImplementationDocumentChunks.mockResolvedValue({ data: structured })
    getImplementationDocumentChunks.mockResolvedValue({ data: structured })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(user, 'DOCUMENT', new File(['{}'], 'model.json'), metadata({ original_filename: 'model.json' }))
    await user.click(screen.getByRole('button', { name: 'Prepare Semantic Chunks' }))
    await user.click(await screen.findByRole('button', { name: 'Review Chunks' }))
    expect(await screen.findByText('Source path: $.tables.bookings')).toBeInTheDocument()
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('shows rule detection only after chunks and renders running and completed metrics', async () => {
    const user = userEvent.setup()
    let resolveDetection
    runImplementationRuleDetector.mockReturnValueOnce(new Promise((resolve) => { resolveDetection = resolve }))
    render(<ImplementationWorkspace project={project} />)
    await attachFile(user, 'DOCUMENT', new File(['doc'], 'input.txt'), metadata({ original_filename: 'input.txt' }))
    expect(screen.queryByRole('button', { name: 'Run Rule Detector' })).not.toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Prepare Semantic Chunks' }))
    expect((await screen.findAllByText('Not run')).length).toBe(3)
    expect(screen.getByText(/Deterministic baseline/)).toHaveTextContent('no AI model used')
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    expect(screen.getByText('Running rule detector...')).toBeInTheDocument()
    resolveDetection({ data: ruleDetectionResult() })
    expect(await screen.findByText('\u2713 Complete')).toBeInTheDocument()
    expect(screen.getByText('Chunks analyzed: 1')).toBeInTheDocument()
    expect(screen.getByText('Artifact candidates: 2')).toBeInTheDocument()
    expect(screen.getByText('Other context: 0')).toBeInTheDocument()
  })

  it('reviews multi-label rule strengths, scores, evidence, and chunk text', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    await user.click(await screen.findByRole('button', { name: 'Review Rule Predictions' }))
    expect(await screen.findByText('API Specification \u2014 Strong')).toBeInTheDocument()
    expect(screen.getByText('Acceptance Criteria \u2014 Moderate')).toBeInTheDocument()
    expect(screen.getByText('Rule strength: Strong')).toBeInTheDocument()
    expect(screen.getByText('Heuristic score: 0.96')).toBeInTheDocument()
    expect(screen.getByText('POST /bookings')).toBeInTheDocument()
    expect(screen.getByText('POST /bookings creates a booking.')).toBeInTheDocument()
    expect(screen.queryByText(/AI confidence/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/LLM/i)).not.toBeInTheDocument()
  })

  it('requires both baselines then summarizes and reviews explainable hybrid candidates', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    const hybrid = screen.getByRole('region', { name: 'Hybrid Artifact Analysis' })
    expect(within(hybrid).getByText('Required: complete Rule-Based Detection.')).toBeInTheDocument()
    expect(within(hybrid).getByText('Required: complete Zero-Shot Model Baseline.')).toBeInTheDocument()
    expect(within(hybrid).queryByRole('button', { name: 'Build Hybrid Candidates' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    await user.click(await within(hybrid).findByRole('button', { name: 'Build Hybrid Candidates' }))
    expect(await within(hybrid).findByText('Likely candidates: 1')).toBeInTheDocument()
    expect(within(hybrid).getByText('Needs review: 1')).toBeInTheDocument()
    expect(within(hybrid).getByText('Rejected weak candidates: 1')).toBeInTheDocument()
    expect(within(hybrid).getByText('Hybrid candidates are not human-verified artifacts yet.')).toBeInTheDocument()
    await user.click(within(hybrid).getByRole('button', { name: 'Review Hybrid Candidates' }))
    expect(await within(hybrid).findByText(/several competing high-scoring labels/)).toBeInTheDocument()
    expect(within(hybrid).getByText(/Top zero-shot scores are ambiguous/)).toBeInTheDocument()
    expect(within(hybrid).getByText('Evidence state: Rule And Model')).toBeInTheDocument()
    expect(within(hybrid).getByText('Reason: RULE_MODEL_AGREEMENT')).toBeInTheDocument()
    expect(within(hybrid).getByText('Decision: Review Required')).toBeInTheDocument()
    expect(within(hybrid).queryByText(/hybrid confidence/i)).not.toBeInTheDocument()
    expect(within(hybrid).queryByRole('button', { name: /accept|relabel|exclude/i })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Artifact Detection Baseline' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Zero-Shot Model Baseline' })).toBeInTheDocument()
  })

  it('supports specification-panel human accept, relabel, exclude, add-label, notes, and progress', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} activeSection="SPECIFICATION_VERIFICATION" />)
    await user.click(screen.getByText('Research Details'))
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    await user.click(await screen.findByRole('button', { name: 'Build Hybrid Candidates' }))
    const verification = await screen.findByRole('region', { name: 'Human Artifact Verification' })
    expect(within(verification).getByText('Status: Not Started')).toBeInTheDocument()
    expect(within(verification).getByText('0 verified')).toBeInTheDocument()
    expect(within(verification).getByText(/Machine suggestions are not considered ground truth/)).toBeInTheDocument()
    expect(within(verification).getByText(/All chunks are reviewed in the research workflow/)).toBeInTheDocument()
    await user.click(within(verification).getByRole('button', { name: 'Start Review' }))
    const review = await screen.findByRole('region', { name: 'Human Artifact Verification Review' })
    expect(within(review).getByText('Source: bookease-api.pdf')).toBeInTheDocument()
    expect(within(review).getByText('POST /bookings creates a booking.')).toBeInTheDocument()
    expect(within(review).getByText('Evidence: POST /bookings')).toBeInTheDocument()
    expect(within(review).getByText(/API Specification 0.9400/)).toBeInTheDocument()
    expect(within(review).getByText(/API Specification — Auto Candidate — Rule And Model/)).toBeInTheDocument()
    expect(within(review).getByText('Machine Suggested')).toBeInTheDocument()
    expect(within(review).getByText('Human Verification')).toBeInTheDocument()

    await user.type(within(review).getByLabelText('Optional review note'), 'Status behavior is also a criterion.')
    await user.click(within(review).getByRole('button', { name: 'Exclude API Specification' }))
    expect(within(review).getByText('Selected action: Exclude')).toBeInTheDocument()
    await user.selectOptions(within(review).getByLabelText('Relabel API Specification'), 'TECHNICAL_CONSTRAINTS')
    await user.click(within(review).getByRole('button', { name: 'Relabel Candidate' }))
    expect(within(review).getByText(/Selected action: Relabel → Technical Constraints/)).toBeInTheDocument()
    await user.click(within(review).getByRole('button', { name: 'Accept API Specification' }))
    await user.selectOptions(within(review).getByLabelText('Add Missing Artifact Type'), 'ACCEPTANCE_CRITERIA')
    await user.click(within(review).getByRole('button', { name: 'Add Missing Artifact Type' }))
    expect(within(review).getByText('✓ API Specification')).toBeInTheDocument()
    expect(within(review).getByText('✓ Acceptance Criteria')).toBeInTheDocument()
    await user.click(within(review).getByRole('button', { name: 'Save Chunk Verification' }))
    await waitFor(() => expect(saveImplementationHumanReview).toHaveBeenCalledWith(
      'AGP-003', metadata().upload_id, chunkResult().chunks[0].chunk_id,
      expect.objectContaining({ expected_review_fingerprint: 'd'.repeat(64) }),
    ))
    expect(await within(verification).findByText('Status: Complete')).toBeInTheDocument()
    expect(within(verification).getByText('1 verified')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Artifact Detection Baseline' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Zero-Shot Model Baseline' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Hybrid Artifact Analysis' })).toBeInTheDocument()
    expect(screen.queryByText(/dataset export|fine-tuning/i)).not.toBeInTheDocument()
  })

  it('shows stale human verification without applying prior labels', async () => {
    const user = userEvent.setup()
    getImplementationHumanReviews.mockResolvedValue({ data: humanReviewState({ stale: true }) })
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    await user.click(await screen.findByRole('button', { name: 'Build Hybrid Candidates' }))
    await user.click(await screen.findByRole('button', { name: 'Start Review' }))
    expect(await screen.findByText('Artifact analysis changed. Human verification must be performed again.')).toBeInTheDocument()
    expect(screen.getByText('No final labels selected yet.')).toBeInTheDocument()
  })

  it('prepares and reviews canonical artifacts only after complete human verification', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    await user.click(await screen.findByRole('button', { name: 'Build Hybrid Candidates' }))
    expect(screen.queryByRole('region', { name: 'Canonical Artifact Preparation' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Start Review' }))
    const human = await screen.findByRole('region', { name: 'Human Artifact Verification Review' })
    await user.click(within(human).getByRole('button', { name: 'Accept API Specification' }))
    await user.click(within(human).getByRole('button', { name: 'Save Chunk Verification' }))
    const preparation = await screen.findByRole('region', { name: 'Canonical Artifact Preparation' })
    expect(within(preparation).getByText('Not prepared')).toBeInTheDocument()
    await user.click(within(preparation).getByRole('button', { name: 'Build Canonical Artifacts' }))
    expect(await within(preparation).findByText('Artifacts: 2')).toBeInTheDocument()
    expect(within(preparation).getByText('Complete: 0')).toBeInTheDocument()
    expect(within(preparation).getByText('Partial: 1')).toBeInTheDocument()
    expect(within(preparation).getByText('Unresolved: 1')).toBeInTheDocument()
    expect(within(preparation).getByText('Built from human-verified artifact labels.')).toBeInTheDocument()
    await user.click(within(preparation).getByRole('button', { name: 'Review Canonical Artifacts' }))
    const review = await within(preparation).findByRole('region', { name: 'Canonical Artifact Review' })
    expect(within(review).getByText('API Specification')).toBeInTheDocument()
    expect(within(review).getAllByText('Status: Partial').length).toBeGreaterThan(0)
    expect(within(review).getByText('Status: Needs Semantic Extraction')).toBeInTheDocument()
    expect(within(review).getAllByText(/bookease-api\.pdf · Pages 3–4 · Chunk CHK-/)).toHaveLength(2)
    expect(within(review).getByText('NO_EXPLICIT_DATABASE_STRUCTURE')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Human Artifact Verification' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Hybrid Artifact Analysis' })).toBeInTheDocument()
    await user.click(within(preparation).getByRole('button', { name: 'Rebuild' }))
    await waitFor(() => expect(buildImplementationCanonicalArtifacts).toHaveBeenLastCalledWith(
      'AGP-003', metadata().upload_id, { force: true },
    ))
  })

  it('runs and reviews source-grounded local semantic fallback without replacing canonical results', async () => {
    const user = userEvent.setup()
    let resolveSemantic
    buildImplementationSemanticArtifacts.mockReturnValueOnce(new Promise((resolve) => { resolveSemantic = resolve }))
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    await user.click(await screen.findByRole('button', { name: 'Build Hybrid Candidates' }))
    await user.click(screen.getByRole('button', { name: 'Start Review' }))
    const human = await screen.findByRole('region', { name: 'Human Artifact Verification Review' })
    await user.click(within(human).getByRole('button', { name: 'Accept API Specification' }))
    await user.click(within(human).getByRole('button', { name: 'Save Chunk Verification' }))
    await user.click(await screen.findByRole('button', { name: 'Build Canonical Artifacts' }))

    const fallback = await screen.findByRole('region', { name: 'Semantic Fallback' })
    expect(within(fallback).getByText('Available')).toBeInTheDocument()
    expect(within(fallback).getByText('Local model: Qwen3-1.7B')).toBeInTheDocument()
    expect(within(fallback).getByText(/only for information the deterministic parser could not structure/)).toBeInTheDocument()
    await user.click(within(fallback).getByRole('button', { name: 'Run Semantic Fallback' }))
    expect(within(fallback).getByText('Semantic extraction in progress...')).toBeInTheDocument()
    expect(within(fallback).getByText('First local model load may take longer.')).toBeInTheDocument()
    resolveSemantic({ data: semanticArtifactResult() })
    expect(await within(fallback).findByText('Target artifacts: 1')).toBeInTheDocument()
    expect(within(fallback).getByText('Needs human review: 1')).toBeInTheDocument()
    expect(within(fallback).getByText('Rejected unsupported facts: 1')).toBeInTheDocument()
    expect(within(fallback).getByText(/have not replaced the deterministic baseline/)).toBeInTheDocument()

    await user.click(within(fallback).getByRole('button', { name: 'Review Semantic Results' }))
    const review = await within(fallback).findByRole('region', { name: 'Semantic Result Review' })
    expect(within(review).getByText('Origin: SEMANTIC')).toBeInTheDocument()
    expect(within(review).getByText('Evidence: “Create a booking using name.”')).toBeInTheDocument()
    expect(within(review).getByText('✓ Source evidence verified')).toBeInTheDocument()
    expect(within(review).getByText('✕ Unsupported by source')).toBeInTheDocument()
    expect(within(review).getByText('Reason: UNSUPPORTED_BY_SOURCE')).toBeInTheDocument()
    expect(within(review).getByText('Semantic / Deterministic Conflict')).toBeInTheDocument()
    expect(within(review).getByText('Deterministic: "POST"')).toBeInTheDocument()
    expect(within(review).getByText('Semantic: "PUT"')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Canonical Artifact Preparation' })).toBeInTheDocument()
    expect(screen.queryByText(/readiness.*semantic/i)).not.toBeInTheDocument()
    await user.click(within(fallback).getByRole('button', { name: 'Re-run Semantic Fallback' }))
    await waitFor(() => expect(buildImplementationSemanticArtifacts).toHaveBeenLastCalledWith(
      'AGP-003', metadata().upload_id, { force: true },
    ))
  })

  it('renders OTHER_CONTEXT and re-runs with force=true', async () => {
    const user = userEvent.setup()
    const other = ruleDetectionResult({
      metrics: {
        ...ruleDetectionResult().metrics,
        classified_chunk_count: 0, other_context_chunk_count: 1, prediction_count: 0,
        strong_prediction_count: 0, moderate_prediction_count: 0, weak_prediction_count: 0,
      },
      detections: [{
        chunk_id: chunkResult().chunks[0].chunk_id,
        text_hash: chunkResult().chunks[0].text_hash,
        unclassified: true,
        predictions: [{
          label: 'OTHER_CONTEXT', rule_score: 0, strength: 'WEAK',
          evidence: [{ rule_id: 'NO_ARTIFACT_RULE_MATCH', matched_text: 'No artifact rule met the emission threshold.', source: 'TEXT' }],
        }],
      }],
    })
    runImplementationRuleDetector.mockResolvedValue({ data: other })
    getImplementationRuleDetections.mockResolvedValue({ data: other })
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Rule Detector' }))
    await user.click(await screen.findByRole('button', { name: 'Review Rule Predictions' }))
    expect(await screen.findByText('Other Context \u2014 Weak')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Re-run' }))
    await waitFor(() => expect(runImplementationRuleDetector).toHaveBeenLastCalledWith(
      'AGP-003', metadata().upload_id, { force: true },
    ))
  })

  it('shows zero-shot action only after chunks, running state, metrics, and baseline wording', async () => {
    const user = userEvent.setup()
    let resolveModel
    runImplementationZeroShotClassifier.mockReturnValueOnce(new Promise((resolve) => { resolveModel = resolve }))
    render(<ImplementationWorkspace project={project} />)
    await attachFile(user, 'DOCUMENT', new File(['doc'], 'input.txt'), metadata({ original_filename: 'input.txt' }))
    expect(screen.queryByRole('button', { name: 'Run Zero-Shot Classifier' })).not.toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Prepare Semantic Chunks' }))
    expect(await screen.findByText('Zero-Shot Model Baseline')).toBeInTheDocument()
    expect(screen.getByText(/not fine-tuned on AgileFlow data/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    expect(screen.getByText('Loading/classifying...')).toBeInTheDocument()
    expect(screen.getByText(/first run may take longer/i)).toBeInTheDocument()
    resolveModel({ data: zeroShotResult() })
    expect(await screen.findByText('Zero-Shot DeBERTa')).toBeInTheDocument()
    expect(screen.getByText('Chunks classified: 1')).toBeInTheDocument()
    expect(screen.getByText('Truncated chunks: 0')).toBeInTheDocument()
    expect(screen.getByText('Model: DeBERTa-v3-base-mnli-fever-anli')).toBeInTheDocument()
  })

  it('reviews all raw zero-shot scores, provenance, model tokens, and force re-runs', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    await user.click(await screen.findByRole('button', { name: 'Review Model Predictions' }))
    expect(await screen.findByRole('heading', { name: 'Zero-Shot Predictions' })).toBeInTheDocument()
    expect(screen.getByText(/not calibrated domain confidence/i)).toBeInTheDocument()
    expect(screen.getAllByText('API Specification: 0.9400')).toHaveLength(2)
    expect(screen.getAllByText('Acceptance Criteria: 0.7300')).toHaveLength(2)
    expect(screen.getByText('Other Context: 0.1000')).toBeInTheDocument()
    expect(screen.getByText('Model tokens: 42 / 512')).toBeInTheDocument()
    expect(screen.getByText('Source: pages 3–4')).toBeInTheDocument()
    expect(screen.queryByText(/AI confidence/i)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Re-run Model' }))
    await waitFor(() => expect(runImplementationZeroShotClassifier).toHaveBeenLastCalledWith(
      'AGP-003', metadata().upload_id, { force: true },
    ))
  })

  it.each([
    ['PARTIAL', 'Partial'],
    ['FAILED', 'Model classification failed'],
  ])('renders %s zero-shot status truthfully', async (status, label) => {
    const user = userEvent.setup()
    runImplementationZeroShotClassifier.mockResolvedValue({ data: zeroShotResult({ status }) })
    render(<ImplementationWorkspace project={project} />)
    await attachAndPrepareDocument(user)
    await user.click(screen.getByRole('button', { name: 'Run Zero-Shot Classifier' }))
    expect(await screen.findByText(label)).toBeInTheDocument()
  })

  it('explicitly evaluates and renders READY_WITH_WARNINGS with grouped findings and frozen stack', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await reachWorkspaceReview(user)
    expect(screen.getByRole('button', { name: 'Check Implementation Readiness' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    expect(await screen.findByText('READY WITH WARNINGS')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Warnings' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Information' })).toBeInTheDocument()
    ;['React + Vite', 'Plain CSS', 'Node.js + Express.js', 'MySQL', 'JavaScript', 'REST'].forEach((value) => {
      expect(screen.getByText(value)).toBeInTheDocument()
    })
    expect(screen.getByText('BACKEND_CODE: Ready')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start Agent|Run Agent/i })).not.toBeInTheDocument()
    expect(evaluateImplementationReadiness).toHaveBeenCalledWith(
      'AGP-003',
      expect.objectContaining({
        selected_outputs: ['BACKEND_CODE'],
        document_upload_ids: [], image_upload_ids: [], human_resolutions: [],
      }),
    )
  })

  it('shows evaluating, READY, and NOT_READY states truthfully', async () => {
    const user = userEvent.setup()
    let resolveEvaluation
    evaluateImplementationReadiness.mockReturnValueOnce(new Promise((resolve) => { resolveEvaluation = resolve }))
    render(<ImplementationWorkspace project={project} />)
    await reachWorkspaceReview(user)
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    expect(screen.getByRole('button', { name: 'Evaluating implementation readiness' })).toBeDisabled()
    resolveEvaluation({ data: readinessResult({
      status: 'READY', summary: { errors: 0, warnings: 0, info: 1 }, findings: [],
    }) })
    expect(await screen.findByText('READY')).toBeInTheDocument()
  })

  it('renders blocking findings and returns to inputs without starting execution', async () => {
    const user = userEvent.setup()
    evaluateImplementationReadiness.mockResolvedValue({ data: readinessResult({
      status: 'NOT_READY', summary: { errors: 1, warnings: 0, info: 0 },
      output_readiness: [{ output: 'BACKEND_CODE', ready: false, findings: ['RF-3333333333333333'] }],
      findings: [{
        finding_id: 'RF-3333333333333333', code: 'API_SPECIFICATION_REQUIRED', severity: 'ERROR',
        title: 'API specification is required', message: 'No API specification was supplied.',
        affected_outputs: ['BACKEND_CODE'], sources: [], requires_human_decision: false,
        allowed_resolutions: [], category: null, provided_value: null, supported_value: null,
        resolved: false, resolution: null,
      }],
    }) })
    render(<ImplementationWorkspace project={project} />)
    await reachWorkspaceReview(user)
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    expect(await screen.findByText('NOT READY')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Blocking Issues' })).toBeInTheDocument()
    expect(screen.getByText('API_SPECIFICATION_REQUIRED')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to Inputs' }))
    expect(screen.getByRole('heading', { name: 'Implementation Inputs' })).toBeInTheDocument()
  })

  it('re-evaluates an explicit prototype-stack adaptation and records human approval', async () => {
    const user = userEvent.setup()
    const conflict = {
      finding_id: 'RF-4444444444444444', code: 'UNSUPPORTED_PROTOTYPE_TECHNOLOGY', severity: 'ERROR',
      title: 'Unsupported Backend Technology', message: 'FastAPI is outside the PP1 stack.',
      affected_outputs: ['BACKEND_CODE'], sources: [], requires_human_decision: true,
      allowed_resolutions: ['ADAPT_TO_SUPPORTED_STACK'], category: 'backend',
      provided_value: 'FastAPI', supported_value: 'Node.js + Express.js', resolved: false, resolution: null,
    }
    evaluateImplementationReadiness
      .mockResolvedValueOnce({ data: readinessResult({
        status: 'NOT_READY', summary: { errors: 1, warnings: 0, info: 0 }, findings: [conflict],
      }) })
      .mockResolvedValueOnce({ data: readinessResult({
        findings: [{ ...conflict, resolved: true, resolution: {
          finding_id: conflict.finding_id, decision: 'ADAPT_TO_SUPPORTED_STACK',
          note: 'Approved for the AgileFlow PP1 prototype.',
        } }],
      }) })
    render(<ImplementationWorkspace project={project} />)
    await reachWorkspaceReview(user)
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    expect(await screen.findByText('Provided: FastAPI')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Adapt to AgileFlow PP1 Stack' }))
    await waitFor(() => expect(evaluateImplementationReadiness).toHaveBeenCalledTimes(2))
    expect(evaluateImplementationReadiness.mock.calls[1][1]).toEqual(expect.objectContaining({
      input_fingerprint: 'b'.repeat(64),
      human_resolutions: [expect.objectContaining({
        finding_id: conflict.finding_id, decision: 'ADAPT_TO_SUPPORTED_STACK',
      })],
    }))
    expect(await screen.findByText(/Human decision recorded/)).toBeInTheDocument()
  })

  it('marks readiness stale after text or output changes', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await reachWorkspaceReview(user)
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    await screen.findByText('READY WITH WARNINGS')
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await user.type(screen.getByLabelText(/Content/), ' Changed')
    expect(screen.getByRole('alert')).toHaveTextContent('Inputs changed')
  })

  it('marks readiness stale after selected outputs change', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await reachWorkspaceReview(user)
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    await screen.findByText('READY WITH WARNINGS')
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await user.click(screen.getByRole('checkbox', { name: 'Frontend Code' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Inputs changed')
  })

  it('marks readiness stale when an uploaded document is removed', async () => {
    const user = userEvent.setup()
    deleteImplementationInputFile.mockResolvedValue({ data: { upload_id: metadata().upload_id } })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user, 'DOCUMENT',
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    await screen.findByText('Complete')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Backend Code' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    await screen.findByText('READY WITH WARNINGS')
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await user.click(screen.getByRole('button', { name: 'Remove Input' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Inputs changed')
  })

  it('shows readiness API failures without claiming a readiness status', async () => {
    const user = userEvent.setup()
    evaluateImplementationReadiness.mockRejectedValue({
      errors: [{ message: 'Readiness dependencies are unavailable' }],
    })
    render(<ImplementationWorkspace project={project} />)
    await reachWorkspaceReview(user)
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('dependencies are unavailable')
    expect(screen.queryByText('READY WITH WARNINGS')).not.toBeInTheDocument()
  })

  it('reports image context as pending without claiming image understanding', async () => {
    const user = userEvent.setup()
    evaluateImplementationReadiness.mockResolvedValue({ data: readinessResult({
      coverage: {
        requirements: true, design: false, implementation: false,
        tests: false, visual_context_pending: true,
      },
      findings: [{
        finding_id: 'RF-5555555555555555', code: 'VISUAL_CONTEXT_PENDING', severity: 'INFO',
        title: 'Visual context is pending',
        message: 'Visual input is attached but has not yet been interpreted.',
        affected_outputs: ['FRONTEND_CODE'], sources: [], requires_human_decision: false,
        allowed_resolutions: [], category: null, provided_value: null, supported_value: null,
        resolved: false, resolution: null,
      }],
    }) })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user, 'IMAGE',
      new File(['png'], 'wireframe.png', { type: 'image/png' }),
      metadata({
        source_type: 'IMAGE', artifact_type: 'UI_WIREFRAMES', original_filename: 'wireframe.png',
        mime_type: 'image/png', extension: '.png', size_bytes: 1024,
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Frontend Code' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    expect(await screen.findByText('Pending image analysis')).toBeInTheDocument()
    expect(screen.getByText('Visual input is attached but has not yet been interpreted.')).toBeInTheDocument()
  })

  it('preserves TEXT input, exact outputs, review, and no execution behavior', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await user.type(screen.getByLabelText(/Content/), '  Build a booking API.  ')
    await user.click(screen.getByRole('button', { name: 'Next' }))

    outputLabels.forEach((label) => {
      expect(screen.getByRole('checkbox', { name: label })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('checkbox', { name: 'Backend Code' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    expect(screen.getByText('BookEase Builder')).toBeInTheDocument()
    expect(screen.getByText('Hospitality')).toBeInTheDocument()
    expect(screen.getByText('Build a booking API.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Workspace Ready' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
    expect(uploadImplementationInputFile).not.toHaveBeenCalled()
  })

  it('enables DOCUMENT and IMAGE with their controlled accept lists', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    const source = screen.getByLabelText(/Input Source/)
    expect(within(source).getByRole('option', { name: 'Document' })).toBeEnabled()
    expect(within(source).getByRole('option', { name: 'Image' })).toBeEnabled()

    await chooseSource(user, 'DOCUMENT')
    expect(screen.getByLabelText(/Document file/)).toHaveAttribute(
      'accept', '.pdf,.docx,.txt,.md,.json,.yaml,.yml',
    )
    await chooseSource(user, 'IMAGE')
    expect(screen.getByLabelText(/Image file/)).toHaveAttribute(
      'accept', '.png,.jpg,.jpeg,.webp',
    )
  })

  it.each([
    {
      sourceType: 'DOCUMENT',
      artifact: 'API_SPECIFICATION',
      file: new File(['%PDF-test'], 'bookease-api.pdf', { type: 'application/pdf' }),
      result: metadata(),
    },
    {
      sourceType: 'IMAGE',
      artifact: 'UI_WIREFRAMES',
      file: new File(['png'], 'booking.png', { type: 'image/png' }),
      result: metadata({
        source_type: 'IMAGE', artifact_type: 'UI_WIREFRAMES',
        original_filename: 'booking.png', mime_type: 'image/png',
        extension: '.png', size_bytes: 2048,
      }),
    },
  ])('uploads and reviews real $sourceType metadata', async ({ sourceType, artifact, file, result }) => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await user.selectOptions(screen.getByLabelText(/Artifact Type/), artifact)
    await user.type(screen.getByLabelText('Label (optional)'), 'Booking API')
    await attachFile(user, sourceType, file, result)

    expect(uploadImplementationInputFile).toHaveBeenCalledWith('AGP-003', {
      source_type: sourceType,
      artifact_type: artifact,
      label: 'Booking API',
      file,
    })
    expect(screen.getByText(result.original_filename)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(result.mime_type))).toBeInTheDocument()
    expect(screen.getByLabelText(/Input Source/)).toBeDisabled()
    expect(screen.getByText(/Remove this uploaded input before changing/i)).toBeInTheDocument()

    if (sourceType === 'DOCUMENT') await screen.findByText('Complete')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Project Structure' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    expect(screen.getByText(new RegExp(`Uploaded / Attached — ${result.original_filename}`))).toBeInTheDocument()
    expect(screen.queryByText(/Analyzed|Processed by AI|Understood/)).not.toBeInTheDocument()
  })

  it('shows upload loading and backend validation failures honestly', async () => {
    const user = userEvent.setup()
    let rejectUpload
    uploadImplementationInputFile.mockReturnValue(new Promise((_, reject) => { rejectUpload = reject }))
    render(<ImplementationWorkspace project={project} />)
    await chooseSource(user, 'DOCUMENT')
    await user.upload(
      screen.getByLabelText(/Document file/),
      new File(['large'], 'large.pdf', { type: 'application/pdf' }),
    )
    await user.click(screen.getByRole('button', { name: 'Attach File' }))
    expect(screen.getByRole('button', { name: 'Uploading file' })).toBeDisabled()
    rejectUpload({ errors: [{ message: 'DOCUMENT files must not exceed 10 MB' }] })
    expect(await screen.findByRole('alert')).toHaveTextContent('must not exceed 10 MB')
    expect(screen.queryByText('Uploaded / Attached')).not.toBeInTheDocument()
  })

  it('automatically extracts a document and shows the extracting state', async () => {
    const user = userEvent.setup()
    let resolveExtraction
    extractImplementationDocument.mockReturnValue(new Promise((resolve) => { resolveExtraction = resolve }))
    uploadImplementationInputFile.mockResolvedValue({ data: metadata() })
    render(<ImplementationWorkspace project={project} />)
    await chooseSource(user, 'DOCUMENT')
    await user.upload(
      screen.getByLabelText(/Document file/),
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
    )
    await user.click(screen.getByRole('button', { name: 'Attach File' }))
    expect(await screen.findByText('Extracting...')).toBeInTheDocument()
    expect(extractImplementationDocument).toHaveBeenCalledWith(
      'AGP-003', metadata().upload_id, { force: false },
    )
    resolveExtraction({ data: extractionResult() })
    expect(await screen.findByText('Complete')).toBeInTheDocument()
  })

  it.each([
    ['PARTIAL', 'Partial', 'Some pages did not contain text.'],
    ['FAILED', 'Failed', 'No reliable textual content could be extracted from this document.'],
  ])('shows %s extraction with warnings and offers retry', async (status, label, warning) => {
    const user = userEvent.setup()
    extractImplementationDocument.mockResolvedValueOnce({
      data: extractionResult({
        status,
        warnings: [{ code: 'NO_EXTRACTABLE_TEXT', message: warning, location: null }],
      }),
    }).mockResolvedValueOnce({ data: extractionResult() })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByText('Warnings: 1')).toBeInTheDocument()
    expect(screen.getByText(warning)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry Extraction' }))
    await waitFor(() => expect(extractImplementationDocument).toHaveBeenLastCalledWith(
      'AGP-003', metadata().upload_id, { force: true },
    ))
  })

  it('reports extraction API failure honestly and allows retry', async () => {
    const user = userEvent.setup()
    extractImplementationDocument.mockRejectedValueOnce({
      errors: [{ message: 'Document extraction is temporarily unavailable' }],
    }).mockResolvedValueOnce({ data: extractionResult() })
    render(<ImplementationWorkspace project={project} />)
    uploadImplementationInputFile.mockResolvedValue({ data: metadata() })
    await chooseSource(user, 'DOCUMENT')
    await user.upload(
      screen.getByLabelText(/Document file/),
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
    )
    await user.click(screen.getByRole('button', { name: 'Attach File' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('temporarily unavailable')
    expect(screen.getByText('Extraction request failed')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry Extraction' }))
    expect(await screen.findByText('Complete')).toBeInTheDocument()
  })

  it.each([
    ['PDF', { pages: [{ page_number: 2, text: 'Page two API details' }], combined_text: 'Page two API details' }, 'Page 2', 'Page two API details'],
    ['DOCX', { blocks: [
      { block_index: 0, type: 'HEADING', level: 1, text: 'API Specification', rows: null },
      { block_index: 1, type: 'PARAGRAPH', level: null, text: 'Create booking', rows: null },
      { block_index: 2, type: 'TABLE', level: null, text: null, rows: [['Method', 'Path'], ['POST', '/bookings']] },
    ], combined_text: 'API Specification\nCreate booking' }, 'API Specification', '/bookings'],
    ['TXT', { text: 'Plain requirements', combined_text: 'Plain requirements' }, 'Plain requirements', null],
    ['MD', { markdown: '# Requirements\n- Booking', combined_text: '# Requirements\n- Booking' }, '# Requirements', null],
    ['JSON', { structured_content: { api: 'bookings' }, normalized_text: '{\n  "api": "bookings"\n}' }, '"api": "bookings"', null],
    ['YAML', { structured_content: { api: 'bookings' }, normalized_text: '{\n  "api": "bookings"\n}' }, '"api": "bookings"', null],
  ])('reviews safe structured %s extraction content', async (documentType, content, expected, secondary) => {
    const user = userEvent.setup()
    const result = extractionResult({ document_type: documentType, content })
    extractImplementationDocument.mockResolvedValue({ data: result })
    getImplementationDocumentExtraction.mockResolvedValue({ data: result })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['document'], `input.${documentType.toLowerCase()}`, { type: 'application/octet-stream' }),
      metadata({ original_filename: `input.${documentType.toLowerCase()}` }),
    )
    await user.click(screen.getByRole('button', { name: 'Review Extracted Content' }))
    expect(await screen.findByRole('heading', { name: 'Extracted Document Content' })).toBeInTheDocument()
    const review = within(screen.getByLabelText('Extracted Document Content'))
    expect(review.getByText(/implementation readiness has not yet been validated/i)).toBeInTheDocument()
    expect(review.getByText(expected, { exact: false })).toBeInTheDocument()
    if (secondary) expect(review.getByText(secondary, { exact: false })).toBeInTheDocument()
  })

  it('keeps IMAGE upload-only and never starts document extraction', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'IMAGE',
      new File(['png'], 'wireframe.png', { type: 'image/png' }),
      metadata({
        source_type: 'IMAGE', artifact_type: 'UI_WIREFRAMES', original_filename: 'wireframe.png',
        mime_type: 'image/png', extension: '.png', size_bytes: 1024,
      }),
    )
    expect(extractImplementationDocument).not.toHaveBeenCalled()
    expect(screen.queryByText('Extraction')).not.toBeInTheDocument()
  })

  it('deletes an uploaded file before removing it locally', async () => {
    const user = userEvent.setup()
    deleteImplementationInputFile.mockResolvedValue({ data: { upload_id: metadata().upload_id } })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    await user.click(screen.getByRole('button', { name: 'Remove Input' }))
    expect(deleteImplementationInputFile).toHaveBeenCalledWith('AGP-003', metadata().upload_id)
    expect(screen.queryByText('bookease-api.pdf')).not.toBeInTheDocument()
  })

  it('retains an uploaded input and reports an error when deletion fails', async () => {
    const user = userEvent.setup()
    deleteImplementationInputFile.mockRejectedValue({
      errors: [{ message: 'Staged upload could not be deleted' }],
    })
    render(<ImplementationWorkspace project={project} />)
    await attachFile(
      user,
      'DOCUMENT',
      new File(['%PDF'], 'bookease-api.pdf', { type: 'application/pdf' }),
      metadata(),
    )
    await user.click(screen.getByRole('button', { name: 'Remove Input' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be deleted')
    expect(screen.getByText('bookease-api.pdf')).toBeInTheDocument()
    expect(screen.getByLabelText(/Input Source/)).toBeDisabled()
  })

  it('validates incomplete inputs and offers real GitHub connection', async () => {
    const user = userEvent.setup()
    render(<ImplementationWorkspace project={project} />)
    await chooseSource(user, 'IMAGE')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('alert')).toHaveTextContent('attach a file')
    expect(await screen.findByRole('button', { name: 'Connect GitHub' })).toBeEnabled()
  })

  it('starts GitHub connection through the backend and redirects to its URL', async () => {
    const user = userEvent.setup()
    connectGitHub.mockResolvedValue({
      data: { installation_url: 'https://github.com/apps/agileflow/installations/new?state=safe' },
    })
    render(<ImplementationWorkspace project={project} />)
    await user.click(await screen.findByRole('button', { name: 'Connect GitHub' }))
    expect(connectGitHub).toHaveBeenCalledWith('AGP-003')
    expect(navigateToGitHub).toHaveBeenCalledWith(
      'https://github.com/apps/agileflow/installations/new?state=safe',
    )
  })

  it('shows a verified personal connection with new-repository setup only', async () => {
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('@octocat')).toBeInTheDocument()
    expect(screen.getByText('Personal')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Repository Setup' })).toBeInTheDocument()
    expect(screen.queryByText(/existing repositor/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Repository' })).toBeEnabled()
  })

  it('trusts backend status, not the connected callback query alone', async () => {
    window.history.replaceState({}, '', '/agent-projects/AGP-003?github=connected')
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('no verified connection')
    expect(screen.queryByText('GitHub account connected successfully.')).not.toBeInTheDocument()
  })

  it('shows callback success only with verified status and handles callback errors', async () => {
    getGitHubConnection.mockResolvedValue({ data: { ...connectedGitHub(), avatar_url: null } })
    window.history.replaceState({}, '', '/agent-projects/AGP-003?github=connected')
    const view = render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('status')).toHaveTextContent('connected successfully')
    view.unmount()

    getGitHubConnection.mockResolvedValue({ data: { connected: false } })
    window.history.replaceState({}, '', '/agent-projects/AGP-003?github=error&reason=authorization_failed')
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('was not completed')
  })

  it('validates repository names before calling the backend', async () => {
    const user = userEvent.setup()
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Repository Setup' })
    await user.type(screen.getByLabelText(/Repository Name/), 'owner/repo')
    await user.click(screen.getByRole('button', { name: 'Create Repository' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/repository name/i)
    expect(createGitHubRepository).not.toHaveBeenCalled()
  })

  it('creates a private or public repository once and disables while pending', async () => {
    const user = userEvent.setup()
    let resolveCreate
    createGitHubRepository.mockReturnValue(new Promise((resolve) => { resolveCreate = resolve }))
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Repository Setup' })
    await user.type(screen.getByLabelText(/Repository Name/), 'quickbook')
    await user.type(screen.getByLabelText('Description'), 'Booking system')
    await user.selectOptions(screen.getByLabelText(/Visibility/), 'PUBLIC')
    await user.click(screen.getByRole('button', { name: 'Create Repository' }))
    expect(screen.getByRole('button', { name: 'Creating repository' })).toBeDisabled()
    expect(createGitHubRepository).toHaveBeenCalledWith('AGP-003', {
      name: 'quickbook', description: 'Booking system', visibility: 'PUBLIC',
    })
    resolveCreate({ data: repositoryMetadata({ visibility: 'PUBLIC', private: false }) })
    expect(await screen.findByText('octocat/quickbook')).toBeInTheDocument()
  })

  it('shows persisted empty repository metadata and no duplicate or Git controls', async () => {
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    getGitHubRepository.mockResolvedValue({ data: repositoryMetadata() })
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByText('octocat/quickbook')).toBeInTheDocument()
    expect(screen.getByText('Empty')).toBeInTheDocument()
    expect(screen.getByText('Not created yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open on GitHub' })).toHaveAttribute(
      'href', 'https://github.com/octocat/quickbook',
    )
    expect(screen.queryByRole('button', { name: 'Create Repository' })).not.toBeInTheDocument()
    expect(screen.queryByText(/existing repository|create branch|clone|commit|pull request/i)).not.toBeInTheDocument()
  })

  it('reports repository API failure without claiming creation', async () => {
    const user = userEvent.setup()
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    createGitHubRepository.mockRejectedValue({
      errors: [{ message: 'A repository with this name already exists' }],
    })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByRole('heading', { name: 'Repository Setup' })
    await user.type(screen.getByLabelText(/Repository Name/), 'quickbook')
    await user.click(screen.getByRole('button', { name: 'Create Repository' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
    expect(screen.queryByText('octocat/quickbook')).not.toBeInTheDocument()
  })

  it('includes the persisted empty repository in workspace review', async () => {
    const user = userEvent.setup()
    getGitHubConnection.mockResolvedValue({ data: connectedGitHub() })
    getGitHubRepository.mockResolvedValue({ data: repositoryMetadata() })
    render(<ImplementationWorkspace project={project} />)
    await screen.findByText('octocat/quickbook')
    await user.type(screen.getByLabelText(/Content/), 'Build booking.')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('checkbox', { name: 'Backend Code' }))
    await user.click(screen.getByRole('button', { name: 'Review Workspace' }))
    expect(screen.getAllByText(/Repository: octocat\/quickbook/).length).toBeGreaterThan(0)
    expect(screen.getByText('Repository state: Empty')).toBeInTheDocument()
    expect(screen.queryByText(/code pushed|branch created|build successful/i)).not.toBeInTheDocument()
  })

  it('reports backend connection status failures without claiming connection', async () => {
    getGitHubConnection.mockRejectedValue({
      errors: [{ message: 'GitHub connection storage is unavailable' }],
    })
    render(<ImplementationWorkspace project={project} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('storage is unavailable')
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Connect GitHub' })).toBeEnabled()
  })

  it('reuses the existing GitHub UI for the delivery setup canvas panel', async () => {
    render(<ImplementationWorkspace project={project} activeSection="DELIVERY_SETUP" />)
    expect(await screen.findByRole('button', { name: 'Connect GitHub' })).toBeEnabled()
    expect(screen.queryByRole('heading', { name: 'Implementation Inputs' })).not.toBeInTheDocument()
  })

  it('keeps research controls reachable in the analysis panel', async () => {
    render(<ImplementationWorkspace project={project} activeSection="INPUT_ANALYSIS" />)
    expect(await screen.findByText('Research Details')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Implementation Inputs' })).toBeInTheDocument()
  })

  it('shows an honest empty readiness panel until the existing evaluation has run', async () => {
    render(<ImplementationWorkspace project={project} activeSection="IMPLEMENTATION_READINESS" />)
    expect(await screen.findByText(/No readiness evaluation exists yet/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Implementation Inputs' })).not.toBeInTheDocument()
  })
})
