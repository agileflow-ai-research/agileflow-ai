import Card from '../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'

function LockedNodeState({ node }) {
  return (
    <Card variant="elevated" className="space-y-3" role="status">
      <StatusBadge label="Locked" tone="neutral" />
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Future Agent 1 node</p>
        <h3 className="mt-1 text-card-heading font-semibold text-content-primary">{node.title}</h3>
        <p className="mt-2 text-sm text-content-secondary">
          This node becomes available after multimodal evidence processing and chunk preparation are complete and its backend stage is implemented.
        </p>
      </div>
    </Card>
  )
}

export default LockedNodeState
