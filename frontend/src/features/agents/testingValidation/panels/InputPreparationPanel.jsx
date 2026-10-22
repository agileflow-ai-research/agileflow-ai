import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { sanitizeDisplayText } from '../displayText.js'
import NodeShellPanel from './NodeShellPanel.jsx'
import { AttentionPanel, DetailLoadState, DisclosureSection, LoadMoreButton, PresentationSection, ResultBanner } from './NodePresentation.jsx'

const statusPresentation = Object.freeze({
  QUEUED: ['Preparing to start', 'neutral'], RUNNING: ['In progress', 'info'], COMPLETED: ['Complete', 'success'],
  EXTRACTING: ['Reading document', 'info'], NORMALIZING: ['Preparing content', 'info'], CHUNKING: ['Organizing information for analysis', 'info'],
  COMPLETE: ['Ready', 'success'], PENDING_ANALYSIS: ['Awaiting image analysis', 'warning'], FAILED: ['Could not be prepared', 'danger'],
  INTERRUPTED: ['Interrupted — retry available', 'danger'],
})

function sourceMessage(source) {
  if (source.status === 'COMPLETE') return 'Ready for Testing Intelligence.'
  if (source.status === 'PENDING_ANALYSIS') return 'Image understanding is not implemented in PP1, so this image produced no text for analysis.'
  if (source.status === 'FAILED') return source.error?.message || 'This source could not be prepared.'
  return statusPresentation[source.status]?.[0] || 'Waiting for preparation'
}

