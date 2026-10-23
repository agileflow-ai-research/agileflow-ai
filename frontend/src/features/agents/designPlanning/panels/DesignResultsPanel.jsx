import { useMemo } from 'react'

import DesignArtifacts from '../../../../components/agents/agent-2/results/DesignArtifacts.jsx'
import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export default function DesignResultsPanel({
  project,
  activeRun,
  run,
  outputs = {},
  runs = [],
  onSelectRun,
  onNavigate,
}) {
  const effectiveActiveRun = activeRun || run
  const safeOutputs = useMemo(() => {
    return outputs && typeof outputs === 'object' && Object.keys(outputs).length > 0
      ? outputs
      : (effectiveActiveRun?.output_manifest || effectiveActiveRun?.outputs || {})
  }, [outputs, effectiveActiveRun])

  const arch = safeOutputs.SYSTEM_ARCHITECTURE
  const uml = safeOutputs.UML_DIAGRAMS
  const db = safeOutputs.DATABASE_SCHEMA
  const api = safeOutputs.API_SPECIFICATION
  const wireframes = safeOutputs.WIREFRAMES
  const uiFlow = safeOutputs.UI_FLOW

  const hasDesignOutputs = Boolean(arch || uml || db || api || wireframes || uiFlow)

  const selectedOutputsList = useMemo(() => {
    if (Array.isArray(effectiveActiveRun?.selected_outputs)) {
      return effectiveActiveRun.selected_outputs
    }
    return Object.keys(safeOutputs)
  }, [effectiveActiveRun, safeOutputs])

  const effectiveStatus = effectiveActiveRun?.status || (effectiveActiveRun ? 'COMPLETED' : 'IDLE')
  const isFailed = effectiveStatus === 'FAILED'

  if (!effectiveActiveRun && runs.length === 0) {
    return (
      <div className="space-y-6" data-testid="agent2-panel-DESIGN_RESULTS">
        <div className="rounded-panel border border-default bg-surface p-6 text-center space-y-3">
          <h2 className="text-card-heading font-semibold text-content-primary">
            No design results recorded yet
          </h2>
          <p className="text-sm text-content-secondary max-w-lg mx-auto">
            Generate Agent 2 deliverables in Node 5 to review system architecture, UML diagrams, database schema, and UI flows.
          </p>
          {onNavigate && (
            <div className="pt-2">
              <Button
                variant="primary"
                size="small"
                onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)}
              >
                Go to Node 5 — Generate Design &amp; Planning
              </Button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6" data-testid="agent2-panel-DESIGN_RESULTS">
      {/* Top Header bar with run info and switcher */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-page-heading font-semibold tracking-tight text-content-primary">
              Design Results
            </h2>
            {effectiveActiveRun?.run_id && (
              <span className="font-mono text-xs font-semibold px-2.5 py-0.5 rounded-control border border-default bg-elevated text-content-primary">
                {effectiveActiveRun.run_id}
              </span>
            )}
            <StatusBadge
              label={isFailed ? 'FAILED' : 'COMPLETED'}
              tone={isFailed ? 'danger' : 'success'}
            />
          </div>
          <p className="mt-1 text-sm text-content-muted">
            Structured architecture, UML, database, and API specifications
          </p>
        </div>

        {runs.length > 1 && onSelectRun && (
          <div className="flex items-center gap-2 text-xs">
            <label htmlFor="design-results-run-select" className="text-content-muted font-medium">
              Run:
            </label>
            <select
              id="design-results-run-select"
              aria-label="Select run to display"
              value={effectiveActiveRun?.run_id || ''}
              onChange={(e) => onSelectRun(e.target.value)}
              className="rounded-control border border-default bg-elevated px-2.5 py-1 text-xs text-content-primary font-mono focus:border-brand focus:outline-none"
            >
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.status || 'COMPLETED'})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* When no design deliverables were selected for this run (e.g. RUN-014 planning-only run) */}
      {!hasDesignOutputs ? (
        <div className="space-y-6">
          <div className="rounded-panel border border-default bg-surface p-6 space-y-4">
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-content-primary">
                No technical design deliverables selected for this run
              </h3>
              <p className="text-sm text-content-secondary">
                Run <strong className="font-mono">{effectiveActiveRun?.run_id || 'active'}</strong> was executed with agile planning deliverables only. Technical design outputs (Architecture, UML Diagrams, Database Schema, API Specification, Wireframes, UI Flow) were not requested in Node 2.
              </p>
            </div>

            {selectedOutputsList.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-default/60">
                <span className="text-xs font-medium uppercase tracking-wider text-content-muted">
                  Persisted deliverables in this run ({selectedOutputsList.length}):
                </span>
                <div className="flex flex-wrap gap-2">
                  {selectedOutputsList.map((outputKey) => (
                    <span
                      key={outputKey}
                      className="inline-flex items-center rounded-control border border-default bg-elevated px-2.5 py-1 text-xs font-mono text-content-secondary"
                    >
                      {outputKey}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {onNavigate && (
              <div className="flex flex-wrap items-center gap-3 pt-3">
                <Button
                  variant="primary"
                  size="small"
                  onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS)}
                >
                  View Planning Results (Node 7) →
                </Button>
                <Button
                  variant="outline"
                  size="small"
                  onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}
                >
                  View Validation &amp; Traceability (Node 8)
                </Button>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* When design deliverables exist */
        <DesignArtifacts
          outputs={safeOutputs}
          run={activeRun}
          status={effectiveStatus}
          project={project}
        />
      )}

      {/* Navigation footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default/60 pt-4">
        {onNavigate ? (
          <Button
            variant="outline"
            size="small"
            onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)}
          >
            ← Back to Node 5 (Generate)
          </Button>
        ) : <span />}
        {onNavigate && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="small"
              onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS)}
            >
              Go to Node 7 (Planning Results) →
            </Button>
            <Button
              variant="ghost"
              size="small"
              onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}
            >
              Node 8 (Validation)
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
