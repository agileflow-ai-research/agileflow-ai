import Button from '../../../ui/Button.jsx'
import { downloadJiraPlan } from '../../../../services/jiraPlanExport.js'
import { deriveCorrectionAttempts } from './correctionAttempts.js'
import { deriveTraceabilityChain, hasTraceabilityReferences } from './traceability.js'

const designOutputCodes = [
  'SYSTEM_ARCHITECTURE',
  'UML_DIAGRAMS',
  'DATABASE_SCHEMA',
  'API_SPECIFICATION',
  'WIREFRAMES',
  'UI_FLOW',
]

function getDesignArtifactSummary(code, data) {
  switch (code) {
    case 'SYSTEM_ARCHITECTURE': {
      const count = Array.isArray(data?.components) ? data.components.length : 0
      return `System architecture · ${count} ${count === 1 ? 'component' : 'components'}`
    }
    case 'UML_DIAGRAMS': {
      const count = Array.isArray(data?.diagrams) ? data.diagrams.length : 0
      return `UML diagrams · ${count} ${count === 1 ? 'diagram' : 'diagrams'}`
    }
    case 'DATABASE_SCHEMA': {
      const count = Array.isArray(data?.entities) ? data.entities.length : 0
      return `Database schema · ${count} ${count === 1 ? 'entity' : 'entities'}`
    }
    case 'API_SPECIFICATION': {
      const count = Array.isArray(data?.operations) ? data.operations.length : 0
      return `API specification · ${count} ${count === 1 ? 'operation' : 'operations'}`
    }
    case 'WIREFRAMES': {
      const count = Array.isArray(data?.screens) ? data.screens.length : 0
      return `Wireframes · ${count} ${count === 1 ? 'screen' : 'screens'}`
    }
    case 'UI_FLOW': {
      const count = Array.isArray(data?.flows) ? data.flows.length : 0
      return `UI flow · ${count} ${count === 1 ? 'flow' : 'flows'}`
    }
    default:
      return null
  }
}

