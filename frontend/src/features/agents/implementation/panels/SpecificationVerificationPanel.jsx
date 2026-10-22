import ArtifactGroup from '../components/common/ArtifactGroup.jsx'
import HumanDecisionCallout from '../components/common/HumanDecisionCallout.jsx'
import ResearchDetails from '../components/common/ResearchDetails.jsx'
import SemanticReviewCards from '../components/review/SemanticReviewCards.jsx'
import { specificationPresentation } from '../constants/specification.js'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import Button from '../../../../components/ui/Button.jsx'
import { reviewTaxonomy } from '../constants/workspace.js'
import { sourceName } from '../utils/sourcePresentation.js'
import { detectionLabel } from '../utils/presentation.js'
import {
  ConsolidationResearchDetails,
  CrossSourceReview,
  FinalProjectSpecification,
} from '../components/review/ProjectSpecificationReview.jsx'

function aggregateArtifacts(inputs) {
  const groups = new Map()
  function include(type, source, layer, status = null, verified = false) {
    if (!type || type === 'OTHER_CONTEXT') return
    const group = groups.get(type) ?? {
      type, sources: new Set(), layers: new Set(), statuses: [], verifiedCount: 0,
    }
    group.sources.add(source)
    group.layers.add(layer)
    if (status) group.statuses.push(status)
    if (verified) group.verifiedCount += 1
    groups.set(type, group)
  }

  let machineSuggestions = 0
  let verifiedReferences = 0
  inputs.forEach((input, index) => {
    const source = sourceName(input, index)
    input.hybridDetections?.chunks?.forEach((chunk) => {
      chunk.candidates?.forEach((candidate) => {
        machineSuggestions += 1
        include(candidate.label, source, 'Machine suggested')
      })
    })
    input.humanReviews?.review?.chunks?.forEach((chunk) => {
      chunk.verified_labels?.forEach((label) => {
        verifiedReferences += 1
        include(label, source, 'Human verified', 'COMPLETE', true)
      })
    })
    input.canonicalArtifacts?.artifacts?.forEach((artifact) => {
      include(artifact.artifact_type, source, 'Deterministic specification', artifact.status)
    })
    input.semanticArtifacts?.results?.forEach((artifact) => {
      include(artifact.artifact_type, source, 'Semantic preview', artifact.status)
    })
  })

  const ordered = reviewTaxonomy
    .map((type) => groups.get(type))
    .filter(Boolean)
    .map((group) => ({
      ...group,
      status: group.statuses.includes('HUMAN_REVIEW_REQUIRED') || group.statuses.includes('UNRESOLVED')
        ? 'HUMAN_REVIEW_REQUIRED'
        : group.statuses.includes('PARTIAL') ? 'PARTIAL' : group.statuses.includes('COMPLETE') ? 'COMPLETE' : null,
    }))
  return { groups: ordered, machineSuggestions, verifiedReferences }
}

