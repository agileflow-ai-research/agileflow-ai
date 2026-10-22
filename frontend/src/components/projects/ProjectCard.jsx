import { formatEnumLabel, projectStatusTone } from '../../utils/workflowPresentation.js'
import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import WorkflowBadge from '../ui/WorkflowBadge.jsx'

function formatUpdatedAt(value) {
  if (!value) {
    return null
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

function ProjectCard({
  projectId,
  name,
  domain,
  description,
  currentStage,
  status,
  updatedAt,
  onOpen,
}) {
  const formattedDate = formatUpdatedAt(updatedAt)

  return (
    <Card variant="interactive" className="group relative flex h-full min-h-64 flex-col overflow-hidden shadow-surface">
      <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-highlight/60 to-transparent opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[0.6875rem] font-semibold uppercase tracking-[0.12em] text-content-muted">{projectId}</p>
          <h2 className="mt-2 text-card-heading font-semibold leading-snug tracking-tight text-content-primary">{name}</h2>
          <p className="mt-1.5 flex items-center gap-2 text-sm text-content-secondary"><span className="h-1 w-1 rounded-full bg-highlight" aria-hidden="true" />{domain}</p>
        </div>
        {status && (
          <StatusBadge label={formatEnumLabel(status)} tone={projectStatusTone(status)} />
        )}
      </div>

      {description && (
        <p className="mt-4 line-clamp-3 text-sm leading-6 text-content-secondary">
          {description}
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-default/70 pt-4">
        <WorkflowBadge stage={currentStage} />
        {formattedDate && (
          <span className="text-helper-copy text-content-muted">Updated {formattedDate}</span>
        )}
      </div>

      {onOpen && (
        <div className="mt-auto flex justify-end pt-5">
          <Button
            variant="outline"
            size="small"
            className="min-w-32"
            aria-label={`Open ${name}`}
            onClick={() => onOpen(projectId)}
          >
            Open project
          </Button>
        </div>
      )}
    </Card>
  )
}

export default ProjectCard