function getPlanningArtifactSummaries(outputs) {
  const items = []
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : {}

  const hierarchyParts = []
  if (Array.isArray(safeOutputs.EPICS)) {
    const count = safeOutputs.EPICS.length
    const hasChildren =
      Array.isArray(safeOutputs.FEATURES) ||
      Array.isArray(safeOutputs.USER_STORIES) ||
      Array.isArray(safeOutputs.TASKS)
    const names = safeOutputs.EPICS.map((e) => e.title || e.id).filter(Boolean)
    const suffix = !hasChildren && count <= 3 && names.length > 0 ? ` (${names.join(', ')})` : ''
    hierarchyParts.push(`${count} ${count === 1 ? 'epic' : 'epics'}${suffix}`)
  }
  if (Array.isArray(safeOutputs.FEATURES)) {
    const count = safeOutputs.FEATURES.length
    hierarchyParts.push(`${count} ${count === 1 ? 'feature' : 'features'}`)
  }
  if (Array.isArray(safeOutputs.USER_STORIES)) {
    const count = safeOutputs.USER_STORIES.length
    hierarchyParts.push(`${count} ${count === 1 ? 'story' : 'stories'}`)
  }
  if (Array.isArray(safeOutputs.TASKS)) {
    const count = safeOutputs.TASKS.length
    hierarchyParts.push(`${count} ${count === 1 ? 'task' : 'tasks'}`)
  }

  if (hierarchyParts.length > 0) {
    items.push(hierarchyParts.join(' · '))
  }

  if (Array.isArray(safeOutputs.PRODUCT_BACKLOG)) {
    const count = safeOutputs.PRODUCT_BACKLOG.length
    items.push(`Product backlog · ${count} ${count === 1 ? 'item' : 'items'}`)
  }
  if (Array.isArray(safeOutputs.SPRINT_PLAN)) {
    const count = safeOutputs.SPRINT_PLAN.length
    items.push(`Sprint plan · ${count} ${count === 1 ? 'sprint' : 'sprints'}`)
  }
  if (Array.isArray(safeOutputs.TASK_ASSIGNMENT)) {
    const count = safeOutputs.TASK_ASSIGNMENT.length
    items.push(`Task assignments · ${count} ${count === 1 ? 'assignment' : 'assignments'}`)
  }
  if (safeOutputs.JIRA_PLAN && typeof safeOutputs.JIRA_PLAN === 'object') {
    const plan = safeOutputs.JIRA_PLAN
    const epicsCount = Array.isArray(plan.epics) ? plan.epics.length : 0
    const storiesCount = Array.isArray(plan.stories) ? plan.stories.length : 0
    const tasksCount = Array.isArray(plan.tasks) ? plan.tasks.length : 0
    const sprintsCount = Array.isArray(plan.sprints) ? plan.sprints.length : 0
    const epicNames = Array.isArray(plan.epics) ? plan.epics.map((e) => e.title || e.id).filter(Boolean) : []
    const planParts = []
    if (epicsCount) {
      planParts.push(
        <span key="epics">
          {epicsCount} {epicsCount === 1 ? 'epic' : 'epics'}
          {epicNames.length > 0 && epicNames.length <= 3 ? (
            <>
              {' ('}
              {epicNames.map((name, i) => (
                <span key={i}>
                  {i > 0 && ', '}
                  <span>{name}</span>
                </span>
              ))}
              {')'}
            </>
          ) : ''}
        </span>,
      )
    }
    if (storiesCount) planParts.push(`${storiesCount} stories`)
    if (tasksCount) planParts.push(`${tasksCount} tasks`)
    if (sprintsCount) planParts.push(`${sprintsCount} sprints`)
    items.push(
      <span key="jira-plan">
        Jira-ready plan ·{' '}
        {planParts.map((part, i) => (
          <span key={i}>
            {i > 0 && ' · '}
            {part}
          </span>
        ))}
      </span>,
    )
    if (plan.synchronization) {
      items.push(
        `Synchronization: ${plan.synchronization === 'NOT_PERFORMED' ? 'Not performed' : plan.synchronization}`,
      )
    }
  }

  return items
}


