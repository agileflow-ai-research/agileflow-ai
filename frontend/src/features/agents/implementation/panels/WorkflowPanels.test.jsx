import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import DeliverySetupPanel from './DeliverySetupPanel.jsx'
import ImplementationReadinessPanel from './ImplementationReadinessPanel.jsx'
import InputAnalysisPanel from './InputAnalysisPanel.jsx'
import ProjectSourcesPanel from './ProjectSourcesPanel.jsx'
import SpecificationVerificationPanel from './SpecificationVerificationPanel.jsx'

function input(overrides = {}) {
  return {
    input_id: 'IN-1', source_type: 'TEXT', artifact_type: 'FUNCTIONAL_REQUIREMENTS',
    label: 'Technical Notes', content: 'Prevent duplicate booking.', file: null,
    status: 'idle', error: '', ...overrides,
  }
}

function inputStepProps(overrides = {}) {
  const actionNames = [
    'buildCanonicalArtifacts', 'buildSemanticArtifacts', 'changeSource', 'prepareChunks',
    'removeInput', 'reviewCanonicalArtifacts', 'reviewChunks', 'reviewDocumentExtraction',
    'openHumanReviews', 'reviewHybridDetections', 'reviewRuleDetections',
    'reviewSemanticArtifacts', 'reviewZeroShotDetections', 'runDocumentExtraction',
    'buildHybridDetections', 'runRuleDetector', 'runZeroShotClassifier', 'saveHumanReview',
    'updateInput', 'uploadFile',
  ]
  return {
    actions: Object.fromEntries(actionNames.map((name) => [name, vi.fn()])),
    error: '',
    onAddInput: vi.fn(),
    reviews: Object.fromEntries([
      'canonicalReview', 'chunkReview', 'detectionReview', 'extractionReview',
      'humanReviewWorkspace', 'hybridReview', 'semanticReview', 'zeroShotReview',
    ].map((name) => [name, { uploadId: null, status: 'idle', result: null, error: '' }])),
    workspaceBusy: false,
    ...overrides,
  }
}

