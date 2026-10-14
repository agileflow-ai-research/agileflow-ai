import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'

function AgentCard({ agent, onViewProjects, onCreateProject }) {
  return (
    <Card className="flex h-full flex-col" variant="interactive">
      <div>
        <p className="text-helper-copy font-semibold uppercase tracking-wider text-highlight">
          Standalone workspace
        </p>
        <h2 className="mt-2 text-card-heading font-semibold text-content-primary">
          {agent.label}
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-content-secondary">
          {agent.description}
        </p>
        <p className="mt-3 text-helper-copy text-content-muted">
          Workspace foundation ready; execution is added in the specialist phase.
        </p>
      </div>
      <div className="mt-auto flex flex-col gap-2 pt-6 sm:flex-row">
        <Button
          className="flex-1"
          variant="outline"
          aria-label={`View ${agent.label} projects`}
          onClick={onViewProjects}
        >
          View Projects
        </Button>
        <Button
          className="flex-1"
          aria-label={`Create ${agent.label} project`}
          onClick={onCreateProject}
        >
          Create Project
        </Button>
      </div>
    </Card>
  )
}

export default AgentCard
