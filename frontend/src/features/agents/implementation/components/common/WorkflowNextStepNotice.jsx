import Button from '../../../../../components/ui/Button.jsx'

export default function WorkflowNextStepNotice({ title = 'Next step', description, actionLabel, targetNodeId, onNavigate }) {
  if (!description || !targetNodeId || !onNavigate) return null
  return (
    <aside className="mb-5 rounded-control border border-accent-border/50 bg-brand-soft/30 p-4" aria-label="Workflow next step">
      <p className="text-xs font-semibold uppercase tracking-wider text-highlight">{title}</p>
      <p className="mt-2 text-sm text-content-secondary">{description}</p>
      <Button className="mt-3" variant="outline" size="small" onClick={() => onNavigate(targetNodeId)}>
        {actionLabel}
      </Button>
    </aside>
  )
}
