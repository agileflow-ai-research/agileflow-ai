import Button from '../../../ui/Button.jsx'
import { deriveCorrectionAttempts } from './correctionAttempts.js'
import { deriveTraceabilityChain, hasTraceabilityReferences } from './traceability.js'
import { formatDateTime } from '../../../../utils/dateTime.js'

function formatRunDate(value) {
  if (!value) return 'Not recorded'
  const formatted = formatDateTime(value)
  return formatted || value
}

function extractGroupedReferences(outputs) {
  if (!outputs || typeof outputs !== 'object') return { sources: [], components: [], planning: [] }

  const sources = new Set()
  const components = new Set()
  const planning = new Set()

  const collectSourceRefs = (items) => {
    if (Array.isArray(items)) {
      items.forEach((item) => {
        if (Array.isArray(item?.source_refs)) {
          item.source_refs.forEach((ref) => sources.add(ref))
        }
      })
    }
  }

  collectSourceRefs(outputs.EPICS)
  collectSourceRefs(outputs.USER_STORIES)
  collectSourceRefs(outputs.TASKS)
  collectSourceRefs(outputs.SYSTEM_ARCHITECTURE?.components)
  collectSourceRefs(outputs.DATABASE_SCHEMA?.entities)
  collectSourceRefs(outputs.UML_DIAGRAMS?.diagrams)
  collectSourceRefs(outputs.API_SPECIFICATION?.operations)
  collectSourceRefs(outputs.WIREFRAMES?.wireframes)

  if (Array.isArray(outputs.SYSTEM_ARCHITECTURE?.components)) {
    outputs.SYSTEM_ARCHITECTURE.components.forEach((c) => {
      if (c?.id) components.add(c.id)
    })
  }
  if (Array.isArray(outputs.API_SPECIFICATION?.operations)) {
    outputs.API_SPECIFICATION.operations.forEach((op) => {
      if (Array.isArray(op?.component_refs)) {
        op.component_refs.forEach((ref) => components.add(ref))
      }
    })
  }

  const collectIds = (items) => {
    if (Array.isArray(items)) {
      items.forEach((i) => {
        if (i?.id) planning.add(i.id)
      })
    }
  }
  collectIds(outputs.EPICS)
  collectIds(outputs.USER_STORIES)
  collectIds(outputs.TASKS)

  return {
    sources: Array.from(sources),
    components: Array.from(components),
    planning: Array.from(planning),
  }
}

