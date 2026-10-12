import { formatDateTime } from '../../utils/dateTime.js'
import { formatEnumLabel } from '../../utils/workflowPresentation.js'
import EmptyState from '../feedback/EmptyState.jsx'
import Card from '../ui/Card.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'

function WorkflowEventList({ events }) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No workflow activity yet"
        description="Workflow events will appear here after the Orchestrator records them."
      />
    )
  }

  return (
    <ol className="space-y-3" aria-label="Workflow events">
      {events.map((event) => {
        const createdAt = formatDateTime(event.created_at)
        const hasStageChange = event.stage_before || event.stage_after

        return (
          <li key={event.event_id}>
            <Card className="overflow-hidden">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge label={formatEnumLabel(event.event_type)} />
                    <span className="text-helper-copy text-content-muted">
                      {event.event_id}
                    </span>
                  </div>
                  <p className="mt-3 break-words text-body-copy text-content-primary">
                    {event.message}
                  </p>
                  <p className="mt-2 break-words text-sm text-content-secondary">
                    {event.source_component}
                    {event.target_component ? ` → ${event.target_component}` : ''}
                  </p>
                  {hasStageChange ? (
                    <p className="mt-1 break-words text-helper-copy text-content-muted">
                      {formatEnumLabel(event.stage_before, 'No prior stage')} →{' '}
                      {formatEnumLabel(event.stage_after, 'No resulting stage')}
                    </p>
                  ) : null}
                </div>
                {createdAt ? (
                  <time
                    className="shrink-0 text-helper-copy text-content-muted"
                    dateTime={event.created_at}
                  >
                    {createdAt}
                  </time>
                ) : null}
              </div>
            </Card>
          </li>
        )
      })}
    </ol>
  )
}

export default WorkflowEventList
