import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  connectGitHub,
  createGitHubRepository,
  deleteImplementationInputFile,
  evaluateImplementationReadiness,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentChunks,
  getImplementationDocumentExtraction,
  getImplementationRuleDetections,
  getGitHubRepository,
  prepareImplementationDocumentChunks,
  runImplementationRuleDetector,
  uploadImplementationInputFile,
} from './implementationAgentService.js'
import { navigateToGitHub } from './githubNavigation.js'
import ImplementationWorkspace from './ImplementationWorkspace.jsx'

vi.mock('./implementationAgentService.js', () => ({
  uploadImplementationInputFile: vi.fn(),
  deleteImplementationInputFile: vi.fn(),
  evaluateImplementationReadiness: vi.fn(),
  extractImplementationDocument: vi.fn(),
  getImplementationDocumentExtraction: vi.fn(),
  getImplementationDocumentChunks: vi.fn(),
  prepareImplementationDocumentChunks: vi.fn(),
  getImplementationRuleDetections: vi.fn(),
  runImplementationRuleDetector: vi.fn(),
  connectGitHub: vi.fn(),
  createGitHubRepository: vi.fn(),
  getGitHubConnection: vi.fn(),
  getGitHubRepository: vi.fn(),
}))
vi.mock('./githubNavigation.js', () => ({ navigateToGitHub: vi.fn() }))

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
    expect(await screen.findByText('Not run')).toBeInTheDocument()
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
    expect(screen.queryByText(/DeBERTa|LLM/i)).not.toBeInTheDocument()
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
})
