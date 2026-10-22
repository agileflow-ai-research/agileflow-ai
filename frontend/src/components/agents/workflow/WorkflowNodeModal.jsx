import { useEffect, useRef } from 'react'

import StatusBadge from '../../ui/StatusBadge.jsx'
import { getWorkflowStatePresentation } from '../workflowState.js'

function WorkflowNodeModal({
  node,
  open,
  onClose,
  children,
  footer,
  eyebrow = 'Workflow',
}) {
  const closeRef = useRef(null)
  const dialogRef = useRef(null)
  const restoreFocusRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    restoreFocusRef.current = document.activeElement
    closeRef.current?.focus()
    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose()
      if (event.key === 'Tab') {
        const focusable = [...(dialogRef.current?.querySelectorAll(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
        ) ?? [])]
        if (!focusable.length) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      restoreFocusRef.current?.focus?.()
    }
  }, [open, onClose])

  const status = getWorkflowStatePresentation(node?.status)
  const titleId = `workflow-modal-${node?.id ?? 'details'}-title`

  return (
    <div hidden={!open} aria-hidden={!open || undefined} className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-2 sm:p-5" data-testid="workflow-modal-backdrop">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[calc(100dvh-1rem)] w-full max-w-5xl flex-col overflow-hidden rounded-panel border border-default bg-sidebar shadow-surface sm:max-h-[calc(100dvh-2rem)]"
      >
        <header className="sticky top-0 z-10 shrink-0 border-b border-default bg-sidebar px-4 py-3 sm:px-6 sm:py-4" data-testid="workflow-modal-header">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">{eyebrow}</p>
              <h2 id={titleId} className="mt-1 text-section-heading font-semibold text-content-primary">{node?.title}</h2>
              {node?.purpose ? <p className="mt-2 max-w-3xl text-sm text-content-secondary">{node.purpose}</p> : null}
              <div className="mt-2"><StatusBadge label={node?.statusLabel ?? status.label} tone={status.tone} /></div>
            </div>
            <button ref={closeRef} type="button" className="rounded-control px-3 py-2 text-sm font-semibold text-content-secondary hover:bg-elevated hover:text-content-primary" aria-label="Close workflow modal" onClick={onClose}>Close</button>
          </div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5 sm:px-6" data-testid="workflow-modal-body">
          {children}
        </div>
        <footer className="sticky bottom-0 z-10 shrink-0 border-t border-default bg-sidebar px-4 py-3 sm:px-6" data-testid="workflow-modal-footer">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-content-muted">Closing this window does not change workflow state.</p>
            {footer ?? <button type="button" className="rounded-control px-3 py-2 text-sm font-semibold text-content-secondary hover:bg-elevated" onClick={onClose}>Close</button>}
          </div>
        </footer>
      </section>
    </div>
  )
}

export default WorkflowNodeModal
