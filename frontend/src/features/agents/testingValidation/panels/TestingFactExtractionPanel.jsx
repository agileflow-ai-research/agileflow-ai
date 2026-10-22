import Button from '../../../../components/ui/Button.jsx'

function TestingFactExtractionPanel({ definition, intelligenceError, n3Execution, onRetryIntelligenceSource, retryingIntelligenceSourceId, workflowNodeStatus }) {
  const factStage = n3Execution?.sub_stages?.find((stage) => stage.stage === 'TI_FACT_EXTRACTION')
  const sources = n3Execution?.sources || []
  const completedChunks = sources.reduce((count, source) => count + (source.fact_extraction_chunks?.length || 0), 0)
  const facts = sources.reduce((count, source) => count + (source.semantic_fact_count || 0), 0)
  const queued = workflowNodeStatus === 'QUEUED' || factStage?.status === 'QUEUED'
  const running = workflowNodeStatus === 'RUNNING' || factStage?.status === 'RUNNING'
  const completed = workflowNodeStatus === 'COMPLETED'
  const failed = workflowNodeStatus === 'FAILED'

  return <section className="space-y-4" aria-label={`${definition.title} details`}>
    {intelligenceError ? <p role="alert" className="text-sm text-state-danger">{intelligenceError}</p> : null}
    {completed ? <div role="status" className="rounded-control border border-state-success/40 bg-state-success/10 p-4"><p className="font-semibold text-state-success">✓ Testing Fact Extraction complete</p><p className="mt-1 text-sm text-content-secondary">{facts} grounded facts extracted from {completedChunks} processed chunks. Context &amp; Testability is ready.</p></div> : null}
    {queued && !completed ? <div role="status" className="rounded-control border border-default bg-surface p-4"><p className="font-semibold text-content-primary">Waiting for extraction capacity</p><p className="mt-1 text-sm text-content-secondary">Approved classifications are saved. This project will start when the local semantic model is available.</p></div> : null}
    {running && !queued && !completed ? <div role="status" className="rounded-control border border-default bg-surface p-4"><p className="font-semibold text-content-primary">Testing fact extraction in progress</p><p className="mt-1 text-sm text-content-secondary">The local semantic model is extracting evidence-grounded facts. Completed chunk results are checkpointed.</p></div> : null}
    {failed ? <div role="alert" className="rounded-control border border-state-danger/40 p-4"><p className="font-semibold text-state-danger">Testing fact extraction failed — retry available</p><p className="mt-1 text-sm text-content-secondary">Completed source and chunk results are preserved.</p></div> : null}
    {sources.length ? <div className="space-y-2">{sources.map((source) => {
      const stage = source.sub_stages?.find((item) => item.stage === 'TI_FACT_EXTRACTION')
      const sourceFailed = ['FAILED', 'INTERRUPTED'].includes(stage?.status)
      const processed = source.fact_extraction_chunks?.length || 0
      return <article key={source.source_id} className="rounded-control border border-default bg-surface p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium text-content-primary">{source.label || source.original_filename || source.source_id}</p><span className={sourceFailed ? 'text-state-danger' : ['COMPLETED', 'NOT_APPLICABLE'].includes(stage?.status) ? 'text-state-success' : 'text-content-secondary'}>{stage?.status?.replaceAll('_', ' ') || 'NOT STARTED'}</span></div><p className="mt-1 text-sm text-content-secondary">{processed} chunks checkpointed · {source.semantic_fact_count || 0} facts</p>{sourceFailed ? <div className="mt-2"><p className="text-sm text-state-danger">{stage?.safe_error?.message || source.error?.message || 'Fact extraction could not complete.'}</p>{source.retryable !== false ? <Button className="mt-2" size="small" variant="outline" loading={retryingIntelligenceSourceId === source.source_id} disabled={Boolean(retryingIntelligenceSourceId)} onClick={() => { void onRetryIntelligenceSource(source.source_id) }}>Retry incomplete extraction</Button> : null}</div> : null}</article>
    })}</div> : <p className="text-sm text-content-secondary">Fact extraction starts after Testing Intelligence and any required human review are complete.</p>}
  </section>
}

export default TestingFactExtractionPanel
