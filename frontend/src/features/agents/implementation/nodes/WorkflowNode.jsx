import { Handle, Position } from '@xyflow/react'

import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { cn } from '../../../../utils/cn.js'
import { getWorkflowStatePresentation } from '../constants/workflow.js'

function WorkflowNode({ data, selected }) {
  const status = getWorkflowStatePresentation(data.status)
  return (
    <div
      className={cn(
        'implementation-workflow-node w-60 rounded-card border bg-surface shadow-surface transition-colors',
        `implementation-workflow-node--${status.visual}`,
        selected && 'implementation-workflow-node--selected',
        data.locked && 'opacity-75',
      )}
      data-workflow-status={data.status}
      data-workflow-visual={status.visual}
      data-selected={selected ? 'true' : 'false'}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} className="!h-2 !w-2 !border-default !bg-content-muted" />
      <button
        type="button"
        className="nodrag w-full rounded-card p-4 text-left"
        aria-label={`Open ${data.title}`}
        onClick={data.onOpen}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-semibold text-content-primary">{data.title}</h3>
          {data.attentionCount ? <span className="rounded-full bg-state-warning/15 px-2 py-0.5 text-xs font-semibold text-state-warning">{data.attentionCount}</span> : null}
        </div>
        <div className="mt-3"><StatusBadge label={data.statusLabel ?? status.label} tone={status.tone} /></div>
        <p className="mt-3 text-xs leading-5 text-content-secondary">{data.summary}</p>
        {data.locked ? <p className="mt-2 text-xs font-semibold text-content-muted">Not implemented yet</p> : null}
      </button>
      <Handle type="source" position={Position.Right} isConnectable={false} className="!h-2 !w-2 !border-default !bg-content-muted" />
    </div>
  )
}

export default WorkflowNode