export default function SpecificationVerificationPanel({
  inputs,
  preparationState,
  humanReviewContent,
  researchContent,
  specificationState,
  consolidationState,
  onSemanticDecision,
  onProjectConflictDecision,
  onOpenArtifactReview,
  onBackToArtifactReviewList,
  artifactReviewQueue = [],
  artifactReviewState,
  selectedArtifactReviewSourceId = null,
}) {
  const { groups, machineSuggestions, verifiedReferences } = aggregateArtifacts(inputs)
  const semanticMetrics = inputs.reduce((summary, input) => ({
    grounded: summary.grounded + (input.semanticArtifacts?.metrics?.accepted_fact_count ?? 0),
    rejected: summary.rejected + (input.semanticArtifacts?.metrics?.rejected_fact_count ?? 0),
    conflicts: summary.conflicts + (input.semanticArtifacts?.metrics?.conflict_count ?? 0),
  }), { grounded: 0, rejected: 0, conflicts: 0 })
  const specification = specificationState?.result
  const presentation = specificationPresentation(specification?.status)
  const consolidation = consolidationState?.result
  const consolidationLabel = {
    NOT_STARTED: 'Awaiting trusted source artifacts',
    CONSOLIDATING: 'Processing',
    WAITING_FOR_HUMAN: 'Cross-source review required',
    READY: 'Project Specification Ready',
    PARTIAL_FAILURE: 'Incomplete source set',
    FAILED: 'Consolidation failed',
    STALE: 'Source set changed',
  }[consolidation?.status] ?? 'Not started'
  const phaseRows = [
    {
      label: 'Input Classification',
      value: preparationState?.result?.status === 'RUNNING' ? 'Preparing'
        : preparationState?.result?.status === 'WAITING_FOR_HUMAN' ? 'Needs your review'
          : ['ANALYSIS_READY', 'PARTIAL_FAILURE'].includes(preparationState?.result?.status) ? 'Complete' : 'Waiting',
    },
    {
      label: 'Semantic Structuring',
      value: specification?.status === 'PREPARING_SPECIFICATION' ? 'Preparing'
        : specification?.status === 'SPECIFICATION_READY' ? 'Complete'
          : ['WAITING_FOR_ARTIFACT_REVIEW', 'WAITING_FOR_SEMANTIC_REVIEW'].includes(specification?.status) ? 'Needs your review' : 'Waiting',
    },
    {
      label: 'Project Consolidation',
      value: consolidation?.status === 'CONSOLIDATING' ? 'Preparing'
        : consolidation?.status === 'WAITING_FOR_HUMAN' ? 'Needs your review'
          : consolidation?.status === 'READY' ? 'Complete' : 'Waiting',
    },
    {
      label: 'Final Trusted Specification',
      value: consolidation?.status === 'READY' ? 'Complete' : 'Waiting',
    },
  ]
  const artifactReviewSources = (preparationState?.result?.sources ?? []).filter(
    (source) => source.status === 'WAITING_FOR_HUMAN',
  )
  const reviewSources = artifactReviewQueue.length > 0 ? artifactReviewQueue : artifactReviewSources
  const selectedReviewSource = reviewSources.find(
    (source) => source.source_id === selectedArtifactReviewSourceId,
  )
  const selectedReviewComplete = Boolean(
    selectedArtifactReviewSourceId
    && artifactReviewState?.uploadId === selectedArtifactReviewSourceId
    && artifactReviewState?.result?.review?.review_status === 'COMPLETE',
  )
  const reviewedCount = reviewSources.filter((source) => (
    source.source_id === selectedArtifactReviewSourceId && selectedReviewComplete
      ? true
      : source.status !== 'WAITING_FOR_HUMAN'
  )).length
  const nextReviewSource = reviewSources.find((source) => (
    source.status === 'WAITING_FOR_HUMAN' && source.source_id !== selectedArtifactReviewSourceId
  ))
  const finalReviewConfirmed = selectedReviewComplete
    && !nextReviewSource
    && preparationState?.result?.status !== 'WAITING_FOR_HUMAN'
  const selectedReviewResult = artifactReviewState?.uploadId === selectedArtifactReviewSourceId
    ? artifactReviewState?.result
    : null
  const currentReviewItem = selectedReviewResult?.review_queue?.find(
    (item) => item.review?.review_status !== 'VERIFIED',
  ) ?? selectedReviewResult?.review_queue?.[0]
  const suggestedLabels = currentReviewItem?.hybrid?.candidates
    ?.filter((candidate) => candidate.decision !== 'REJECTED')
    .map((candidate) => detectionLabel(candidate.label)) ?? []
  const artifactReviewPending = artifactReviewSources.length > 0
  const semanticReviewPending = !artifactReviewPending && specification?.status === 'WAITING_FOR_SEMANTIC_REVIEW'
  const conflictReviewPending = !artifactReviewPending && !semanticReviewPending
    && consolidation?.status === 'WAITING_FOR_HUMAN'

  if (selectedArtifactReviewSourceId) {
    const sourcePosition = Math.max(
      reviewSources.findIndex((source) => source.source_id === selectedArtifactReviewSourceId),
      0,
    )
    return (
      <div className="space-y-5" data-testid="focused-source-review">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button variant="outline" size="small" onClick={onBackToArtifactReviewList}>Back to Review List</Button>
          <p className="text-sm font-medium text-content-secondary">Source {sourcePosition + 1} of {reviewSources.length}</p>
        </div>
        <div>
          <h3 className="break-words text-card-heading font-semibold text-content-primary">
            {selectedReviewSource?.filename || selectedReviewSource?.label || selectedArtifactReviewSourceId}
          </h3>
          <p className="mt-1 text-sm text-content-secondary">Why Agent 3 stopped: This source contains artifact classifications that require human confirmation.</p>
        </div>
        {selectedReviewComplete ? (
          <section className="rounded-control border border-state-success/40 bg-state-success-soft p-4" role="status">
            <h3 className="font-semibold text-content-primary">✓ Classification review complete</h3>
            <p className="mt-2 text-sm text-content-secondary">
              {nextReviewSource
                ? 'Your saved decisions are reflected in the review queue.'
                : finalReviewConfirmed
                  ? 'Agent 3 is continuing automatically...'
                  : 'Your decision was saved. Agent 3 is confirming that every required review is complete.'}
            </p>
            {!nextReviewSource && preparationState?.error ? <p role="alert" className="mt-2 text-sm text-state-danger">{preparationState.error}</p> : null}
            {nextReviewSource ? (
              <Button className="mt-4" onClick={() => onOpenArtifactReview?.(nextReviewSource.source_id)}>Review Next Source</Button>
            ) : null}
          </section>
        ) : (
          <>
            <HumanDecisionCallout
              title="How should this information be classified?"
              description={suggestedLabels.length > 0 ? `Suggested classification: ${suggestedLabels.join(', ')}` : 'Review the source evidence and confirm, relabel, exclude, or add the appropriate classification.'}
              evidence={currentReviewItem?.chunk?.text || selectedReviewSource?.filename || selectedReviewSource?.label || selectedArtifactReviewSourceId}
              outcome="Agent 3 will continue once all required source reviews are complete."
            />
            {humanReviewContent}
          </>
        )}
        <ResearchDetails description="Access the full file-level extraction, classification, and provenance details for this source.">
          {researchContent}
        </ResearchDetails>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {artifactReviewPending ? (
        <HumanDecisionCallout
          title={`${artifactReviewSources.length} ${artifactReviewSources.length === 1 ? 'decision' : 'decisions'} required`}
          description={`Agent 3 analyzed all project inputs. ${artifactReviewSources.length === 1 ? 'One source contains' : `${artifactReviewSources.length} sources contain`} classifications that require your confirmation before structured specification generation can continue.`}
          evidence={artifactReviewSources.map((source) => source.filename || source.label || source.source_id).join(', ')}
          outcome="Agent 3 resumes semantic preparation after every required source review is complete."
        />
      ) : semanticReviewPending ? (
        <HumanDecisionCallout
          title="Should this grounded information be included in the trusted specification?"
          description="Compare the verified value with the grounded semantic suggestion, then approve or reject each item."
          evidence={`${specification.pending_semantic_decision_count} semantic decisions require review.`}
          outcome="Project consolidation begins only after all semantic decisions are complete."
        />
      ) : conflictReviewPending ? (
        <HumanDecisionCallout
          title="Which conflicting project information should Agent 3 use?"
          description="Select the supported candidate for each cross-source conflict. Source evidence remains visible with every option."
          evidence={`${consolidation.pending_conflict_count} cross-source decisions require review.`}
          outcome="The final trusted project specification becomes ready after every conflict is resolved."
        />
      ) : null}
      <section aria-labelledby="verification-phases-title" className="space-y-3">
        <div>
          <h3 id="verification-phases-title" className="font-semibold text-content-primary">Verification progress</h3>
          <p className="mt-1 text-sm text-content-secondary">Mechanical preparation continues automatically and pauses only when your decision is required.</p>
        </div>
        <ol className="divide-y divide-default rounded-control border border-default">
          {phaseRows.map((phase) => (
            <li key={phase.label} className="flex items-center justify-between gap-4 px-3 py-3 text-sm">
              <span className="font-medium text-content-primary">{phase.label}</span>
              <span className={phase.value === 'Complete' ? 'text-state-success' : phase.value === 'Needs your review' ? 'text-state-warning' : 'text-content-secondary'}>{phase.value}</span>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="specification-preparation-title" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 id="specification-preparation-title" className="font-semibold text-content-primary">Structured Specification</h3>
            <p className="mt-1 text-sm text-content-secondary">Deterministic extraction and grounded semantic fallback continue automatically after artifact verification.</p>
          </div>
          <StatusBadge label={presentation.label} tone={presentation.tone} />
        </div>
        {artifactReviewPending ? (
          <p className="text-sm text-content-secondary">
            {reviewedCount} / {reviewSources.length} reviewed
          </p>
        ) : specification ? (
          <p className="text-sm text-content-secondary">
            {specification.ready_source_count} / {specification.applicable_source_count} sources prepared
            {specification.pending_semantic_decision_count > 0 ? ` · ${specification.pending_semantic_decision_count} decisions required` : ''}
          </p>
        ) : null}
        {specificationState?.status === 'loading' ? <p className="text-sm text-content-secondary">Loading specification status...</p> : null}
        {specificationState?.error ? <p role="alert" className="text-sm text-state-danger">{specificationState.error}</p> : null}
      </section>

      {reviewSources.length > 0 && (artifactReviewPending || reviewedCount < reviewSources.length) ? (
        <section aria-labelledby="artifact-review-title" className="space-y-3">
          <div>
            <h3 id="artifact-review-title" className="font-semibold text-content-primary">Input Classification Review</h3>
            <p className="mt-1 text-sm text-content-secondary">Progress: {reviewedCount} / {reviewSources.length} reviewed</p>
          </div>
          <div className="space-y-2">
            {reviewSources.map((source, index) => {
              const pending = source.status === 'WAITING_FOR_HUMAN'
              return (
              <div key={source.source_id} className="flex items-center justify-between gap-4 rounded-control border border-state-warning p-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-content-muted">{index + 1}.</p>
                  <p className="truncate text-sm font-medium text-content-primary">{source.filename || source.label || source.source_id}</p>
                  {source.artifact_type ? <p className="mt-1 text-xs text-content-secondary">Suggested: {detectionLabel(source.artifact_type)}</p> : null}
                  <p className={`mt-1 text-xs ${pending ? 'text-state-warning' : 'text-state-success'}`}>{pending ? 'Needs your review' : '✓ Reviewed'}</p>
                </div>
                {pending ? (
                  <Button variant="outline" size="small" onClick={() => onOpenArtifactReview?.(source.source_id)}>
                    Review Now
                  </Button>
                ) : null}
              </div>
              )
            })}
          </div>
        </section>
      ) : null}

      {semanticReviewPending ? (
        <section aria-labelledby="semantic-review-title" className="space-y-3">
          <div>
            <h3 id="semantic-review-title" className="font-semibold text-content-primary">Semantic Review</h3>
            <p className="mt-1 text-sm text-content-secondary">Approve only grounded additions, or resolve conflicts between the verified deterministic value and a grounded semantic interpretation.</p>
          </div>
          <SemanticReviewCards
            reviews={specificationState.reviews}
            savingDecisionId={specificationState.savingDecisionId}
            onDecision={onSemanticDecision}
          />
        </section>
      ) : null}

      {specification?.status === 'SPECIFICATION_READY' ? (
        <p className="rounded-control border border-state-success p-4 text-sm text-content-primary">Final trusted artifacts are prepared for every applicable source.</p>
      ) : null}

      <section aria-labelledby="project-consolidation-title" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 id="project-consolidation-title" className="font-semibold text-content-primary">Project Consolidation</h3>
            <p className="mt-1 text-sm text-content-secondary">Trusted source artifacts are consolidated deterministically; interpretation remains under human control.</p>
          </div>
          <StatusBadge
            label={consolidationLabel}
            tone={consolidation?.status === 'READY' ? 'success'
              : ['WAITING_FOR_HUMAN', 'STALE', 'PARTIAL_FAILURE'].includes(consolidation?.status) ? 'warning'
                : consolidation?.status === 'FAILED' ? 'danger' : 'neutral'}
          />
        </div>
        {consolidation?.status === 'WAITING_FOR_HUMAN' ? (
          <p className="text-sm text-state-warning">{consolidation.pending_conflict_count} cross-source {consolidation.pending_conflict_count === 1 ? 'decision' : 'decisions'} required</p>
        ) : null}
        {consolidation?.issues?.map((issue) => (
          <p key={`${issue.source_id}-${issue.error_code}`} role="alert" className="text-sm text-state-warning">{issue.message}</p>
        ))}
        {consolidationState?.status === 'starting' ? <p className="text-sm text-content-secondary">Consolidating the current trusted source set...</p> : null}
        {consolidationState?.error ? <p role="alert" className="text-sm text-state-danger">{consolidationState.error}</p> : null}
      </section>

      {conflictReviewPending ? (
        <CrossSourceReview
          conflicts={consolidationState?.conflicts ?? []}
          savingConflictId={consolidationState?.savingConflictId}
          onDecision={onProjectConflictDecision}
        />
      ) : null}

      <FinalProjectSpecification specification={consolidationState?.specification} />

      <section aria-labelledby="verification-summary-title">
        <h3 id="verification-summary-title" className="font-semibold text-content-primary">Specification summary</h3>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div className="border-l-2 border-accent-border pl-3"><dt className="text-content-muted">Machine Suggested</dt><dd className="mt-1 text-xl font-semibold text-content-primary">{machineSuggestions}</dd></div>
          <div className="border-l-2 border-state-success pl-3"><dt className="text-content-muted">Human Verified</dt><dd className="mt-1 text-xl font-semibold text-content-primary">{verifiedReferences}</dd></div>
        </dl>
      </section>

      <section aria-labelledby="verified-specification-title" className="space-y-4">
        <div>
          <h3 id="verified-specification-title" className="font-semibold text-content-primary">Verified Specification</h3>
          <p className="mt-1 text-sm text-content-secondary">Available file-scoped artifacts grouped across the project while preserving their source.</p>
        </div>
        {groups.length > 0 ? groups.map((group) => <ArtifactGroup key={group.type} group={group} />) : (
          <p className="rounded-control border border-dashed border-default p-4 text-sm text-content-secondary">No machine-suggested or human-verified specification artifacts are loaded yet.</p>
        )}
      </section>

      {(semanticMetrics.grounded > 0 || semanticMetrics.rejected > 0 || semanticMetrics.conflicts > 0) ? (
        <section aria-labelledby="semantic-summary-title">
          <h3 id="semantic-summary-title" className="font-semibold text-content-primary">Suggested Structured Information</h3>
          <dl className="mt-3 grid gap-2 text-sm">
            <div><dt className="inline text-content-muted">Grounded additions: </dt><dd className="inline text-content-primary">{semanticMetrics.grounded}</dd></div>
            <div><dt className="inline text-content-muted">Rejected unsupported information: </dt><dd className="inline text-content-primary">{semanticMetrics.rejected}</dd></div>
            <div><dt className="inline text-content-muted">Conflicts requiring review: </dt><dd className="inline text-content-primary">{semanticMetrics.conflicts}</dd></div>
          </dl>
        </section>
      ) : null}

      {humanReviewContent ? (
        <section aria-labelledby="human-verification-title">
          <h3 id="human-verification-title" className="font-semibold text-content-primary">Human Verification</h3>
          <p className="mt-1 text-sm text-content-secondary">Compare machine suggestions with human-verified decisions.</p>
          {humanReviewContent}
        </section>
      ) : null}

      <ResearchDetails description="Access file-level extraction, rule baseline, DeBERTa, hybrid analysis, human review controls, deterministic canonical details, semantic/Qwen previews, metrics, and provenance.">
        <div className="space-y-5">
          <ConsolidationResearchDetails
            status={consolidation}
            conflicts={consolidationState?.conflicts ?? []}
            specification={consolidationState?.specification}
          />
          {researchContent}
        </div>
      </ResearchDetails>
    </div>
  )
}
