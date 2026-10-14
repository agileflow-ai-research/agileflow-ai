import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import { formatDateTime } from '../../utils/dateTime.js'
import {
  getAgentRunModePresentation,
  getAgentRunStatusPresentation,
} from '../../utils/agentPresentation.js'

function Timestamp({ label, value }) {
  const formatted = formatDateTime(value)
  if (!formatted) return null
  return <span>{label}: {formatted}</span>
}

function RunHistory({ runs = [], onViewRun }) {
  if (runs.length === 0) {
    return <p className="rounded-card border border-dashed border-default p-card text-body-copy text-content-secondary">No runs yet.</p>
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => {
        const status = getAgentRunStatusPresentation(run.status)
        const mode = getAgentRunModePresentation(run.run_mode)
        const outputs = Array.isArray(run.selected_outputs) ? run.selected_outputs : []

        return (
          <Card key={run.run_id}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="break-all font-mono text-sm font-semibold text-content-primary">{run.run_id}</p>
                <p className="mt-1 text-sm text-content-secondary">{mode.label}</p>
              </div>
              <StatusBadge label={status.label} tone={status.tone} />
            </div>

            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Selected outputs</p>
              <p className="mt-1 break-words text-sm text-content-secondary">
                {outputs.length > 0 ? outputs.join(', ') : 'None recorded'}
              </p>
            </div>

            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-content-muted">
              <Timestamp label="Created" value={run.created_at} />
              <Timestamp label="Started" value={run.started_at} />
              <Timestamp label="Completed" value={run.completed_at} />
            </div>

            {onViewRun && (
              <Button
                className="mt-4"
                variant="outline"
                size="small"
                onClick={() => onViewRun(run.run_id)}
                aria-label={`View details for run ${run.run_id}`}
              >
                View Details
              </Button>
            )}
          </Card>
        )
      })}
    </div>
  )
}

export default RunHistory
