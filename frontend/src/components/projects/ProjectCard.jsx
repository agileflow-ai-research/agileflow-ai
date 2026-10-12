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
    <Card variant="interactive" className="flex h-full flex-col">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-helper-copy font-medium text-content-muted">{projectId}</p>
          <h2 className="mt-1 text-card-heading font-semibold text-content-primary">{name}</h2>
          <p className="mt-1 text-sm text-content-secondary">{domain}</p>
        </div>
        {status && (
          <StatusBadge label={formatEnumLabel(status)} tone={projectStatusTone(status)} />
        )}
      </div>

      {description && (
        <p className="mt-4 line-clamp-3 text-sm leading-relaxed text-content-secondary">
          {description}
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <WorkflowBadge stage={currentStage} />
        {formattedDate && (
          <span className="text-helper-copy text-content-muted">Updated {formattedDate}</span>
        )}
      </div>

      {onOpen && (
        <div className="mt-auto pt-5">
          <Button
            variant="outline"
            size="small"
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
