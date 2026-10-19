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
        canAnalyze
        analyzing={false}
        onAnalyze={vi.fn()}
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
    expect(within(overview).getByText('Analyzed').nextSibling).toHaveTextContent('1')
    expect(within(overview).getByText('Needs Review').nextSibling).toHaveTextContent('0')
    expect(within(overview).getByText('Failed').nextSibling).toHaveTextContent('1')
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

    expect(screen.getByText('Needs Review').nextSibling).toHaveTextContent('1')
    const overview = screen.getByRole('heading', { name: 'Source analysis overview' }).closest('section')
    expect(within(overview).getByText('Failed').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('requirements.pdf').closest('div').parentElement).toHaveTextContent('Complete')
    expect(screen.getByText('api-spec.docx').closest('div').parentElement).toHaveTextContent('Needs your review')
    expect(screen.getByText('broken.yaml').closest('div').parentElement).toHaveTextContent('The document could not be extracted.')
    await user.click(screen.getByRole('button', { name: 'Retry Input Analysis' }))
    expect(onAnalyze).toHaveBeenCalledOnce()
  })

  it('presents completed analysis as a handoff with accurate review counters', async () => {
    const user = userEvent.setup()
    const onGoToVerification = vi.fn()
    render(
      <InputAnalysisPanel
        inputs={[]}
        preparationState={{
          status: 'loaded', error: '',
          result: {
            status: 'WAITING_FOR_HUMAN', source_count: 3,
            completed_source_count: 3, failed_source_count: 0,
            human_review_source_count: 3,
            sources: [1, 2, 3].map((index) => ({
              source_id: `UP-${index}`, filename: `source-${index}.pdf`,
              source_kind: 'DOCUMENT', status: 'WAITING_FOR_HUMAN',
            })),
          },
        }}
        onGoToVerification={onGoToVerification}
      />,
    )

    const overview = screen.getByRole('heading', { name: 'Source analysis overview' }).closest('section')
    expect(within(overview).getByText('Complete')).toBeInTheDocument()
    expect(within(overview).getByText('Analyzed').nextSibling).toHaveTextContent('3')
    expect(within(overview).getByText('Needs Review').nextSibling).toHaveTextContent('3')
    expect(screen.getByText('Analysis complete. 3 sources need confirmation.')).toBeInTheDocument()
    expect(screen.queryByText('Needs Attention 0')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Go to Specification Verification' }))
    expect(onGoToVerification).toHaveBeenCalledOnce()
  })

  it('keeps a completed Input Analysis panel truthful while the next stage progresses', () => {
    render(
      <InputAnalysisPanel
        inputs={[]}
        preparationState={{
          status: 'loaded', error: '',
          result: {
            status: 'ANALYSIS_READY', source_count: 3,
            completed_source_count: 3, failed_source_count: 0, sources: [],
          },
        }}
      />,
    )

    expect(screen.getByText('✓ Analysis complete')).toBeInTheDocument()
    expect(screen.getByText('3 sources analyzed.')).toBeInTheDocument()
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
    expect(screen.getByText('Should this grounded information be included in the trusted specification?')).toBeInTheDocument()
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

  it('surfaces required artifact decisions outside Research Details', async () => {
    const user = userEvent.setup()
    const onOpenArtifactReview = vi.fn()
    render(
      <SpecificationVerificationPanel
        inputs={[]}
        preparationState={{
          result: {
            status: 'WAITING_FOR_HUMAN',
            sources: [{
              source_id: 'UP-REVIEW', filename: 'requirements.pdf', status: 'WAITING_FOR_HUMAN',
            }],
          },
        }}
        onOpenArtifactReview={onOpenArtifactReview}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Input Classification Review' })).toBeInTheDocument()
    expect(screen.getByText('1 decision required')).toBeInTheDocument()
    expect(screen.getAllByText(/requirements\.pdf/).length).toBeGreaterThan(0)
    const action = screen.getByRole('button', { name: 'Review Now' })
    expect(action.closest('details')).toBeNull()
    await user.click(action)
    expect(onOpenArtifactReview).toHaveBeenCalledWith('UP-REVIEW')
  })

  it('shows a three-source queue at zero reviewed without fabricating labels', () => {
    const sources = [
      { source_id: 'UP-1', filename: 'requirements.txt', artifact_type: 'FUNCTIONAL_REQUIREMENTS', status: 'WAITING_FOR_HUMAN' },
      { source_id: 'UP-2', filename: 'api.pdf', artifact_type: 'API_SPECIFICATION', status: 'WAITING_FOR_HUMAN' },
      { source_id: 'UP-3', filename: 'flow.md', artifact_type: 'UI_FLOW', status: 'WAITING_FOR_HUMAN' },
    ]
    render(
      <SpecificationVerificationPanel
        inputs={[]}
        preparationState={{ result: { status: 'WAITING_FOR_HUMAN', sources } }}
        artifactReviewQueue={sources}
      />,
    )

    expect(screen.getByText('3 decisions required')).toBeInTheDocument()
    expect(screen.getAllByText(/0 \/ 3 reviewed/).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Review Now' })).toHaveLength(3)
    expect(screen.getByText('Suggested: Functional Requirements')).toBeInTheDocument()
    expect(screen.getByText('Suggested: API Specification')).toBeInTheDocument()
    expect(screen.getByText('Suggested: UI Flow')).toBeInTheDocument()
  })

  it('switches the same surface into focused source review and returns to the queue', async () => {
    const user = userEvent.setup()
    const onBack = vi.fn()
    const source = {
      source_id: 'UP-REVIEW', filename: 'requirements.pdf',
      artifact_type: 'FUNCTIONAL_REQUIREMENTS', status: 'WAITING_FOR_HUMAN',
    }
    render(
      <SpecificationVerificationPanel
        inputs={[]}
        preparationState={{ result: { status: 'WAITING_FOR_HUMAN', sources: [source] } }}
        artifactReviewQueue={[source]}
        selectedArtifactReviewSourceId="UP-REVIEW"
        artifactReviewState={{
          uploadId: 'UP-REVIEW', status: 'loaded',
          result: {
            review: { review_status: 'NOT_STARTED' },
            review_queue: [{
              chunk: { text: 'Users can create bookings.' },
              review: { review_status: 'UNREVIEWED' },
              hybrid: { candidates: [{ label: 'FUNCTIONAL_REQUIREMENTS', decision: 'REVIEW_REQUIRED' }] },
            }],
          },
        }}
        humanReviewContent={<section aria-label="Human Artifact Verification Review">Existing review controls</section>}
        onBackToArtifactReviewList={onBack}
      />,
    )

    expect(screen.getByTestId('focused-source-review')).toBeInTheDocument()
    expect(screen.getByText('Source 1 of 1')).toBeInTheDocument()
    expect(screen.getByText('How should this information be classified?')).toBeInTheDocument()
    expect(screen.getByText(/Suggested classification: Functional Requirements/)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Human Artifact Verification Review' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to Review List' }))
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('marks a backend-complete source reviewed and offers the next pending source', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    const sources = [
      { source_id: 'UP-1', filename: 'requirements.txt', status: 'READY' },
      { source_id: 'UP-2', filename: 'api.pdf', status: 'WAITING_FOR_HUMAN' },
      { source_id: 'UP-3', filename: 'flow.md', status: 'WAITING_FOR_HUMAN' },
    ]
    render(
      <SpecificationVerificationPanel
        inputs={[]}
        preparationState={{ result: { status: 'WAITING_FOR_HUMAN', sources } }}
        artifactReviewQueue={sources}
        selectedArtifactReviewSourceId="UP-1"
        artifactReviewState={{
          uploadId: 'UP-1', status: 'loaded',
          result: { review: { review_status: 'COMPLETE' }, review_queue: [] },
        }}
        onOpenArtifactReview={onOpen}
      />,
    )

    expect(screen.getByText('✓ Classification review complete')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Review Next Source' }))
    expect(onOpen).toHaveBeenCalledWith('UP-2')
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
    expect(screen.getByText('Which conflicting project information should Agent 3 use?')).toBeInTheDocument()
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
    expect(screen.getByText('Do you want Agent 3 to continue with these warnings?')).toBeInTheDocument()
    const research = screen.getByRole('button', { name: 'Re-evaluate Readiness' }).closest('details')
    expect(research).not.toHaveAttribute('open')
    await user.click(within(research).getByRole('button', { name: 'Re-evaluate Readiness' }))
    expect(onCheck).toHaveBeenCalledOnce()
  })

  it('presents existing GitHub and repository state as one delivery setup experience', async () => {
    const user = userEvent.setup()
    const onConnect = vi.fn()
    const onContinue = vi.fn()
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
        onContinue={onContinue}
      />,
    )
    expect(screen.getByText(/GitHub Account:/).parentElement).toHaveTextContent('Not connected')
    expect(screen.getByText(/Repository:/).parentElement).toHaveTextContent('Not created yet')
    expect(screen.getByText('How should the generated implementation be delivered?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Connect GitHub' }))
    expect(onConnect).toHaveBeenCalledOnce()
    await user.click(screen.getByRole('button', { name: 'Continue Without Repository Delivery' }))
    expect(onContinue).toHaveBeenCalledOnce()
  })

  it('shows completed delivery without repeating its decision action', () => {
    const githubState = { status: 'disconnected', connection: null, notice: '', error: '' }
    const repositoryState = { status: 'idle', repository: null, error: '' }
    render(
      <DeliverySetupPanel
        githubState={githubState}
        repositoryState={repositoryState}
        deliveryDecision="SKIPPED"
        integrationProps={{
          githubState, repositoryState, repositoryForm: { name: '', description: '', visibility: 'PRIVATE' },
          setRepositoryForm: vi.fn(), setRepositoryState: vi.fn(), onConnect: vi.fn(), onCreateRepository: vi.fn(),
        }}
        onContinue={vi.fn()}
      />,
    )

    expect(screen.getByText('✓ Delivery setup complete')).toBeInTheDocument()
    expect(screen.getByText('The implementation plan is ready for final approval.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Continue Without Repository Delivery' })).not.toBeInTheDocument()
  })
})
