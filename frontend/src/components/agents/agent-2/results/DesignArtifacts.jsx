import Button from '../../../ui/Button.jsx'

function getMethodColor(method) {
  switch (method?.toUpperCase()) {
    case 'POST':
      return 'text-state-success'
    case 'GET':
      return 'text-state-info'
    case 'PUT':
      return 'text-state-warning'
    case 'PATCH':
      return 'text-brand'
    case 'DELETE':
      return 'text-state-danger'
    default:
      return 'text-content-primary'
  }
}

function DesignArtifacts({
  title = 'Generated Design Artifacts',
  subtitle = 'Structured architecture, UML, database and API specifications',
  status,
  result,
  run,
  outputs,
  warnings = [],
  errors = [],
  project,
  onBackToOverview,
}) {
  const safeOutputs =
    outputs && typeof outputs === 'object'
      ? outputs
      : result?.outputs || run?.output_manifest || {}

  const hasErrors = Array.isArray(errors) && errors.length > 0
  const isFailed = status === 'FAILED' || hasErrors

  const arch = safeOutputs.SYSTEM_ARCHITECTURE
  const uml = safeOutputs.UML_DIAGRAMS
  const db = safeOutputs.DATABASE_SCHEMA
  const api = safeOutputs.API_SPECIFICATION
  const wireframes = safeOutputs.WIREFRAMES
  const uiFlow = safeOutputs.UI_FLOW

  const archComponents = Array.isArray(arch?.components) ? arch.components : []
  const umlDiagrams = Array.isArray(uml?.diagrams) ? uml.diagrams : []
  const dbEntities = Array.isArray(db?.entities) ? db.entities : []
  const apiOperations = Array.isArray(api?.operations) ? api.operations : []
  const wfScreens = Array.isArray(wireframes?.screens) ? wireframes.screens : []
  const flowItems = Array.isArray(uiFlow?.flows) ? uiFlow.flows : []

  const hasDesignOutputs =
    Boolean(arch) ||
    Boolean(uml) ||
    Boolean(db) ||
    Boolean(api) ||
    Boolean(wireframes) ||
    Boolean(uiFlow)

  return (
    <section aria-labelledby="design-artifacts-heading" className="space-y-6">
      {/* Top breadcrumb bar matching S2-07 PNG */}
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

      {/* Navigation back control */}
      {onBackToOverview && (
        <div>
          <button
            type="button"
            onClick={onBackToOverview}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-content-muted transition-colors hover:text-content-primary"
            aria-label="Back to Results Overview"
          >
            <span aria-hidden="true">←</span>
            <span>Back to Results Overview</span>
          </button>
        </div>
      )}

      {/* Header with Validated badge matching PNG */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            id="design-artifacts-heading"
            className="text-2xl font-bold tracking-tight text-content-primary"
          >
            {title}
          </h2>
          <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
        </div>
        <div>
          <span
            className={`inline-flex items-center rounded-control border px-3 py-1 text-xs font-medium ${
              isFailed
                ? 'border-state-danger/40 bg-state-danger-soft text-state-danger'
                : 'border-state-success/40 bg-state-success-soft text-state-success'
            }`}
          >
            {isFailed ? 'Validation findings' : 'Validated'}
          </span>
        </div>
      </div>

      {/* Warnings & Errors */}
      {warnings && warnings.length > 0 && (
        <div className="rounded-control border border-state-warning/40 bg-state-warning/10 p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-state-warning">Warnings</h4>
          <ul className="mt-1 space-y-1 text-xs text-content-secondary">
            {warnings.map((w, idx) => (
              <li key={idx}>
                • {typeof w === 'object' ? `${w.code ? `${w.code}: ` : ''}${w.message}` : w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {errors && errors.length > 0 && (
        <div className="rounded-control border border-state-danger/40 bg-state-danger/10 p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-state-danger">Errors</h4>
          <ul className="mt-1 space-y-1 text-xs text-content-secondary">
            {errors.map((e, idx) => (
              <li key={idx}>
                • {typeof e === 'object' ? `${e.code ? `${e.code}: ` : ''}${e.message}` : e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Empty state if no design artifacts were returned */}
      {!hasDesignOutputs && (
        <div className="rounded-panel border border-default bg-surface p-8 text-center">
          <p className="text-sm text-content-muted">
            No design artifacts were generated for this run.
          </p>
          {onBackToOverview && (
            <div className="mt-4">
              <Button variant="outline" size="small" onClick={onBackToOverview}>
                Back to Results Overview
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Row 1: System Architecture and Database Schema (2-column grid matching PNG) */}
      {(Boolean(arch) || Boolean(db)) && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* System Architecture */}
          {arch && (
            <div className="rounded-panel border border-default bg-surface p-5 space-y-3">
              <div>
                <h3 className="font-semibold text-content-primary">System architecture</h3>
                <p className="mt-0.5 text-xs text-content-muted">
                  {arch.style
                    ? `ARCH-001 · ${arch.style}`
                    : `${archComponents.length} ${archComponents.length === 1 ? 'component' : 'components'}`}
                </p>
              </div>

              <ul className="space-y-2 text-sm text-content-secondary" aria-label="System architecture components">
                {archComponents.map((comp) => (
                  <li key={comp.id || comp.name} className="space-y-1">
                    <div className="flex items-baseline gap-2">
                      <span className="text-content-muted" aria-hidden="true">•</span>
                      <span className="font-medium text-content-primary">
                        {comp.id ? `${comp.id} · ` : ''}
                        {comp.name}
                      </span>
                    </div>
                    {comp.responsibility && (
                      <p className="pl-4 text-xs text-content-secondary">{comp.responsibility}</p>
                    )}
                    {Array.isArray(comp.dependencies) && comp.dependencies.length > 0 && (
                      <p className="pl-4 text-xs text-content-muted">
                        <span className="font-medium text-content-secondary">Dependencies:</span>{' '}
                        {comp.dependencies.join(', ')}
                      </p>
                    )}
                    {Array.isArray(comp.source_refs) && comp.source_refs.length > 0 && (
                      <p className="pl-4 text-xs text-content-muted">
                        <span className="font-medium text-content-secondary">Source refs:</span>{' '}
                        <span className="font-mono text-content-secondary">{comp.source_refs.join(', ')}</span>
                      </p>
                    )}
                  </li>
                ))}
              </ul>

              {Array.isArray(arch.boundaries) && arch.boundaries.length > 0 && (
                <div className="border-t border-default pt-2 text-xs">
                  <span className="font-medium text-content-secondary">Boundaries:</span>{' '}
                  <span className="text-content-muted">{arch.boundaries.join(', ')}</span>
                </div>
              )}
              {Array.isArray(arch.constraints) && arch.constraints.length > 0 && (
                <div className="pt-1 text-xs">
                  <span className="font-medium text-content-secondary">Constraints:</span>{' '}
                  <span className="text-content-muted">{arch.constraints.join(', ')}</span>
                </div>
              )}
            </div>
          )}

          {/* Database Schema */}
          {db && (
            <div className="rounded-panel border border-default bg-surface p-5 space-y-3">
              <div>
                <h3 className="font-semibold text-content-primary">Database schema</h3>
                <p className="mt-0.5 text-xs text-content-muted">
                  {dbEntities.length} traceable {dbEntities.length === 1 ? 'entity' : 'entities'}
                </p>
              </div>

              <ul className="space-y-3 text-sm text-content-secondary" aria-label="Database schema entities">
                {dbEntities.map((entity) => (
                  <li key={entity.id || entity.name} className="space-y-1.5">
                    <div className="flex items-baseline gap-2">
                      <span className="text-content-muted" aria-hidden="true">•</span>
                      <span className="font-mono text-xs font-semibold text-content-primary">
                        {entity.id || entity.name}
                      </span>
                      {entity.id && entity.name && entity.id !== entity.name && (
                        <span className="text-xs text-content-muted">({entity.name})</span>
                      )}
                    </div>

                    {Array.isArray(entity.fields) && entity.fields.length > 0 && (
                      <div className="overflow-x-auto pl-4">
                        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-content-muted font-mono">
                          {entity.fields.map((field, fIdx) => (
                            <span key={fIdx} className="inline-flex items-center gap-1">
                              <span className="text-content-secondary">{field.name}</span>
                              <span className="text-content-muted">
                                ({field.data_type}
                                {field.required ? ', req' : ''}
                                {field.constraints?.length ? `, ${field.constraints.join(' ')}` : ''})
                              </span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {Array.isArray(entity.relationships) && entity.relationships.length > 0 && (
                      <p className="pl-4 text-xs text-content-muted">
                        <span className="font-medium text-content-secondary">Relationships:</span>{' '}
                        {entity.relationships.map((rel, rIdx) => (
                          <span key={rIdx} className="font-mono text-content-secondary">
                            {rIdx > 0 && ', '}
                            {rel.relationship_type} → {rel.target_entity_id}
                            {rel.description ? ` (${rel.description})` : ''}
                          </span>
                        ))}
                      </p>
                    )}

                    {Array.isArray(entity.source_refs) && entity.source_refs.length > 0 && (
                      <p className="pl-4 text-xs text-content-muted">
                        <span className="font-medium text-content-secondary">Source refs:</span>{' '}
                        <span className="font-mono text-content-secondary">{entity.source_refs.join(', ')}</span>
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Row 2: API Specification (full-width table matching PNG) */}
      {api && (
        <div className="rounded-panel border border-default bg-surface p-5 space-y-4">
          <div>
            <h3 className="font-semibold text-content-primary">API specification</h3>
            <p className="mt-0.5 text-xs text-content-muted">
              {api.base_path ? `Base path: ${api.base_path} · ` : ''}
              Operations reference architecture components and database entities.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="API operations">
              <thead>
                <tr className="border-b border-default text-content-muted">
                  <th className="pb-2.5 font-medium">Method</th>
                  <th className="pb-2.5 font-medium">Path</th>
                  <th className="pb-2.5 font-medium">Component / Entity</th>
                  <th className="pb-2.5 font-medium">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-default font-mono">
                {apiOperations.map((op) => {
                  const compRefs = Array.isArray(op.component_refs) ? op.component_refs : []
                  const entRefs = Array.isArray(op.entity_refs) ? op.entity_refs : []
                  const combined = [...compRefs, ...entRefs]
                  const compEntityStr = combined.length > 0 ? combined.join(' / ') : '—'
                  const sourceStr = Array.isArray(op.source_refs) && op.source_refs.length > 0
                    ? op.source_refs.join(', ')
                    : '—'

                  return (
                    <tr
                      key={op.id || `${op.method}-${op.path}`}
                      className="transition-colors hover:bg-elevated/60"
                    >
                      <td className="py-2.5 font-bold">
                        <span className={getMethodColor(op.method)}>{op.method}</span>
                      </td>
                      <td className="py-2.5 text-content-primary">
                        {op.path}
                        {op.summary && (
                          <span className="block font-sans text-[11px] text-content-muted">
                            {op.summary}
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 text-content-secondary">{compEntityStr}</td>
                      <td className="py-2.5 text-content-secondary">{sourceStr}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Row 3: UML diagram source (full-width code block matching PNG) */}
      {uml && (
        <div className="rounded-panel border border-default bg-surface p-5 space-y-4">
          <div>
            <h3 className="font-semibold text-content-primary">UML diagram source</h3>
            <p className="mt-0.5 text-xs text-content-muted">
              Authoritative structured source — no fake rendered image.
            </p>
          </div>

          <div className="space-y-4">
            {umlDiagrams.map((diag) => (
              <div key={diag.id || diag.title} className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="font-medium text-content-primary">
                    {diag.title}
                    {diag.id ? ` (${diag.id})` : ''}
                  </span>
                  <span className="font-mono text-content-muted">
                    {diag.diagram_type} · {diag.notation}
                  </span>
                </div>
                <pre className="overflow-x-auto whitespace-pre-wrap rounded-control border border-default bg-canvas p-3 font-mono text-xs text-content-primary">
                  {diag.source}
                </pre>
                {Array.isArray(diag.source_refs) && diag.source_refs.length > 0 && (
                  <p className="text-xs text-content-muted">
                    <span className="font-medium text-content-secondary">Source refs:</span>{' '}
                    <span className="font-mono text-content-secondary">
                      {diag.source_refs.join(', ')}
                    </span>
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Wireframes (when present in output) */}
      {wireframes && (
        <div className="rounded-panel border border-default bg-surface p-5 space-y-4">
          <div>
            <h3 className="font-semibold text-content-primary">Wireframes</h3>
            <p className="mt-0.5 text-xs text-content-muted">
              Structured low-fidelity wireframe specifications ({wfScreens.length}{' '}
              {wfScreens.length === 1 ? 'screen' : 'screens'})
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {wfScreens.map((screen) => (
              <div
                key={screen.id || screen.name}
                className="rounded-control border border-default bg-elevated p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-sm font-semibold text-content-primary">{screen.name}</h4>
                  <span className="font-mono text-xs text-content-muted">{screen.id}</span>
                </div>
                {screen.purpose && (
                  <p className="text-xs text-content-secondary">{screen.purpose}</p>
                )}
                {Array.isArray(screen.regions) && screen.regions.length > 0 && (
                  <div className="text-xs">
                    <span className="font-medium text-content-secondary">Regions:</span>{' '}
                    <span className="text-content-muted">{screen.regions.join(', ')}</span>
                  </div>
                )}
                {Array.isArray(screen.components) && screen.components.length > 0 && (
                  <div className="text-xs">
                    <span className="font-medium text-content-secondary">Components:</span>{' '}
                    <span className="text-content-muted">{screen.components.join(', ')}</span>
                  </div>
                )}
                {Array.isArray(screen.interactions) && screen.interactions.length > 0 && (
                  <div className="text-xs">
                    <span className="font-medium text-content-secondary">Interactions:</span>{' '}
                    <span className="text-content-muted">{screen.interactions.join(', ')}</span>
                  </div>
                )}
                {Array.isArray(screen.source_refs) && screen.source_refs.length > 0 && (
                  <div className="text-xs text-content-muted">
                    <span className="font-medium text-content-secondary">Source refs:</span>{' '}
                    <span className="font-mono text-content-secondary">
                      {screen.source_refs.join(', ')}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* UI Flow (when present in output) */}
      {uiFlow && (
        <div className="rounded-panel border border-default bg-surface p-5 space-y-4">
          <div>
            <h3 className="font-semibold text-content-primary">UI flow</h3>
            <p className="mt-0.5 text-xs text-content-muted">
              User interaction flows and step transitions ({flowItems.length}{' '}
              {flowItems.length === 1 ? 'flow' : 'flows'})
            </p>
          </div>

          <div className="space-y-4">
            {flowItems.map((flow) => (
              <div
                key={flow.id || flow.goal}
                className="rounded-control border border-default bg-elevated p-4 space-y-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-semibold text-content-primary">{flow.actor}</span>
                    <span className="text-xs text-content-muted"> · {flow.goal}</span>
                  </div>
                  <span className="font-mono text-xs text-content-muted">{flow.id}</span>
                </div>
                {Array.isArray(flow.steps) && flow.steps.length > 0 && (
                  <ol className="list-decimal space-y-1 pl-4 text-xs text-content-secondary">
                    {flow.steps.map((step, sIdx) => (
                      <li key={sIdx}>{step}</li>
                    ))}
                  </ol>
                )}
                {Array.isArray(flow.screen_refs) && flow.screen_refs.length > 0 && (
                  <div className="text-xs text-content-muted">
                    <span className="font-medium text-content-secondary">Referenced screens:</span>{' '}
                    <span className="font-mono text-content-secondary">
                      {flow.screen_refs.join(', ')}
                    </span>
                  </div>
                )}
                {Array.isArray(flow.alternate_paths) && flow.alternate_paths.length > 0 && (
                  <div className="text-xs text-content-muted">
                    <span className="font-medium text-content-secondary">Alternate paths:</span>{' '}
                    <span className="text-content-secondary">
                      {flow.alternate_paths.join(', ')}
                    </span>
                  </div>
                )}
                {Array.isArray(flow.source_refs) && flow.source_refs.length > 0 && (
                  <div className="text-xs text-content-muted">
                    <span className="font-medium text-content-secondary">Source refs:</span>{' '}
                    <span className="font-mono text-content-secondary">
                      {flow.source_refs.join(', ')}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bottom actions */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        {onBackToOverview && (
          <Button variant="primary" onClick={onBackToOverview}>
            Back to Results Overview
          </Button>
        )}
      </div>
    </section>
  )
}

export default DesignArtifacts