describe('Agent 3 workflow panels', () => {
  it('presents project outputs and sources with existing input actions but no model internals', async () => {
    const user = userEvent.setup()
    const props = inputStepProps()
    const inputs = [
      input(),
      input({
        input_id: 'IN-2', source_type: 'DOCUMENT', artifact_type: 'API_SPECIFICATION',
        label: '', content: '', file: {
          upload_id: 'UP-2', original_filename: 'api-spec.docx', mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', size_bytes: 1200,
        },
      }),
    ]
    render(
      <ProjectSourcesPanel
        project={{ name: 'Booking Platform', domain: 'Hospitality', description: 'Implementation project' }}
        inputs={inputs}
        selectedOutputs={['FRONTEND_CODE', 'BACKEND_CODE']}
        onOutputsChange={vi.fn()}
        outputError=""
        inputStepProps={props}
      />,
    )

    expect(screen.getByRole('checkbox', { name: 'Frontend Code' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Backend Code' })).toBeChecked()
    expect(screen.getByText('Sources — 2')).toBeInTheDocument()
    expect(screen.getAllByText('Technical Notes').length).toBeGreaterThan(0)
    expect(screen.getAllByText('api-spec.docx').length).toBeGreaterThan(0)
    expect(screen.queryByText(/Zero-Shot DeBERTa|Hybrid Artifact Analysis|Semantic Fallback/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add Input' }))
    expect(props.onAddInput).toHaveBeenCalledOnce()
    await user.click(screen.getAllByRole('button', { name: 'Remove Input' })[0])
    expect(props.actions.removeInput).toHaveBeenCalledWith(0)
  })

  it('shows source-oriented analysis and keeps technical controls in collapsed research details', () => {
    render(
      <InputAnalysisPanel
        inputs={[
          input({ chunks: { status: 'SUCCESS' } }),
          input({ input_id: 'IN-2', label: 'Pending notes', chunks: null }),
          input({ input_id: 'IN-3', label: 'Broken source', error: 'Failed to load' }),
        ]}
        researchContent={<button type="button">Run Zero-Shot Classifier</button>}
      />,
    )

    const overview = screen.getByRole('heading', { name: 'Source analysis overview' }).closest('section')
    expect(within(overview).getByText('Sources').nextSibling).toHaveTextContent('3')
    expect(within(overview).getByText('Prepared').nextSibling).toHaveTextContent('1')
    expect(within(overview).getByText('Needs Attention').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Pending notes').closest('div').parentElement).toHaveTextContent('Available')
    const disclosure = screen.getByText('Research Details').closest('details')
    expect(disclosure).not.toHaveAttribute('open')
    expect(within(disclosure).getByRole('button', { name: 'Run Zero-Shot Classifier' })).toBeInTheDocument()
    expect(screen.queryByText(/75%|100%/)).not.toBeInTheDocument()
  })

  it('shows authoritative multi-source preparation state and safe failures', async () => {
    const user = userEvent.setup()
    const onAnalyze = vi.fn()
    render(
      <InputAnalysisPanel
        inputs={[]}
        preparationState={{
          status: 'loaded', error: '',
          result: {
            status: 'PARTIAL_FAILURE', source_count: 3,
            completed_source_count: 2, failed_source_count: 1,
            sources: [
              { source_id: 'UP-1', filename: 'requirements.pdf', source_kind: 'DOCUMENT', status: 'READY', current_stage: 'HUMAN_REVIEW' },
              { source_id: 'UP-2', filename: 'api-spec.docx', source_kind: 'DOCUMENT', status: 'WAITING_FOR_HUMAN', current_stage: 'HUMAN_REVIEW' },
              { source_id: 'UP-3', filename: 'broken.yaml', source_kind: 'DOCUMENT', status: 'FAILED', current_stage: 'EXTRACTION', error: { message: 'The document could not be extracted.' } },
            ],
          },
        }}
        onAnalyze={onAnalyze}
        researchContent={<button type="button">Run Hybrid Analysis</button>}
      />,
    )

    expect(screen.getAllByText('Needs Attention')).toHaveLength(2)
    expect(screen.getByText('requirements.pdf').closest('div').parentElement).toHaveTextContent('Prepared')
    expect(screen.getByText('api-spec.docx').closest('div').parentElement).toHaveTextContent('Waiting for Review')
    expect(screen.getByText('broken.yaml').closest('div').parentElement).toHaveTextContent('The document could not be extracted.')
    await user.click(screen.getByRole('button', { name: 'Analyze Project Inputs' }))
    expect(onAnalyze).toHaveBeenCalledOnce()
  })

  it('groups loaded specification layers by artifact and preserves source identity and advanced access', () => {
    const verifiedInput = input({
      label: '',
      file: { upload_id: 'UP-1', original_filename: 'requirements.pdf' },
      source_type: 'DOCUMENT', content: '',
      hybridDetections: { chunks: [{ candidates: [{ label: 'API_SPECIFICATION' }, { label: 'DATABASE_SCHEMA' }] }] },
      humanReviews: { review: { chunks: [{ verified_labels: ['API_SPECIFICATION'] }] } },
      canonicalArtifacts: {
        artifacts: [
          { artifact_type: 'API_SPECIFICATION', status: 'PARTIAL' },
          { artifact_type: 'DATABASE_SCHEMA', status: 'UNRESOLVED' },
        ],
      },
      semanticArtifacts: {
        results: [{ artifact_type: 'API_SPECIFICATION', status: 'HUMAN_REVIEW_REQUIRED' }],
        metrics: { accepted_fact_count: 2, rejected_fact_count: 1, conflict_count: 1 },
      },
    })
    render(
      <SpecificationVerificationPanel
        inputs={[verifiedInput]}
        humanReviewContent={<div>ACCEPT · RELABEL · EXCLUDE · ADD_LABEL</div>}
        researchContent={<div>DETERMINISTIC · extractor version · Source provenance · Qwen semantic preview</div>}
      />,
    )

    expect(screen.getByText('Machine Suggested').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Human Verified').nextSibling).toHaveTextContent('1')
    expect(screen.getByRole('region', { name: 'API Specification' })).toHaveTextContent('requirements.pdf')
    expect(screen.getByRole('region', { name: 'Database Schema' })).toHaveTextContent('Needs Further Interpretation')
    expect(screen.getByText(/ACCEPT · RELABEL/)).toBeInTheDocument()
    expect(screen.getByText('Grounded additions:').parentElement).toHaveTextContent('2')
    expect(screen.getByText('Rejected unsupported information:').parentElement).toHaveTextContent('1')
    expect(screen.getByText('Conflicts requiring review:').parentElement).toHaveTextContent('1')
    const research = screen.getByText('Research Details').closest('details')
    expect(research).not.toHaveAttribute('open')
    expect(within(research).getByText(/DETERMINISTIC/)).toBeInTheDocument()
    expect(within(research).getByText(/Qwen semantic preview/)).toBeInTheDocument()
    expect(within(research).getByText(/Source provenance/)).toBeInTheDocument()
  })

  it('presents grounded additions and conflicts as human semantic decisions', async () => {
    const user = userEvent.setup()
    const onSemanticDecision = vi.fn()
    const fingerprint = 'a'.repeat(64)
    render(
      <SpecificationVerificationPanel
        inputs={[]}
        specificationState={{
          status: 'loaded', error: '', savingDecisionId: null,
          result: {
            status: 'WAITING_FOR_SEMANTIC_REVIEW', ready_source_count: 0,
            applicable_source_count: 1, pending_semantic_decision_count: 2,
          },
          reviews: {
            'UP-1': {
              upload_id: 'UP-1', original_filename: 'api-spec.docx',
              review_fingerprint: fingerprint,
              items: [{
                decision_id: 'SRD-ADD', artifact_type: 'API_SPECIFICATION',
                kind: 'ADDITION', field_path: 'endpoints[0].request_fields',
                deterministic_value: null, semantic_value: ['name', 'email'],
                evidence: [{ chunk_id: 'CHK-1', quote: 'Requires name and email.' }],
                allowed_actions: ['APPROVE_ADDITION', 'REJECT_ADDITION'], decision: null,
              }, {
                decision_id: 'SRD-CONFLICT', artifact_type: 'TECHNOLOGY_STACK',
                kind: 'CONFLICT', field_path: 'stack.database[0]',
                deterministic_value: 'MySQL', semantic_value: 'PostgreSQL',
                evidence: [{ chunk_id: 'CHK-2', quote: 'Use PostgreSQL.' }],
                allowed_actions: ['KEEP_DETERMINISTIC', 'ACCEPT_SEMANTIC_OVERRIDE'], decision: null,
              }],
            },
          },
        }}
        onSemanticDecision={onSemanticDecision}
        researchContent={<button type="button">Run Semantic Fallback</button>}
      />,
    )

    expect(screen.getByText('Semantic Review Required')).toBeInTheDocument()
    expect(screen.getByText(/Requires name and email\./)).toBeInTheDocument()
    expect(screen.getByText('MySQL')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(onSemanticDecision).toHaveBeenCalledWith('UP-1', 'SRD-ADD', {
      action: 'APPROVE_ADDITION', expected_review_fingerprint: fingerprint,
    })
    const research = screen.getByText('Research Details').closest('details')
    expect(within(research).getByRole('button', { name: 'Run Semantic Fallback' })).toBeInTheDocument()
  })

  it('renders cross-source evidence, submits stored choices, and shows the final specification by category', async () => {
    const user = userEvent.setup()
    const onDecision = vi.fn()
    const sourceA = { source_id: 'UP-A', label: 'constraints.pdf' }
    const sourceB = { source_id: 'UP-B', label: 'architecture.docx' }
    const conflict = {
      conflict_id: 'PCF-1', conflict_type: 'TECHNOLOGY_SELECTION',
      artifact_type: 'TECHNOLOGY_STACK', status: 'PENDING',
      fingerprint: 'a'.repeat(64),
      allowed_actions: ['SELECT_CANDIDATE', 'KEEP_BOTH', 'MARK_NOT_CONFLICTING'],
      candidates: [
        { candidate_id: 'PCC-1', label: 'MySQL', value: 'MySQL', supporting_sources: [sourceA] },
        { candidate_id: 'PCC-2', label: 'PostgreSQL', value: 'PostgreSQL', supporting_sources: [sourceB] },
      ],
    }
    const projectItem = {
      project_item_id: 'PSI-1', data: { statement: 'Create booking' },
      supporting_sources: [sourceA, sourceB],
    }
    const { rerender } = render(
      <SpecificationVerificationPanel
        inputs={[]}
        specificationState={{ result: { status: 'SPECIFICATION_READY', ready_source_count: 2, applicable_source_count: 2 } }}
        consolidationState={{
          status: 'loaded', result: { status: 'WAITING_FOR_HUMAN', pending_conflict_count: 1, issues: [], source_set_digest: 'b'.repeat(64) },
          conflicts: [conflict], specification: null, savingConflictId: null,
        }}
        onProjectConflictDecision={onDecision}
      />,
    )

    expect(screen.getByText('Cross-source review required')).toBeInTheDocument()
    const conflictCard = screen.getByText('Technology Conflict').closest('article')
    expect(within(conflictCard).getByText(/constraints\.pdf/)).toBeInTheDocument()
    expect(within(conflictCard).getByText(/architecture\.docx/)).toBeInTheDocument()
    expect(within(conflictCard).queryByText('TECHNOLOGY_SELECTION')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Use MySQL' }))
    expect(onDecision).toHaveBeenCalledWith(conflict, 'SELECT_CANDIDATE', 'PCC-1')

    rerender(
      <SpecificationVerificationPanel
        inputs={[]}
        specificationState={{ result: { status: 'SPECIFICATION_READY', ready_source_count: 2, applicable_source_count: 2 } }}
        consolidationState={{
          status: 'loaded', result: { status: 'READY', pending_conflict_count: 0, issues: [], source_set_digest: 'b'.repeat(64) },
          conflicts: [conflict], savingConflictId: null,
          specification: {
            project_specification_id: 'TPS-1', decision_digest: 'c'.repeat(64),
            categories: { FUNCTIONAL_REQUIREMENTS: [projectItem] },
          },
        }}
        onProjectConflictDecision={onDecision}
      />,
    )
    expect(screen.getByText('Project Specification Ready')).toBeInTheDocument()
    expect(screen.getByText('Functional Requirements').nextSibling).toHaveTextContent('1')
    expect(screen.getByText(/Supported by:/)).toHaveTextContent('constraints.pdf, architecture.docx')
    const research = screen.getByText('Research Details').closest('details')
    expect(research).not.toHaveAttribute('open')
    expect(within(research).getByText(/TPS-1/)).toBeInTheDocument()
    expect(within(research).getByText(/TECHNOLOGY_SELECTION/)).toBeInTheDocument()
  })

  it('renders real readiness findings and keeps the existing evaluation action', async () => {
    const user = userEvent.setup()
    const onCheck = vi.fn()
    render(
      <ImplementationReadinessPanel
        state={{
          status: 'complete', stale: false, error: '',
          result: {
            status: 'READY_WITH_WARNINGS', summary: { errors: 0, warnings: 1, info: 0 },
            coverage: { requirements: true, design: false, implementation: false, tests: false, visual_context_pending: false },
            effective_stack: { frontend: 'React', backend: 'FastAPI' },
            output_readiness: [{ output: 'BACKEND_CODE', ready: true }],
            findings: [{
              finding_id: 'RF-1', severity: 'WARNING', resolved: false, title: 'Tests missing',
              code: 'TESTS_MISSING', message: 'No pre-code tests supplied.', provided_value: null,
              supported_value: null, allowed_resolutions: [],
            }],
          },
        }}
        workspaceBusy={false}
        errors={{}}
        onCheck={onCheck}
        onAdapt={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    expect(screen.getByText('READY WITH WARNINGS')).toBeInTheDocument()
    expect(screen.getByText('Tests missing')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Check Implementation Readiness' }))
    expect(onCheck).toHaveBeenCalledOnce()
  })

  it('presents existing GitHub and repository state as one delivery setup experience', async () => {
    const user = userEvent.setup()
    const onConnect = vi.fn()
    const githubState = { status: 'disconnected', connection: null, notice: '', error: '' }
    const repositoryState = { status: 'idle', repository: null, error: '' }
    render(
      <DeliverySetupPanel
        githubState={githubState}
        repositoryState={repositoryState}
        integrationProps={{
          githubState, repositoryState, repositoryForm: { name: '', description: '', visibility: 'PRIVATE' },
          setRepositoryForm: vi.fn(), setRepositoryState: vi.fn(), onConnect, onCreateRepository: vi.fn(),
        }}
      />,
    )
    expect(screen.getByText(/GitHub Account:/).parentElement).toHaveTextContent('Not connected')
    expect(screen.getByText(/Repository:/).parentElement).toHaveTextContent('Not created yet')
    await user.click(screen.getByRole('button', { name: 'Connect GitHub' }))
    expect(onConnect).toHaveBeenCalledOnce()
  })
})
