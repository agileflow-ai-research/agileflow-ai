import { useEffect, useState } from 'react'

import ArtifactViewer from './ArtifactViewer.jsx'
import RequirementsResults from './RequirementsResults.jsx'
import ErrorState from '../feedback/ErrorState.jsx'
import LoadingState from '../feedback/LoadingState.jsx'
import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import { getAgentProjectRun } from '../../services/agentProjectService.js'
import { formatDateTime } from '../../utils/dateTime.js'
import {
  getAgentRunModePresentation,
  getAgentRunStatusPresentation,
} from '../../utils/agentPresentation.js'

function RunMessageList({ title, messages, tone }) {
  if (!Array.isArray(messages) || messages.length === 0) return null

  return (
    <Card className={tone === 'danger' ? 'border-state-danger/40 bg-state-danger/10' : 'border-state-warning/40 bg-state-warning/10'}>
      <h3 className="font-semibold text-content-primary">{title}</h3>
      <ul className="mt-3 space-y-3">
        {messages.map((item, index) => (
          <li key={`${item?.code ?? 'message'}-${index}`}>
            <p className="font-medium text-content-primary">{item?.message ?? 'No message provided'}</p>
            {item?.code && <p className="mt-1 font-mono text-xs text-content-muted">{item.code}</p>}
            {item?.details && (
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-control bg-canvas p-3 text-xs text-content-secondary">
                {JSON.stringify(item.details, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function RunDetail({ agentProjectId, runId, onClose }) {
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    let active = true

    getAgentProjectRun(agentProjectId, runId)
      .then((response) => {
        if (active) setRun(response?.data ?? null)
      })
      .catch((requestError) => {
        if (active && requestError?.status !== 401) setError(requestError)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => { active = false }
  }, [agentProjectId, runId, retryKey])

  function handleRetry() {
    setLoading(true)
    setError(null)
    setRetryKey((value) => value + 1)
  }

  if (loading) return <LoadingState message="Loading run details" />

  if (error || !run) {
    return (
      <ErrorState
        title={error?.status === 404 ? 'Run not found' : 'Unable to load run details'}
        message={error?.status === 404 ? 'This run is unavailable or does not belong to this project.' : 'Run details could not be loaded. Please try again.'}
        onRetry={error?.status === 404 ? undefined : handleRetry}
      />
    )
  }

  const status = getAgentRunStatusPresentation(run.status)
  const mode = getAgentRunModePresentation(run.run_mode)
  const outputs = Array.isArray(run.selected_outputs) ? run.selected_outputs : []
  const manifest = run.output_manifest && typeof run.output_manifest === 'object' ? run.output_manifest : {}

  return (
    <section aria-labelledby="run-detail-title" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="run-detail-title" className="text-section-heading font-semibold text-content-primary">Run details</h2>
          <p className="mt-1 break-all font-mono text-sm text-content-secondary">{run.run_id}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge label={status.label} tone={status.tone} />
          {onClose && <Button variant="ghost" size="small" onClick={onClose}>Close</Button>}
        </div>
      </div>

      <Card>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div><dt className="text-content-muted">Mode</dt><dd className="mt-1 text-content-primary">{mode.label}</dd></div>
          <div><dt className="text-content-muted">Selected outputs</dt><dd className="mt-1 break-words text-content-primary">{outputs.length > 0 ? outputs.join(', ') : 'None recorded'}</dd></div>
          <div><dt className="text-content-muted">Created</dt><dd className="mt-1 text-content-primary">{formatDateTime(run.created_at) ?? 'Not recorded'}</dd></div>
          <div><dt className="text-content-muted">Started</dt><dd className="mt-1 text-content-primary">{formatDateTime(run.started_at) ?? 'Not started'}</dd></div>
          <div><dt className="text-content-muted">Completed</dt><dd className="mt-1 text-content-primary">{formatDateTime(run.completed_at) ?? 'Not completed'}</dd></div>
        </dl>
      </Card>

      <RunMessageList title="Warnings" messages={run.warnings} tone="warning" />
      <RunMessageList title="Errors" messages={run.errors} tone="danger" />

      {run.agent_type === 'REQUIREMENTS' ? (
        <RequirementsResults outputs={manifest} title="Persisted requirements outputs" />
      ) : (
        <ArtifactViewer heading="Output manifest" metadata="Persisted manifest metadata">
          {Object.keys(manifest).length > 0 ? (
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-control bg-canvas p-3 text-xs">
              {JSON.stringify(manifest, null, 2)}
            </pre>
          ) : (
            <p>No output manifest entries recorded.</p>
          )}
        </ArtifactViewer>
      )}
    </section>
  )
}

export default RunDetail
