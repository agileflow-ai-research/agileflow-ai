import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { getWorkflowStatePresentation } from '../constants/workflow.js'

function WorkflowNodePanel({ node, open, onClose, children }) {
  const status = getWorkflowStatePresentation(node?.status)
  return (
    <aside
      className={open ? 'fixed inset-y-0 right-0 z-20 w-full overflow-y-auto border-l border-default bg-sidebar p-5 shadow-surface sm:w-[min(46rem,92vw)] lg:static lg:z-auto lg:w-[34rem] lg:shrink-0' : 'hidden'}
      aria-label="Workflow node details"
    >
      <div className="flex items-start justify-between gap-4 border-b border-default pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">Agent 3 workflow</p>
          <h2 className="mt-1 text-section-heading font-semibold text-content-primary">{node?.title}</h2>
          <div className="mt-2"><StatusBadge label={status.label} tone={status.tone} /></div>
        </div>
        <button type="button" className="rounded-control px-3 py-2 text-sm font-semibold text-content-secondary hover:bg-elevated hover:text-content-primary" aria-label="Close workflow details" onClick={onClose}>Close</button>
      </div>
      <div className="mt-5">{children}</div>
    </aside>
  )
}

export default WorkflowNodePanel