function ResultsOverview({
  title = 'Agent 2 Results',
  subtitle = 'Generated design and planning artifacts',
  status,
  result,
  run,
  outputs,
  warnings = [],
  errors = [],
  isHistorical = false,
  correction_attempts,
  project,
  onStartAnotherRun,
  onOpenRunHistory,
  onViewDesignArtifacts,
  onViewPlanningHierarchy,
  onViewSprintPlan,
  onViewTaskAssignment,
  onViewJiraPlan,
  onViewValidationHistory,
  actions,
}) {
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : result?.outputs || {}
  const effectiveStatus = status || result?.status || (errors.length > 0 ? 'FAILED' : 'COMPLETED')
  const jiraPlan = safeOutputs.JIRA_PLAN
  const hasSprintPlan = Boolean(
    safeOutputs.SPRINT_PLAN && (!Array.isArray(safeOutputs.SPRINT_PLAN) || safeOutputs.SPRINT_PLAN.length > 0),
  )
  const hasTaskAssignment = Boolean(
    safeOutputs.TASK_ASSIGNMENT &&
      (!Array.isArray(safeOutputs.TASK_ASSIGNMENT) || safeOutputs.TASK_ASSIGNMENT.length > 0),
  )

  // Derive summary metrics dynamically
  const outputCount = Object.keys(safeOutputs).length
  const hasErrors = errors.length > 0
  const validationStatus =
    effectiveStatus === 'COMPLETED' && !hasErrors
      ? 'Passed'
      : hasErrors || effectiveStatus === 'FAILED'
        ? 'Failed'
        : 'Not available'

  // Truthful correction attempts using real response or historical run evidence
  const correctionAttemptsValue = deriveCorrectionAttempts({
    correction_attempts,
    result,
    run,
    warnings,
    errors,
    status: effectiveStatus,
    isHistorical,
    title,
  })

  const hasTraceability = hasTraceabilityReferences(safeOutputs)
  const traceabilityChain = deriveTraceabilityChain(safeOutputs)

  // Derive Result Package items
  const designItems = designOutputCodes
    .filter((code) => Object.hasOwn(safeOutputs, code))
    .map((code) => getDesignArtifactSummary(code, safeOutputs[code]))
    .filter(Boolean)

  const planningItems = getPlanningArtifactSummaries(safeOutputs)

  const handleOpenRunHistory = () => {
    if (onOpenRunHistory) {
      onOpenRunHistory()
      return
    }
    const historySection = document.querySelector('[aria-label="Run History"]')
    if (historySection) {
      historySection.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <section aria-labelledby="results-title" className="space-y-6">
      {/* Top breadcrumb bar matching S2-06 PNG */}
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

      {/* Header row with Title, Subtitle, and Status Badge */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <h2 id="results-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
            {title}
          </h2>
          <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
        </div>
        <div className="pt-1">
          {effectiveStatus === 'COMPLETED' ? (
            <span className="inline-flex items-center rounded-control border border-state-success/40 bg-state-success-soft px-3 py-1 text-xs font-semibold uppercase tracking-wider text-state-success">
              COMPLETED
            </span>
          ) : effectiveStatus === 'FAILED' ? (
            <span className="inline-flex items-center rounded-control border border-state-danger/40 bg-state-danger/20 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-state-danger">
              FAILED
            </span>
          ) : null}
        </div>
      </div>

      {/* Summary Metrics (4 cards) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Summary metrics">
        {/* Outputs generated */}
        <div className="flex flex-col justify-between rounded-panel border border-default bg-surface p-4">
          <span className="text-xs text-content-muted">Outputs generated</span>
          <span className={`mt-2 text-2xl font-bold ${outputCount > 0 ? 'text-state-success' : 'text-content-muted'}`}>
            {outputCount}
          </span>
        </div>

        {/* Validation */}
        <div className="flex flex-col justify-between rounded-panel border border-default bg-surface p-4">
          <span className="text-xs text-content-muted">Validation</span>
          <span
            className={`mt-2 text-2xl font-bold ${
              validationStatus === 'Passed'
                ? 'text-state-success'
                : validationStatus === 'Failed'
                  ? 'text-state-danger'
                  : 'text-content-muted'
            }`}
          >
            {validationStatus}
          </span>
        </div>

        {/* Correction attempts */}
        <div className="flex flex-col justify-between rounded-panel border border-default bg-surface p-4">
          <span className="text-xs text-content-muted">Correction attempts</span>
          <span className="mt-2 text-2xl font-bold text-content-secondary">{correctionAttemptsValue}</span>
        </div>

        {/* Traceability */}
        <div className="flex flex-col justify-between rounded-panel border border-default bg-surface p-4">
          <span className="text-xs text-content-muted">Traceability</span>
          <span className={`mt-2 text-2xl font-bold ${hasTraceability ? 'text-brand' : 'text-content-muted'}`}>
            {hasTraceability ? 'Available' : 'Not available'}
          </span>
        </div>
      </div>

      {/* Result Package Cards (2-column grid) */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Design package */}
        <div className="rounded-panel border border-default bg-surface p-4">
          <h3 className="font-semibold text-content-primary">Design package</h3>
          <p className="mt-0.5 text-xs text-content-muted">Architecture and technical specifications</p>
          <div className="mt-3 space-y-1.5 text-sm text-content-secondary">
            {designItems.length > 0 ? (
              designItems.map((item, idx) => <p key={idx}>• {item}</p>)
            ) : (
              <p className="text-xs text-content-muted">No design artifacts returned for this run.</p>
            )}
          </div>
        </div>

        {/* Planning package */}
        <div className="rounded-panel border border-default bg-surface p-4">
          <h3 className="font-semibold text-content-primary">Planning package</h3>
          <p className="mt-0.5 text-xs text-content-muted">Agile hierarchy and delivery plan</p>
          <div className="mt-3 space-y-1.5 text-sm text-content-secondary">
            {planningItems.length > 0 ? (
              planningItems.map((item, idx) => <p key={idx}>• {item}</p>)
            ) : (
              <p className="text-xs text-content-muted">No planning artifacts returned for this run.</p>
            )}
          </div>
        </div>
      </div>

      {/* Validation & Traceability Evidence Card */}
      <div className="space-y-3 rounded-panel border border-default bg-surface p-4">
        <div>
          <h3 className="font-semibold text-content-primary">Validation & traceability evidence</h3>
          <p className="mt-0.5 text-xs text-content-muted">
            {effectiveStatus === 'COMPLETED' && !hasErrors
              ? 'Run completed after Agent 2 validation.'
              : 'Execution checks completed with findings.'}
          </p>
        </div>

        {/* Validation Badges */}
        <div className="flex flex-wrap items-center gap-2">
          {effectiveStatus === 'COMPLETED' && !hasErrors && (
            <span className="inline-flex items-center rounded-control border border-state-success/40 bg-state-success-soft px-3 py-1 text-xs font-medium text-state-success">
              Structural validation passed
            </span>
          )}
          {hasTraceability && (
            <span className="inline-flex items-center rounded-control border border-state-success/40 bg-state-success-soft px-3 py-1 text-xs font-medium text-state-success">
              Cross-artifact references valid
            </span>
          )}
        </div>

        {/* Traceability preview */}
        {traceabilityChain && traceabilityChain.length >= 2 ? (
          <p className="text-xs font-mono text-brand">
            Example trace: {traceabilityChain.join(' → ')}
          </p>
        ) : hasTraceability ? (
          <p className="text-xs text-content-secondary">
            Traceability references are available within generated artifacts.
          </p>
        ) : (
          <p className="text-xs text-content-muted">
            No explicit traceability chain returned for this run.
          </p>
        )}

        {/* Truthful Warnings & Errors */}
        {warnings && warnings.length > 0 && (
          <div className="mt-2 rounded-control border border-state-warning/40 bg-state-warning/10 p-3">
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
          <div className="mt-2 rounded-control border border-state-danger/40 bg-state-danger/10 p-3">
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
      </div>

      {/* Actions matching PNG */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <Button
          variant="primary"
          disabled={!onViewDesignArtifacts}
          onClick={onViewDesignArtifacts}
          title={!onViewDesignArtifacts ? 'Design artifact detail view will be available in S2-07' : undefined}
        >
          View design artifacts
        </Button>
        <Button
          variant="outline"
          disabled={!onViewPlanningHierarchy}
          onClick={onViewPlanningHierarchy}
          title={!onViewPlanningHierarchy ? 'Planning hierarchy view will be available in S2-08' : undefined}
        >
          View planning hierarchy
        </Button>
        {hasSprintPlan && (
          <Button
            variant="outline"
            disabled={!onViewSprintPlan}
            onClick={onViewSprintPlan}
          >
            View sprint plan
          </Button>
        )}
        {hasTaskAssignment && (
          <Button
            variant="outline"
            disabled={!onViewTaskAssignment}
            onClick={onViewTaskAssignment}
          >
            View task assignments
          </Button>
        )}
        {jiraPlan && (
          <Button
            variant="outline"
            disabled={!onViewJiraPlan}
            onClick={onViewJiraPlan}
          >
            View Jira plan
          </Button>
        )}
        <Button
          variant="outline"
          disabled={!onViewValidationHistory && !onOpenRunHistory}
          onClick={onViewValidationHistory || handleOpenRunHistory}
        >
          Validation & history
        </Button>
        <Button variant="outline" onClick={handleOpenRunHistory}>
          Open run history
        </Button>
        {onStartAnotherRun && (
          <Button variant="outline" onClick={onStartAnotherRun}>
            Start another run
          </Button>
        )}
        {jiraPlan && (
          <Button variant="outline" onClick={() => downloadJiraPlan(jiraPlan)}>
            Download Jira-compatible JSON
          </Button>
        )}
        {actions}
      </div>
    </section>
  )
}

export default ResultsOverview
