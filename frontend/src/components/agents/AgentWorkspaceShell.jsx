import Card from '../ui/Card.jsx'

function AgentWorkspaceShell({ title = 'Agent workspace', description, children }) {
  return (
    <section aria-labelledby="agent-workspace-heading">
      <Card>
        <h2
          id="agent-workspace-heading"
          className="text-section-heading font-semibold text-content-primary"
        >
          {title}
        </h2>
        {description ? (
          <p className="mt-2 text-sm text-content-secondary">{description}</p>
        ) : null}
        <div className="mt-5 rounded-control border border-dashed border-default bg-elevated p-5">
          {children ?? (
            <p className="text-sm text-content-secondary">
              Agent-specific input and execution controls will appear here.
            </p>
          )}
        </div>
      </Card>
    </section>
  )
}

export default AgentWorkspaceShell
