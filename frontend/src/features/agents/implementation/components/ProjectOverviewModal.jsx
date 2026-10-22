import { useEffect, useRef } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { formatDateTime } from '../../../../utils/dateTime.js'

function OverviewItem({ label, children }) {
  return (
    <div className="rounded-control border border-default bg-elevated p-3">
      <dt className="text-xs font-semibold uppercase tracking-wider text-content-muted">{label}</dt>
      <dd className="mt-1 text-sm text-content-primary">{children}</dd>
    </div>
  )
}

export default function ProjectOverviewModal({
  open,
  project,
  projectStatus,
  currentStage,
  currentStatus,
  completedNodeCount,
  totalNodeCount,
  sourceCount,
  analyzedCount,
  selectedOutputs,
  repository,
  onClose,
}) {
  const closeRef = useRef(null)
  const restoreFocusRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    restoreFocusRef.current = document.activeElement
    closeRef.current?.focus()
    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      restoreFocusRef.current?.focus?.()
    }
  }, [onClose, open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/65 p-2 sm:p-5">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-overview-title"
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-panel border border-default bg-sidebar shadow-surface sm:max-h-[85vh]"
      >
        <header className="sticky top-0 z-10 shrink-0 border-b border-default bg-sidebar px-4 py-4 sm:px-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">Agent 3 project</p>
              <h2 id="project-overview-title" className="mt-1 text-section-heading font-semibold text-content-primary">{project.name}</h2>
              <p className="mt-2 text-sm text-content-secondary">Review the current project state before entering the workflow canvas.</p>
            </div>
            <button ref={closeRef} type="button" className="rounded-control px-3 py-2 text-sm font-semibold text-content-secondary hover:bg-elevated hover:text-content-primary" aria-label="Close project overview" onClick={onClose}>Close</button>
          </div>
        </header>

        <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5 sm:px-6">
          <dl className="grid gap-3 sm:grid-cols-2">
            <OverviewItem label="Project ID">{project.agent_project_id}</OverviewItem>
            <OverviewItem label="Agent type">Agent 3 — Implementation</OverviewItem>
            {project.created_at ? <OverviewItem label="Created">{formatDateTime(project.created_at)}</OverviewItem> : null}
            <OverviewItem label="Overall status"><StatusBadge label={projectStatus.label} tone={projectStatus.tone} /></OverviewItem>
            <OverviewItem label="Current status">{currentStatus}</OverviewItem>
            <OverviewItem label="Current stage">{currentStage}</OverviewItem>
            <OverviewItem label="Workflow progress">{completedNodeCount} of {totalNodeCount} stages complete</OverviewItem>
            <OverviewItem label="Sources">{sourceCount}</OverviewItem>
            <OverviewItem label="Analyzed">{analyzedCount ?? 'Not available yet'}</OverviewItem>
            <OverviewItem label="Selected outputs">
              {selectedOutputs.length > 0 ? selectedOutputs.join(', ') : 'Not available yet'}
            </OverviewItem>
            <OverviewItem label="Repository">{repository?.full_name ?? 'Not configured'}</OverviewItem>
          </dl>
        </div>

        <footer className="sticky bottom-0 z-10 flex shrink-0 justify-end border-t border-default bg-sidebar px-4 py-3 sm:px-6">
          <Button onClick={onClose}>View Canvas</Button>
        </footer>
      </section>
    </div>
  )
}
