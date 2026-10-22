import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import NodeShellPanel from './NodeShellPanel.jsx'

const statusLabels = Object.freeze({
  QUEUED: 'Queued',
  RUNNING: 'Running',
  COMPLETED: 'Completed',
  EXTRACTING: 'Extracting',
  NORMALIZING: 'Normalizing',
  CHUNKING: 'Chunking',
  COMPLETE: 'Complete',
  PENDING_ANALYSIS: 'Pending Analysis',
  FAILED: 'Failed',
  INTERRUPTED: 'Interrupted',
})

function toneFor(status) {
  if (['COMPLETE', 'COMPLETED'].includes(status)) return 'success'
  if (['FAILED', 'INTERRUPTED'].includes(status)) return 'danger'
  if (status === 'PENDING_ANALYSIS') return 'warning'
  return 'info'
}

function stageText(source) {
  if (source.status === 'COMPLETE') return `${source.chunk_count} chunks prepared`
  if (source.status === 'PENDING_ANALYSIS') {
    return 'Image understanding is not implemented; no textual chunks were created.'
  }
  if (source.status === 'FAILED') {
    return source.error?.message || 'This source could not be prepared.'
  }
  if (source.status === 'EXTRACTING') return 'Extracting document text'
  if (source.status === 'NORMALIZING') return 'Creating normalized evidence'
  if (source.status === 'CHUNKING') return 'Creating deterministic chunks'
  return 'Waiting for preparation'
}

function InputPreparationPanel({
  definition,
  n2Execution,
  onRetryPreparationSource,
  preparationError,
  retryingSourceId,
  statusLabel,
  workflowNodeStatus,
}) {
  const terminal = n2Execution?.sources?.filter((source) => (
    ['COMPLETE', 'PENDING_ANALYSIS', 'FAILED'].includes(source.status)
  )).length ?? 0
  const total = n2Execution?.sources?.length ?? 0
  const note = workflowNodeStatus === 'NOT_STARTED'
    ? 'Input Preparation is the next workflow node. Existing confirmed projects start through the compatibility workflow command.'
    : workflowNodeStatus === 'LOCKED'
      ? 'No extraction, normalization, or chunking can run until Input & Output Setup is confirmed.'
    : workflowNodeStatus === 'COMPLETED'
      ? 'Input Preparation is complete. Testing Intelligence is now the next workflow node.'
      : 'Preparation runs automatically and preserves successful work when another source fails.'

  return (
    <NodeShellPanel definition={definition} availability={statusLabel} note={note}>
      {n2Execution ? (
        <section className="space-y-3" aria-label="Input preparation progress">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h4 className="font-semibold text-content-primary">Preparation attempt {n2Execution.attempt_number}</h4>
              <p className="text-sm text-content-secondary">{terminal} / {total} sources terminal · {n2Execution.total_chunks} chunks</p>
            </div>
            <StatusBadge label={statusLabels[n2Execution.status] || n2Execution.status} tone={toneFor(n2Execution.status)} />
          </div>
          {preparationError ? <p role="alert" className="text-sm text-state-danger">{preparationError}</p> : null}
          <ul className="space-y-2">
            {n2Execution.sources.map((source) => (
              <li key={source.source_id} className="rounded-control border border-default bg-surface p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-content-primary">{source.label || source.original_filename || source.artifact_type.replaceAll('_', ' ')}</p>
                    <p className="text-xs text-content-muted">{source.source_type} · {source.artifact_type.replaceAll('_', ' ')}</p>
                  </div>
                  <StatusBadge label={statusLabels[source.status] || source.status} tone={toneFor(source.status)} />
                </div>
                <p className="mt-2 text-sm text-content-secondary">{stageText(source)}</p>
                {source.warnings?.map((warning) => (
                  <p key={warning.code} className="mt-1 text-xs text-state-warning">{warning.message}</p>
                ))}
                {source.status === 'FAILED' ? (
                  <Button
                    className="mt-3"
                    variant="outline"
                    size="small"
                    loading={retryingSourceId === source.source_id}
                    loadingLabel="Retrying source"
                    disabled={Boolean(retryingSourceId)}
                    onClick={() => { void onRetryPreparationSource(source.source_id) }}
                  >
                    Retry Source
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-content-secondary">Preparation execution details will appear here when N2 is queued.</p>
      )}
    </NodeShellPanel>
  )
}

export default InputPreparationPanel
