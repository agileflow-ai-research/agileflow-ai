import Button from '../../../../components/ui/Button.jsx'
import { DetailLoadState, DisclosureSection, LoadMoreButton, NextStep, PresentationSection, ResultBanner } from './NodePresentation.jsx'

function friendlyStatus(status) {
  return ({ COMPLETED: 'Ready', NOT_APPLICABLE: 'Not required', QUEUED: 'Preparing to start', RUNNING: 'In progress', FAILED: 'Could not complete', INTERRUPTED: 'Interrupted — retry available' })[status] || 'Not started'
}

function TestingFactExtractionPanel({ definition, detailData, detailError, detailStatus, intelligenceError, n3Execution, onLoadMoreDetails, onRetryDetails, onRetryIntelligenceSource, retryingIntelligenceSourceId, workflowNodeStatus }) {
  const factStage = n3Execution?.sub_stages?.find((stage) => stage.stage === 'TI_FACT_EXTRACTION')
  const sources = n3Execution?.sources || []
  const preparedSections = sources.reduce((count, source) => count + (source.fact_extraction_chunks?.length || 0), 0)
  const facts = sources.reduce((count, source) => count + (source.semantic_fact_count || 0), 0)
  const failedSources = sources.filter((source) => {
    const stage = source.sub_stages?.find((item) => item.stage === 'TI_FACT_EXTRACTION')
    return ['FAILED', 'INTERRUPTED'].includes(stage?.status)
  })
  const warnings = sources.reduce((count, source) => count + (source.warnings?.length || 0), 0)
  const queued = workflowNodeStatus === 'QUEUED' || factStage?.status === 'QUEUED'
  const running = workflowNodeStatus === 'RUNNING' || factStage?.status === 'RUNNING'
  const completed = workflowNodeStatus === 'COMPLETED'
  const failed = workflowNodeStatus === 'FAILED'

  return <section className="space-y-4" aria-label={`${definition.title} details`}>
    {intelligenceError ? <p role="alert" className="text-sm text-state-danger">{intelligenceError}</p> : null}
    <PresentationSection label="Result" title="Testing facts prepared from approved evidence">
      <ResultBanner tone={completed ? 'success' : failed ? 'danger' : queued || running ? 'info' : 'neutral'} title={completed ? 'Testing facts are ready' : failed ? 'Testing fact extraction could not complete — retry available' : queued ? 'Waiting for extraction capacity' : running ? 'Extracting testing facts' : 'Waiting for approved classifications'} description={completed ? 'Agent 4 produced grounded testing facts for Context & Testability.' : failed ? 'Completed source and section results are preserved for a safe retry.' : queued || running ? 'The local semantic model is processing only approved evidence.' : 'This step starts after Testing Intelligence and any required human review.'} metrics={[{ label: 'Sources', value: sources.length }, { label: 'Prepared sections', value: preparedSections }, { label: 'Testing facts', value: facts }, { label: 'Warnings / failures', value: warnings + failedSources.length }]} />
    </PresentationSection>
    {sources.length ? <PresentationSection label="Supporting evidence" title="Source results"><div className="space-y-2">{sources.map((source) => {
      const stage = source.sub_stages?.find((item) => item.stage === 'TI_FACT_EXTRACTION')
      const sourceFailed = ['FAILED', 'INTERRUPTED'].includes(stage?.status)
      const processed = source.fact_extraction_chunks?.length || 0
      return <article key={source.source_id} className="rounded-control border border-default bg-surface p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium text-content-primary">{source.label || source.original_filename || 'Project source'}</p><span className={sourceFailed ? 'text-state-danger' : ['COMPLETED', 'NOT_APPLICABLE'].includes(stage?.status) ? 'text-state-success' : 'text-content-secondary'}>{friendlyStatus(stage?.status)}</span></div><p className="mt-1 text-sm text-content-secondary">{processed} prepared section{processed === 1 ? '' : 's'} · {source.semantic_fact_count || 0} testing fact{source.semantic_fact_count === 1 ? '' : 's'}</p>{sourceFailed ? <div className="mt-2"><p className="text-sm text-state-danger">{stage?.safe_error?.message || source.error?.message || 'Fact extraction could not complete.'}</p>{source.retryable !== false ? <Button className="mt-2" size="small" variant="outline" loading={retryingIntelligenceSourceId === source.source_id} disabled={Boolean(retryingIntelligenceSourceId)} onClick={() => { void onRetryIntelligenceSource(source.source_id) }}>Retry incomplete extraction</Button> : null}</div> : null}<div className="mt-3"><DisclosureSection title="Technical details" summary="Internal stage, chunk checkpoints, and source identifier"><dl className="grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">Internal stage status</dt><dd className="text-content-secondary">{stage?.status || 'NOT_STARTED'}</dd></div><div><dt className="text-content-muted">Checkpointed chunks</dt><dd className="text-content-secondary">{processed}</dd></div><div className="sm:col-span-2"><dt className="text-content-muted">Source ID</dt><dd className="break-all text-content-secondary">{source.source_id}</dd></div></dl></DisclosureSection></div></article>
    })}</div></PresentationSection> : null}
    <PresentationSection label="View extracted output" title={`Testing Facts${detailData ? ` (${detailData.total})` : ''}`} description="Only facts accepted by Agent 4's persisted grounding validation are shown.">
      <DetailLoadState error={detailError} onRetry={onRetryDetails} status={detailStatus} />
      {detailData?.items?.length ? <div className="space-y-3">{detailData.items.map((fact) => <article key={fact.fact_id} className="rounded-control border border-default bg-surface p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold text-content-primary">{fact.fact_type.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())}</p><p className="mt-1 text-sm text-content-muted">{fact.source_label}</p></div><span className="rounded-full bg-state-success/15 px-2 py-1 text-xs font-semibold text-state-success">Grounded</span></div><dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">{Object.entries(fact.structured_values).map(([key, value]) => <div key={key}><dt className="text-content-muted">{key.replaceAll('_', ' ')}</dt><dd className="text-content-primary">{Array.isArray(value) ? value.join(', ') : String(value)}</dd></div>)}</dl><div className="mt-3"><p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Source Evidence</p><blockquote className="mt-2 whitespace-pre-wrap rounded-control border-l-2 border-accent-border bg-elevated p-3 text-sm text-content-primary">â€œ{fact.evidence_quote}â€</blockquote></div><DisclosureSection title="Technical details" summary="Classification labels and persisted identifiers"><dl className="grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">Related classifications</dt><dd>{fact.related_labels.join(', ')}</dd></div><div><dt className="text-content-muted">Section</dt><dd>{fact.sequence}</dd></div><div><dt className="text-content-muted">Fact ID</dt><dd className="break-all">{fact.fact_id}</dd></div><div><dt className="text-content-muted">Chunk ID</dt><dd className="break-all">{fact.chunk_id}</dd></div></dl></DisclosureSection></article>)}</div> : detailStatus === 'success' ? <p className="text-sm text-content-secondary">No grounded testing facts were produced for the persisted evidence.</p> : null}
      {detailData?.has_more ? <LoadMoreButton disabled={detailStatus === 'loading-more'} onClick={onLoadMoreDetails}>{detailStatus === 'loading-more' ? 'Loadingâ€¦' : `Show more (${detailData.total - detailData.items.length} remaining)`}</LoadMoreButton> : null}
    </PresentationSection>
    <DisclosureSection title="How Agent 4 reached this result" summary="Local semantic extraction and evidence grounding"><p className="text-sm text-content-secondary">The local semantic model extracts testing facts only from effective classifications. Results are checkpointed by source and prepared section; model identifiers and grounding metadata remain backend evidence and are not fabricated here.</p></DisclosureSection>
    <NextStep>{completed ? 'Context & Testability now checks whether each selected output has enough evidence to proceed.' : failed ? 'Retry the failed source; completed work will be preserved.' : 'This view refreshes automatically while extraction runs.'}</NextStep>
  </section>
}

export default TestingFactExtractionPanel
