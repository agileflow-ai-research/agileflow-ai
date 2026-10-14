import { formatDateTime } from '../../utils/dateTime.js'
import { getAgentProjectStatusPresentation } from '../../utils/agentPresentation.js'
import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'

function AgentProjectCard({ project, onOpen }) {
  const status = getAgentProjectStatusPresentation(project.status)
  const updatedAt = formatDateTime(project.updated_at)
  const description = project.description?.trim()

  return (
    <Card className="flex h-full flex-col" variant="interactive">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-helper-copy font-medium text-content-muted">
            {project.agent_project_id}
          </p>
          <h2 className="mt-1 text-card-heading font-semibold text-content-primary">
            {project.name}
          </h2>
          <p className="mt-1 text-sm text-content-secondary">{project.domain}</p>
        </div>
        <StatusBadge label={status.label} tone={status.tone} />
      </div>

      {description ? (
        <p className="mt-4 line-clamp-3 text-sm leading-relaxed text-content-secondary">
          {description}
        </p>
      ) : null}

      {updatedAt ? (
        <p className="mt-4 text-helper-copy text-content-muted">Updated {updatedAt}</p>
      ) : null}

      <div className="mt-auto pt-5">
        <Button
          variant="outline"
          size="small"
          aria-label={`Open ${project.name}`}
          onClick={() => onOpen(project.agent_project_id)}
        >
          Open Project
        </Button>
      </div>
    </Card>
  )
}

export default AgentProjectCard