function InputPreparationPanel({ definition, detailData, detailError, detailStatus, n2Execution, onLoadMoreDetails, onRetryDetails, onRetryPreparationSource, preparationError, retryingSourceId, statusLabel, workflowNodeStatus }) {
  const sources = n2Execution?.sources || []
  const ready = sources.filter((source) => source.status === 'COMPLETE').length
  const images = sources.filter((source) => source.status === 'PENDING_ANALYSIS').length
  const failed = sources.filter((source) => ['FAILED', 'INTERRUPTED'].includes(source.status)).length
  const preparing = Math.max(0, sources.length - ready - images - failed)
  const complete = workflowNodeStatus === 'COMPLETED'
  const next = complete ? 'Testing Intelligence will analyze the prepared evidence next.' : workflowNodeStatus === 'LOCKED' ? 'Confirm Input & Output Setup to begin preparation.' : 'Preparation runs automatically; this view refreshes as each source becomes ready.'

  return <NodeShellPanel definition={definition} availability={statusLabel} note={next}>
    {preparationError ? <p role="alert" className="text-sm text-state-danger">{sanitizeDisplayText(preparationError)}</p> : null}
    {n2Execution ? <>
      <PresentationSection label="Result" title="Source readiness"><ResultBanner tone={failed ? 'danger' : images ? 'warning' : complete ? 'success' : 'info'} title={complete ? 'Inputs are ready for analysis' : failed ? 'Some inputs need attention' : 'Preparing your inputs'} description="Agent 4 reads each source and prepares consistent evidence for later analysis." metrics={[{ label: 'Ready', value: ready }, { label: 'Preparing', value: preparing }, { label: 'Images awaiting analysis', value: images }, { label: 'Could not prepare', value: failed }]} /></PresentationSection>
      {images ? <AttentionPanel title="Image analysis limitation"><p>{images} image source{images === 1 ? ' is' : 's are'} preserved, but image understanding is not implemented in PP1.</p></AttentionPanel> : null}
      <PresentationSection label="What Agent 4 received" title={`${sources.length} confirmed source${sources.length === 1 ? '' : 's'}`}>
        <ul className="space-y-2">{sources.map((source) => {
          const [label, tone] = statusPresentation[source.status] || [source.status, 'neutral']
          const sourceFailed = ['FAILED', 'INTERRUPTED'].includes(source.status)
          return <li key={source.source_id} className="rounded-control border border-default bg-surface p-3">
            <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium text-content-primary">{sanitizeDisplayText(source.label || source.original_filename || source.artifact_type.replaceAll('_', ' '))}</p><p className="mt-1 text-sm text-content-secondary">{sanitizeDisplayText(sourceMessage(source))}</p></div><StatusBadge label={label} tone={tone} /></div>
            {source.warnings?.map((warning) => <p key={warning.code} className="mt-2 text-sm text-state-warning">{sanitizeDisplayText(warning.message)}</p>)}
            {sourceFailed && source.retryable !== false ? <Button className="mt-3" variant="outline" size="small" loading={retryingSourceId === source.source_id} loadingLabel="Retrying source" disabled={Boolean(retryingSourceId)} onClick={() => { void onRetryPreparationSource(source.source_id) }}>Retry source</Button> : null}
            <div className="mt-3"><DisclosureSection title="Technical details" summary="Extraction status, chunks, and source identifier"><dl className="grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">Artifact type</dt><dd className="text-content-secondary">{source.artifact_type.replaceAll('_', ' ')}</dd></div><div><dt className="text-content-muted">Prepared chunks</dt><dd className="text-content-secondary">{source.chunk_count || 0}</dd></div><div><dt className="text-content-muted">Internal status</dt><dd className="text-content-secondary">{source.status}</dd></div><div><dt className="text-content-muted">Source ID</dt><dd className="break-all text-content-secondary">{source.source_id}</dd></div></dl></DisclosureSection></div>
          </li>
        })}</ul>
      </PresentationSection>
      <PresentationSection label="View prepared output" title={`Prepared Sections${detailData ? ` (${detailData.total})` : ''}`} description="These are the real persisted sections Agent 4 created for analysis.">
        <DetailLoadState error={detailError} onRetry={onRetryDetails} status={detailStatus} />
        {detailData?.items?.length ? <div className="space-y-2">{detailData.items.map((section) => <DisclosureSection key={section.chunk_id} title={`${sanitizeDisplayText(section.source_label)} - Section ${section.sequence} of ${section.section_count}`} summary={sanitizeDisplayText(section.heading_path.length ? section.heading_path.join(' / ') : section.artifact_type.replaceAll('_', ' '))}><blockquote className="whitespace-pre-wrap rounded-control bg-elevated p-3 text-sm leading-6 text-content-primary">{sanitizeDisplayText(section.text)}</blockquote><dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">Structure</dt><dd>{sanitizeDisplayText(section.structure_type)}</dd></div><div><dt className="text-content-muted">Tokens</dt><dd>{section.token_count}</dd></div><div className="sm:col-span-2"><dt className="text-content-muted">Chunk ID</dt><dd className="break-all">{sanitizeDisplayText(section.chunk_id)}</dd></div></dl></DisclosureSection>)}</div> : detailStatus === 'success' ? <p className="text-sm text-content-secondary">No persisted text sections are available. Image-only sources do not create sections in PP1.</p> : null}
        {detailData?.has_more ? <LoadMoreButton disabled={detailStatus === 'loading-more'} onClick={onLoadMoreDetails}>{detailStatus === 'loading-more' ? 'Loading...' : `Show more (${detailData.total - detailData.items.length} remaining)`}</LoadMoreButton> : null}
      </PresentationSection>
      <DisclosureSection title="Technical details" summary="Execution attempt and prepared chunk total"><dl className="grid gap-2 text-sm sm:grid-cols-3"><div><dt className="text-content-muted">Attempt</dt><dd className="text-content-secondary">{n2Execution.attempt_number}</dd></div><div><dt className="text-content-muted">Internal status</dt><dd className="text-content-secondary">{n2Execution.status}</dd></div><div><dt className="text-content-muted">Total chunks</dt><dd className="text-content-secondary">{n2Execution.total_chunks}</dd></div></dl></DisclosureSection>
    </> : <ResultBanner title="Waiting for preparation to start" description="Confirmed inputs are ready. Execution details will appear when preparation is queued." />}
  </NodeShellPanel>
}

export default InputPreparationPanel
