import { Handle, Position } from '@xyflow/react'

import StatusBadge from '../../ui/StatusBadge.jsx'
import { cn } from '../../../utils/cn.js'
import { getWorkflowStatePresentation } from '../workflowState.js'

function WorkflowNode({ data, selected }) {
  const status = getWorkflowStatePresentation(data.status)
  const summary = data.summary ?? data.subtitle
  return (
    <div
      className={cn(
        'workflow-node w-60 rounded-card border bg-surface shadow-surface transition-colors',
        `workflow-node--${status.visual}`,
        selected && 'workflow-node--selected',
        data.locked && 'opacity-75',
      )}
      data-workflow-status={data.status}
      data-workflow-visual={status.visual}
      data-selected={selected ? 'true' : 'false'}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} className="pointer-events-none !h-px !min-h-0 !w-px !min-w-0 !border-0 !bg-transparent opacity-0" />
      <button
        type="button"
        className="w-full cursor-grab rounded-card p-4 text-left active:cursor-grabbing"
        aria-label={`Open ${data.title}`}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-semibold text-content-primary">{data.title}</h3>
          {data.attentionCount ? <span className="rounded-full bg-state-warning/15 px-2 py-0.5 text-xs font-semibold text-state-warning">{data.attentionCount}</span> : null}
        </div>
        <div className="mt-3"><StatusBadge label={data.statusLabel ?? status.label} tone={status.tone} /></div>
        {summary ? <p className="mt-3 text-xs leading-5 text-content-secondary">{summary}</p> : null}
        {data.locked ? <p className="mt-2 text-xs font-semibold text-content-muted">{data.lockedNote ?? 'Not implemented yet'}</p> : null}
      </button>
      <Handle type="source" position={Position.Right} isConnectable={false} className="pointer-events-none !h-px !min-h-0 !w-px !min-w-0 !border-0 !bg-transparent opacity-0" />
    </div>
  )
}

export default WorkflowNode
