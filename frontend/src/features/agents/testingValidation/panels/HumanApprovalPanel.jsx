import { ReviewExperience } from './TestingIntelligencePanel.jsx'

function HumanApprovalPanel({
  definition,
  intelligenceError,
  intelligenceReview,
  n3Execution,
  onRetryIntelligenceSource,
  onSubmitIntelligenceReview,
  retryingIntelligenceSourceId,
  reviewSubmitting,
  workflowNodeStatus,
}) {
  const waiting = workflowNodeStatus === 'WAITING_FOR_HUMAN'
  const complete = workflowNodeStatus === 'COMPLETED'

  return <section className="space-y-4" aria-label={`${definition.title} details`}>
    {intelligenceError ? <p role="alert" className="text-sm text-state-danger">{intelligenceError}</p> : null}
    {waiting ? <div className="space-y-3">
      <div>
        <p className="font-semibold text-content-primary">Approval required</p>
        <p className="mt-1 text-sm text-content-secondary">Review the uncertain classifications before Testing Fact Extraction continues.</p>
      </div>
      <ReviewExperience
        key={intelligenceReview?.review_snapshot_fingerprint}
        execution={n3Execution}
        onRetry={onRetryIntelligenceSource}
        onSubmit={onSubmitIntelligenceReview}
        retryingSourceId={retryingIntelligenceSourceId}
        review={intelligenceReview}
        submitting={reviewSubmitting}
      />
    </div> : complete ? <div role="status" className="rounded-control border border-state-success/40 bg-state-success/10 p-4">
      <p className="font-semibold text-state-success">✓ Human Approval complete</p>
      <p className="mt-1 text-sm text-content-secondary">Required decisions were approved, or no uncertain classifications required manual review.</p>
    </div> : <p className="text-sm text-content-secondary">This checkpoint becomes available after Testing Intelligence and is completed automatically when no human review is required.</p>}
  </section>
}

export default HumanApprovalPanel
