import Card from '../../../../components/ui/Card.jsx'
import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { getWorkflowStatePresentation } from '../../../../components/agents/workflowState.js'

function N2OrchestrationStatus({ workflowState, retrying, error, onRetry }) {
  const execution = workflowState?.n2_execution
  if (!execution) return null
  const isCurrent = workflowState?.n2_is_current !== false
  const status = isCurrent ? execution.status : 'BLOCKED'
  const presentation = getWorkflowStatePresentation(status)
  const completeCount = execution.source_progress?.filter(
    (source) => source.preparation_status === 'COMPLETE',
  ).length ?? 0
  const totalCount = execution.input_sources?.length ?? 0
  const canRetry = isCurrent
    && execution.retryable
    && ['FAILED', 'BLOCKED'].includes(execution.status)

  return (
    <Card variant="elevated" className="space-y-4" aria-label="N2 orchestration status">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-content-primary">Automatic Evidence Processing</p>
          <p className="mt-1 text-sm text-content-secondary">
            {completeCount} of {totalCount} confirmed sources prepared
          </p>
        </div>
        <StatusBadge label={presentation.label} tone={presentation.tone} />
      </div>
      {!isCurrent ? (
        <p className="text-sm text-state-warning" role="alert">
          Sources or requested outputs changed. Reconfirm Node 1 to start a current N2 execution.
        </p>
      ) : null}
      {execution.error?.message ? (
        <p className="text-sm text-state-danger" role="alert">
          {execution.error.code}: {execution.error.message}
        </p>
      ) : null}
      {error ? <p className="text-sm text-state-danger" role="alert">{error}</p> : null}
      <ol className="grid gap-2 sm:grid-cols-2">
        {(execution.source_progress ?? []).map((source) => (
          <li key={source.source_id} className="rounded-control border border-default bg-surface p-3 text-sm">
            <p className="font-semibold text-content-primary">{source.source_id}</p>
            <p className="mt-1 text-content-secondary">
              Processing: {source.processing_status} · Preparation: {source.preparation_status}
              {source.chunk_count ? ` · ${source.chunk_count} chunks` : ''}
            </p>
          </li>
        ))}
      </ol>
      {canRetry ? (
        <Button loading={retrying} loadingLabel="Retrying N2" onClick={() => { void onRetry() }}>
          Retry N2
        </Button>
      ) : null}
    </Card>
  )
}

export default N2OrchestrationStatus