function ValidationTraceabilityHistory({
  title = 'Validation, Traceability & Run History',
  subtitle = 'Evidence for human review and research evaluation',
  status,
  result,
  run,
  outputs,
  warnings = [],
  errors = [],
  correction_attempts,
  isHistorical = false,
  project,
  runs = [],
  onViewRun,
  onBackToOverview,
}) {
  const safeOutputs =
    outputs && typeof outputs === 'object'
      ? outputs
      : result?.outputs || run?.output_manifest || {}

  const effectiveStatus = status || result?.status || run?.status || (errors.length > 0 ? 'FAILED' : 'COMPLETED')
  const hasErrors = (Array.isArray(errors) && errors.length > 0) || (Array.isArray(result?.errors) && result.errors.length > 0)

  // Derive correction attempts truthfully
  const attemptsValue = deriveCorrectionAttempts({
    correction_attempts,
    result,
    run,
    warnings,
    errors,
    status: effectiveStatus,
    isHistorical,
    title,
  })

  const hasCorrectionCount = attemptsValue !== 'Not available' && Number(attemptsValue) > 0
  const allWarnings = [
    ...(Array.isArray(warnings) ? warnings : []),
    ...(Array.isArray(result?.warnings) ? result.warnings : []),
    ...(Array.isArray(run?.warnings) ? run.warnings : []),
  ]
  const hasOutputCorrectedWarning = allWarnings.some(
    (w) => typeof w === 'object' && w !== null && w.code === 'OUTPUT_CORRECTED',
  )
  const hasCorrections = hasCorrectionCount || hasOutputCorrectedWarning

  // Derive findings list
  const allErrors = [
    ...(Array.isArray(errors) ? errors : []),
    ...(Array.isArray(result?.errors) ? result.errors : []),
    ...(Array.isArray(run?.errors) ? run.errors : []),
  ]

  // Derive traceability
  const hasTraceability = hasTraceabilityReferences(safeOutputs)
  const traceabilityChain = deriveTraceabilityChain(safeOutputs)
  const groupedRefs = extractGroupedReferences(safeOutputs)

  // Prepare historical runs list from props or active run
  let runList = Array.isArray(runs) && runs.length > 0 ? runs : []
  if (runList.length === 0) {
    if (run) {
      runList = [run]
    } else if (result) {
      runList = [
        {
          run_id: result.run_id || 'RUN-CURRENT',
          created_at: result.created_at || new Date().toISOString(),
          status: result.status || effectiveStatus,
          selected_outputs: result.selected_outputs || Object.keys(safeOutputs),
          output_manifest: result.outputs,
          warnings: result.warnings || warnings,
          errors: result.errors || errors,
        },
      ]
    }
  }

  const handleOpenRun = (targetRunId) => {
    if (onViewRun) {
      onViewRun(targetRunId)
    }
  }

  return (
    <section aria-labelledby="validation-history-title" className="space-y-6">
      {/* Top breadcrumb bar matching S2-12 PNG */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-content-muted">
        <div className="flex items-center gap-1.5">
          <span className="font-medium text-content-secondary">{project?.name || 'BookEase'}</span>
          <span className="text-content-muted">/</span>
          <span>Standalone Agent 2</span>
        </div>
        <div className="flex items-center gap-2">
          <span>Standalone demo</span>
          <span className="text-content-muted">•</span>
          <span className="flex items-center gap-1.5 text-content-secondary">
            <span className="inline-block h-2 w-2 rounded-full bg-content-primary" aria-hidden="true" />
            Human reviewer
          </span>
        </div>
      </div>

      {/* Header row with Title, Subtitle, and Evidence available badge */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <h2 id="validation-history-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
            {title}
          </h2>
          <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
        </div>
        <div className="flex items-center gap-3 pt-1">
          <span className="inline-flex items-center rounded-control border border-state-success/40 bg-state-success-soft px-3 py-1 text-xs font-semibold text-state-success">
            Evidence available
          </span>
          {onBackToOverview && (
            <Button variant="outline" size="small" onClick={onBackToOverview}>
              ← Back to Results Overview
            </Button>
          )}
        </div>
      </div>

      {/* Two Evidence Cards matching S2-12 PNG */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Left Card: Validation evidence */}
        <div className="rounded-panel border border-default bg-surface p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-1">
            <h3 className="font-semibold text-content-primary text-base">Validation evidence</h3>
            <p className="text-xs text-content-muted">Bounded correction summary</p>
          </div>

          <div className="pt-2">
            {hasErrors || effectiveStatus === 'FAILED' ? (
              <span className="inline-flex items-center rounded-control border border-state-danger/40 bg-state-danger-soft px-2.5 py-1 text-xs font-semibold text-state-danger">
                Run failed validation/execution. Review persisted findings.
              </span>
            ) : hasCorrections ? (
              <span className="inline-flex items-center rounded-control border border-state-warning/40 bg-state-warning-soft px-2.5 py-1 text-xs font-semibold text-state-warning">
                Initial validation: findings detected
              </span>
            ) : (
              <span className="inline-flex items-center rounded-control border border-state-success/40 bg-state-success-soft px-2.5 py-1 text-xs font-semibold text-state-success">
                Run completed after Agent 2 validation
              </span>
            )}
          </div>

          <div className="space-y-2 pt-2 border-t border-default text-xs">
            <p className="text-content-secondary">
              Correction attempts: {attemptsValue}
            </p>

            {hasOutputCorrectedWarning && (
              <p className="text-state-warning">
                Automatic correction applied bounded repair to align generated schema.
              </p>
            )}

            {allErrors.length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="font-semibold text-state-danger">Errors:</p>
                <ul className="list-disc pl-4 space-y-0.5 text-content-secondary">
                  {allErrors.map((err, idx) => (
                    <li key={idx}>
                      {typeof err === 'object' ? `${err.code ? `${err.code}: ` : ''}${err.message}` : err}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {allWarnings.length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="font-semibold text-state-warning">Warnings / Findings:</p>
                <ul className="list-disc pl-4 space-y-0.5 text-content-secondary">
                  {allWarnings.map((w, idx) => (
                    <li key={idx}>
                      {typeof w === 'object' ? `${w.code ? `${w.code}: ` : ''}${w.message}` : w}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!hasErrors && allWarnings.length === 0 && (
              <p className="text-content-muted">
                No validation findings recorded. Clean execution passed.
              </p>
            )}
          </div>
        </div>

        {/* Right Card: Traceability evidence */}
        <div className="rounded-panel border border-default bg-surface p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-1">
            <h3 className="font-semibold text-content-primary text-base">Traceability evidence</h3>
            <p className="text-xs text-content-muted">Specification → design → planning</p>
          </div>

          <div className="pt-2">
            {traceabilityChain && traceabilityChain.length >= 2 ? (
              <div className="font-mono text-sm font-semibold text-content-primary break-words">
                {traceabilityChain.join(' → ')}
              </div>
            ) : groupedRefs.sources.length > 0 ? (
              <div className="font-mono text-sm font-semibold text-content-primary">
                {groupedRefs.sources[0]}
              </div>
            ) : hasTraceability ? (
              <div className="text-xs text-content-secondary">
                Traceability references available across artifacts.
              </div>
            ) : (
              <div className="text-xs text-content-muted">
                No explicit traceability chain returned for this run.
              </div>
            )}
          </div>

          <div className="space-y-2 pt-2 border-t border-default text-xs text-content-muted">
            {groupedRefs.sources.length > 0 && (
              <p>
                <strong className="text-content-secondary">Source refs:</strong> {groupedRefs.sources.join(', ')}
              </p>
            )}
            {groupedRefs.components.length > 0 && (
              <p>
                <strong className="text-content-secondary">Component refs:</strong> {groupedRefs.components.join(', ')}
              </p>
            )}
            {groupedRefs.planning.length > 0 && (
              <p>
                <strong className="text-content-secondary">Planning refs:</strong> {groupedRefs.planning.slice(0, 5).join(', ')}{groupedRefs.planning.length > 5 ? '…' : ''}
              </p>
            )}
            <p className="italic text-content-secondary pt-1">
              Human reviewer can inspect validation and traceability evidence.
            </p>
          </div>
        </div>
      </div>

      {/* Historical Agent 2 runs table Card matching S2-12 PNG */}
      <div className="rounded-panel border border-default bg-surface p-5 space-y-4">
        <div>
          <h3 className="font-semibold text-content-primary text-base">Historical Agent 2 runs</h3>
          <p className="mt-0.5 text-xs text-content-muted">
            Shared AgentRun lifecycle — reopen persisted results without regeneration.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm" aria-label="Historical Agent 2 runs table">
            <thead>
              <tr className="border-b border-default text-xs text-content-muted font-medium">
                <th scope="col" className="pb-3 pr-4 font-medium">Run</th>
                <th scope="col" className="pb-3 pr-4 font-medium">Created</th>
                <th scope="col" className="pb-3 pr-4 font-medium">Status</th>
                <th scope="col" className="pb-3 pr-4 font-medium">Outputs</th>
                <th scope="col" className="pb-3 font-medium text-right sm:text-left">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              {runList.map((r) => {
                const isRunFailed = r.status === 'FAILED'
                const outputsArray = Array.isArray(r.selected_outputs)
                  ? r.selected_outputs
                  : r.output_manifest && typeof r.output_manifest === 'object'
                    ? Object.keys(r.output_manifest)
                    : []

                let outputText = `${outputsArray.length} outputs`
                if (isRunFailed) {
                  outputText =
                    (Array.isArray(r.errors) && r.errors[0]?.message) ||
                    (Array.isArray(r.errors) && typeof r.errors[0] === 'string' && r.errors[0]) ||
                    'Structured output invalid'
                }

                return (
                  <tr key={r.run_id} className="hover:bg-elevated/60 transition-colors">
                    <td className="py-3 pr-4 font-mono text-xs font-semibold text-content-primary">
                      {r.run_id}
                    </td>
                    <td className="py-3 pr-4 text-xs text-content-secondary whitespace-nowrap">
                      {formatRunDate(r.created_at || r.started_at)}
                    </td>
                    <td className="py-3 pr-4 text-xs font-semibold uppercase">
                      {isRunFailed ? (
                        <span className="text-state-danger">FAILED</span>
                      ) : (
                        <span className="text-state-success">COMPLETED</span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-xs text-content-secondary">
                      {outputText}
                    </td>
                    <td className="py-3 text-right sm:text-left">
                      <Button
                        variant="ghost"
                        size="small"
                        onClick={() => handleOpenRun(r.run_id)}
                        aria-label={`Open run ${r.run_id}`}
                      >
                        Open
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Standalone scope disclaimer banner matching S2-12 PNG */}
      <div className="rounded-panel border border-default bg-surface p-4 text-xs text-content-muted">
        Standalone scope: no Agent 1/3/4 execution · no Orchestrator · no H2 · no integrated SKB write · no Jira Cloud sync · no RAG.
      </div>
    </section>
  )
}

export default ValidationTraceabilityHistory
