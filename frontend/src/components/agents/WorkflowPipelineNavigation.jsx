import StatusBadge from '../ui/StatusBadge.jsx'
import { cn } from '../../utils/cn.js'
import { getWorkflowStatePresentation, WORKFLOW_NODE_STATES } from './workflowState.js'

function WorkflowPipelineNavigation({ nodes, activeNodeId, currentNodeId, onSelect }) {
  return (
    <nav aria-label="Agent 1 pipeline" className="overflow-x-auto pb-2">
      <ol className="grid min-w-[70rem] grid-cols-7 gap-3 lg:min-w-0">
        {nodes.map((node, index) => {
          const statePresentation = getWorkflowStatePresentation(node.state)
          const locked = node.state === WORKFLOW_NODE_STATES.LOCKED
          const selected = node.id === activeNodeId
          const current = node.id === currentNodeId
          return (
            <li key={node.id}>
              <button
                type="button"
                aria-disabled={locked || undefined}
                aria-current={current ? 'step' : undefined}
                aria-pressed={selected}
                onClick={() => onSelect(node.id)}
                className={cn(
                  'flex h-full min-h-32 w-full flex-col items-start rounded-card border p-4 text-left transition-colors',
                  selected
                    ? 'border-accent-border bg-brand-soft shadow-brand-glow'
                    : 'border-default bg-surface hover:border-accent-border hover:bg-elevated',
                  locked && 'cursor-not-allowed opacity-65 hover:border-default hover:bg-surface',
                )}
              >
                <span className="text-xs font-semibold uppercase tracking-wide text-content-muted">
                  N{index + 1}{current ? ' · Current' : ''}
                </span>
                <span className="mt-2 flex-1 text-sm font-semibold text-content-primary">{node.shortTitle}</span>
                <StatusBadge className="mt-3" label={statePresentation.label} tone={statePresentation.tone} />
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export default WorkflowPipelineNavigation
