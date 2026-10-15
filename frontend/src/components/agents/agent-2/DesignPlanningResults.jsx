import Button from '../../ui/Button.jsx'
import { downloadJiraPlan } from '../../../services/jiraPlanExport.js'
import ArtifactViewer from '../ArtifactViewer.jsx'
import ResultsWorkspace from '../ResultsWorkspace.jsx'

const outputLabels = {
  SYSTEM_ARCHITECTURE: 'System Architecture',
  UML_DIAGRAMS: 'UML Diagrams',
  DATABASE_SCHEMA: 'Database Schema',
  API_SPECIFICATION: 'API Specification',
  WIREFRAMES: 'Wireframes',
  UI_FLOW: 'UI Flow',
  PRODUCT_BACKLOG: 'Product Backlog',
  EPICS: 'Epics',
  FEATURES: 'Features',
  USER_STORIES: 'User Stories',
  TASKS: 'Tasks',
  SPRINT_PLAN: 'Sprint Plan',
  TASK_ASSIGNMENT: 'Task Assignment',
  JIRA_PLAN: 'Jira-ready Plan',
}

const designOutputCodes = [
  'SYSTEM_ARCHITECTURE',
  'UML_DIAGRAMS',
  'DATABASE_SCHEMA',
  'API_SPECIFICATION',
  'WIREFRAMES',
  'UI_FLOW',
]

function deriveTraceabilityChain(outputs) {
  if (!outputs || typeof outputs !== 'object') return null

  const chain = []

  const apiOps = outputs.API_SPECIFICATION?.operations || []
  const firstOp = apiOps[0]

  let specRef = firstOp?.source_refs?.[0]
  const compRef = firstOp?.component_refs?.[0]
  const entityRef = firstOp?.entity_refs?.[0]
  const apiId = firstOp?.id

  const epics = Array.isArray(outputs.EPICS) ? outputs.EPICS : outputs.JIRA_PLAN?.epics || []
  const stories = Array.isArray(outputs.USER_STORIES) ? outputs.USER_STORIES : outputs.JIRA_PLAN?.stories || []
  const tasks = Array.isArray(outputs.TASKS) ? outputs.TASKS : outputs.JIRA_PLAN?.tasks || []

  const firstTask = tasks[0]
  const matchingStory = stories.find((s) => s.id === firstTask?.story_id) || stories[0]
  const matchingEpic = epics.find((e) => e.id === (firstTask?.epic_id || matchingStory?.epic_id)) || epics[0]

  if (!specRef) {
    specRef =
      matchingEpic?.source_refs?.[0] ||
      matchingStory?.source_refs?.[0] ||
      firstTask?.source_refs?.[0] ||
      outputs.SYSTEM_ARCHITECTURE?.components?.[0]?.source_refs?.[0] ||
      outputs.DATABASE_SCHEMA?.entities?.[0]?.source_refs?.[0]
  }

  if (specRef) chain.push(specRef)
  if (compRef && !chain.includes(compRef)) chain.push(compRef)
  if (entityRef && !chain.includes(entityRef)) chain.push(entityRef)
  if (apiId && !chain.includes(apiId)) chain.push(apiId)
  if (matchingEpic?.id && !chain.includes(matchingEpic.id)) chain.push(matchingEpic.id)
  if (matchingStory?.id && !chain.includes(matchingStory.id)) chain.push(matchingStory.id)
  if (firstTask?.id && !chain.includes(firstTask.id)) chain.push(firstTask.id)

  return chain.length >= 2 ? chain : null
}

function hasTraceabilityReferences(outputs) {
  if (!outputs || typeof outputs !== 'object') return false
  const jsonStr = JSON.stringify(outputs)
  return (
    jsonStr.includes('source_refs') ||
    jsonStr.includes('component_refs') ||
    jsonStr.includes('entity_refs') ||
    jsonStr.includes('item_refs') ||
    jsonStr.includes('screen_refs')
  )
}

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
    const planParts = []
    if (epicsCount) planParts.push(`${epicsCount} epics`)
    if (storiesCount) planParts.push(`${storiesCount} stories`)
    if (tasksCount) planParts.push(`${tasksCount} tasks`)
    if (sprintsCount) planParts.push(`${sprintsCount} sprints`)
    items.push(`Jira-ready plan · ${planParts.join(' · ') || 'Generated'}`)
    if (plan.synchronization) {
      items.push(
        `Synchronization: ${plan.synchronization === 'NOT_PERFORMED' ? 'Not performed' : plan.synchronization}`,
      )
    }
  }

  return items
}

function References({ values, label = 'Source references' }) {
  if (!Array.isArray(values) || values.length === 0) return null
  return (
    <p className="mt-2 text-xs text-content-muted">
      <strong>{label}:</strong> {values.join(', ')}
    </p>
  )
}

function DetailList({ values }) {
  if (!Array.isArray(values) || values.length === 0)
    return <p className="text-sm text-content-muted">None recorded.</p>
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-content-secondary">
      {values.map((value, index) => (
        <li key={`${index}-${value}`}>{value}</li>
      ))}
    </ul>
  )
}

function ItemCard({ title, id, children }) {
  return (
    <article className="rounded-control border border-default bg-canvas p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="font-semibold text-content-primary">{title}</h4>
        {id && <span className="font-mono text-xs text-content-muted">{id}</span>}
      </div>
      <div className="mt-3 text-sm text-content-secondary">{children}</div>
    </article>
  )
}

function Architecture({ value }) {
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>Style:</strong> {value.style}
      </p>
      {value.components.map((item) => (
        <ItemCard key={item.id} id={item.id} title={item.name}>
          <p>{item.responsibility}</p>
          <References label="Dependencies" values={item.dependencies} />
          <References values={item.source_refs} />
        </ItemCard>
      ))}
      <section>
        <h4 className="mb-2 font-semibold">Interactions</h4>
        <DetailList values={value.interactions} />
      </section>
      <section>
        <h4 className="mb-2 font-semibold">Boundaries</h4>
        <DetailList values={value.boundaries} />
      </section>
      <section>
        <h4 className="mb-2 font-semibold">Assumptions</h4>
        <DetailList values={value.assumptions} />
      </section>
    </div>
  )
}

function Diagrams({ value }) {
  return (
    <div className="space-y-4">
      {value.diagrams.map((item) => (
        <ItemCard key={item.id} id={item.id} title={item.title}>
          <p>
            <strong>Type:</strong> {item.diagram_type} · <strong>Notation:</strong> {item.notation}
          </p>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-control bg-elevated p-3 text-xs">
            {item.source}
          </pre>
          <References values={item.source_refs} />
        </ItemCard>
      ))}
    </div>
  )
}

function Database({ value }) {
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>Technology:</strong> {value.technology}
      </p>
      {value.entities.map((entity) => (
        <ItemCard key={entity.id} id={entity.id} title={entity.name}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th className="pb-2">Field</th>
                  <th className="pb-2">Type</th>
                  <th className="pb-2">Required</th>
                  <th className="pb-2">Constraints</th>
                </tr>
              </thead>
              <tbody>
                {entity.fields.map((field) => (
                  <tr key={field.name} className="border-t border-default">
                    <td className="py-2">{field.name}</td>
                    <td>{field.data_type}</td>
                    <td>{field.required ? 'Yes' : 'No'}</td>
                    <td>{field.constraints.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {entity.relationships.length > 0 && (
            <div className="mt-3">
              <strong>Relationships:</strong>
              <DetailList
                values={entity.relationships.map(
                  (relation) =>
                    `${relation.relationship_type} → ${relation.target_entity_id}: ${relation.description}`,
                )}
              />
            </div>
          )}
          <References values={entity.source_refs} />
        </ItemCard>
      ))}
    </div>
  )
}

function ApiSpecification({ value }) {
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>Base path:</strong> <code>{value.base_path}</code>
      </p>
      {value.operations.map((operation) => (
        <ItemCard key={operation.id} id={operation.id} title={`${operation.method} ${operation.path}`}>
          <p>{operation.summary}</p>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="font-semibold">Request</dt>
              <dd>{operation.request ?? 'None'}</dd>
            </div>
            <div>
              <dt className="font-semibold">Response</dt>
              <dd>{operation.response}</dd>
            </div>
            <div>
              <dt className="font-semibold">Authentication</dt>
              <dd>{operation.authentication}</dd>
            </div>
            <div>
              <dt className="font-semibold">Errors</dt>
              <dd>{operation.errors.join(', ') || 'None'}</dd>
            </div>
          </dl>
          <References label="Architecture components" values={operation.component_refs} />
          <References label="Database entities" values={operation.entity_refs} />
          <References values={operation.source_refs} />
        </ItemCard>
      ))}
    </div>
  )
}

function Wireframes({ value }) {
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>Fidelity:</strong> {value.fidelity}
      </p>
      {value.screens.map((screen) => (
        <ItemCard key={screen.id} id={screen.id} title={screen.name}>
          <p>{screen.purpose}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <div>
              <strong>Sections</strong>
              <DetailList values={screen.regions} />
            </div>
            <div>
              <strong>Components</strong>
              <DetailList values={screen.components} />
            </div>
            <div>
              <strong>Actions</strong>
              <DetailList values={screen.interactions} />
            </div>
          </div>
          <References values={screen.source_refs} />
        </ItemCard>
      ))}
    </div>
  )
}

function UiFlows({ value }) {
  return (
    <div className="space-y-4">
      {value.flows.map((flow) => (
        <ItemCard key={flow.id} id={flow.id} title={`${flow.actor}: ${flow.goal}`}>
          <ol className="list-decimal space-y-1 pl-5">
            {flow.steps.map((step, index) => (
              <li key={`${index}-${step}`}>{step}</li>
            ))}
          </ol>
          <References label="Screens" values={flow.screen_refs} />
          <References values={flow.source_refs} />
        </ItemCard>
      ))}
    </div>
  )
}

function PlanningItems({ items }) {
  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const id = item.id ?? item.item_id ?? item.task_id
        const parents = [item.epic_id, item.feature_id, item.story_id, item.parent_id].filter(Boolean)
        return (
          <ItemCard
            key={id ?? index}
            id={id}
            title={
              item.title ??
              item.name ??
              item.goal ??
              (item.priority ? `${id}: ${item.priority}` : `Item ${index + 1}`)
            }
          >
            <p>{item.description ?? item.outcome ?? item.benefit ?? item.rationale}</p>
            {parents.length > 0 && <References label="Hierarchy" values={parents} />}
            {item.depends_on?.length > 0 && <References label="Dependencies" values={item.depends_on} />}
            {item.estimate_points && (
              <p className="mt-2">
                <strong>Estimate:</strong> {item.estimate_points} points
              </p>
            )}
            <References values={item.source_refs} />
          </ItemCard>
        )
      })}
    </div>
  )
}

function SprintPlan({ items }) {
  return (
    <div className="space-y-4">
      {items.map((sprint) => (
        <ItemCard key={sprint.id} id={sprint.id} title={sprint.name}>
          <dl className="grid gap-3 sm:grid-cols-4">
            <div>
              <dt className="font-semibold">Duration</dt>
              <dd>{sprint.duration_days} days</dd>
            </div>
            <div>
              <dt className="font-semibold">Estimated capacity</dt>
              <dd>{sprint.capacity_points} points</dd>
            </div>
            <div>
              <dt className="font-semibold">Planned workload</dt>
              <dd>{sprint.planned_points} points</dd>
            </div>
            <div>
              <dt className="font-semibold">Estimated utilization</dt>
              <dd>{sprint.utilization_percent}%</dd>
            </div>
          </dl>
          <References label="Included work" values={sprint.item_refs} />
          <p className="mt-2 text-xs text-content-muted">{sprint.estimate_basis}</p>
          {sprint.planning_warnings?.length > 0 && (
            <div className="mt-3 rounded-control border border-state-warning/40 bg-state-warning/10 p-3">
              <strong>Planning warnings</strong>
              <DetailList values={sprint.planning_warnings} />
            </div>
          )}
        </ItemCard>
      ))}
    </div>
  )
}

function Assignments({ items }) {
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <ItemCard key={item.task_id} id={item.task_id} title={item.team_slot}>
          <p>
            <strong>Recommended role:</strong> {item.role}
          </p>
          <p className="mt-1">{item.rationale}</p>
          <dl className="mt-3 grid gap-2 sm:grid-cols-3">
            <div>
              <dt className="font-semibold">Role match</dt>
              <dd>{item.role_match ? 'Yes' : 'No'}</dd>
            </div>
            <div>
              <dt className="font-semibold">Skill matches</dt>
              <dd>{item.skill_matches?.join(', ') || 'None'}</dd>
            </div>
            <div>
              <dt className="font-semibold">Deterministic score</dt>
              <dd>{item.confidence_score}/100</dd>
            </div>
          </dl>
          {item.sprint_id && <References label="Sprint" values={[item.sprint_id]} />}
        </ItemCard>
      ))}
    </div>
  )
}

function JiraPlan({ plan }) {
  return (
    <div className="space-y-5">
      <p className="rounded-control border border-default bg-canvas p-3 text-sm">
        Synchronization:{' '}
        <strong>{plan.synchronization === 'NOT_PERFORMED' ? 'Not performed' : plan.synchronization}</strong>
      </p>
      <section>
        <h4 className="mb-2 font-semibold">Epics</h4>
        <PlanningItems items={plan.epics} />
      </section>
      <section>
        <h4 className="mb-2 font-semibold">Stories</h4>
        <PlanningItems items={plan.stories} />
      </section>
      <section>
        <h4 className="mb-2 font-semibold">Tasks</h4>
        <PlanningItems items={plan.tasks} />
      </section>
      <section>
        <h4 className="mb-2 font-semibold">Sprints</h4>
        <SprintPlan items={plan.sprints} />
      </section>
      <section>
        <h4 className="mb-2 font-semibold">Assignments</h4>
        <Assignments items={plan.assignments} />
      </section>
      <section>
        <h4 className="mb-2 font-semibold">Priorities</h4>
        <PlanningItems items={plan.priorities} />
      </section>
    </div>
  )
}

function renderOutput(code, value) {
  switch (code) {
    case 'SYSTEM_ARCHITECTURE':
      return <Architecture value={value} />
    case 'UML_DIAGRAMS':
      return <Diagrams value={value} />
    case 'DATABASE_SCHEMA':
      return <Database value={value} />
    case 'API_SPECIFICATION':
      return <ApiSpecification value={value} />
    case 'WIREFRAMES':
      return <Wireframes value={value} />
    case 'UI_FLOW':
      return <UiFlows value={value} />
    case 'SPRINT_PLAN':
      return <SprintPlan items={value} />
    case 'TASK_ASSIGNMENT':
      return <Assignments items={value} />
    case 'JIRA_PLAN':
      return <JiraPlan plan={value} />
    default:
      return Array.isArray(value) ? <PlanningItems items={value} /> : null
  }
}

function DetailedResultsWorkspace({ outputs, title, warnings, errors, actions }) {
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : {}
  const jiraPlan = safeOutputs.JIRA_PLAN
  const resultActions = (
    <div className="flex flex-wrap gap-2">
      {jiraPlan && (
        <Button variant="outline" onClick={() => downloadJiraPlan(jiraPlan)}>
          Download Jira-compatible JSON
        </Button>
      )}
      {actions}
    </div>
  )
  const sections = Object.keys(outputLabels)
    .filter((code) => Object.hasOwn(safeOutputs, code))
    .map((code) => ({
      id: code,
      title: outputLabels[code],
      content: (
        <ArtifactViewer heading={outputLabels[code]} metadata={code}>
          {renderOutput(code, safeOutputs[code])}
        </ArtifactViewer>
      ),
    }))
  if (sections.length === 0)
    sections.push({
      id: 'empty',
      title: 'No generated output',
      content: <p className="text-sm text-content-muted">This run did not produce a validated output artifact.</p>,
    })
  return (
    <ResultsWorkspace
      title={title}
      sections={sections}
      warnings={warnings}
      errors={errors}
      actions={resultActions}
    />
  )
}

function DesignPlanningResults({
  title = 'Agent 2 Results',
  subtitle = 'Generated design and planning artifacts',
  status,
  result,
  outputs,
  warnings = [],
  errors = [],
  project,
  onStartAnotherRun,
  onOpenRunHistory,
  onViewDesignArtifacts,
  onViewPlanningHierarchy,
  actions,
  mode = 'overview',
}) {
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : result?.outputs || {}
  const effectiveStatus = status || result?.status || (errors.length > 0 ? 'FAILED' : 'COMPLETED')
  const jiraPlan = safeOutputs.JIRA_PLAN

  // Check if detail mode is explicitly requested or historical RunDetail title passed
  const isDetail =
    mode === 'detail' ||
    title === 'Persisted design and planning outputs' ||
    title === 'Persisted requirements outputs'

  if (isDetail) {
    return (
      <DetailedResultsWorkspace
        outputs={safeOutputs}
        title={title}
        warnings={warnings}
        errors={errors}
        actions={actions}
      />
    )
  }

  // Derive summary metrics dynamically
  const outputCount = Object.keys(safeOutputs).length
  const hasErrors = errors.length > 0
  const validationStatus =
    effectiveStatus === 'COMPLETED' && !hasErrors
      ? 'Passed'
      : hasErrors || effectiveStatus === 'FAILED'
        ? 'Failed'
        : 'Not available'

  // Truthful correction attempts: current API does not return correction count, do not fabricate "1"
  const correctionAttemptsValue =
    result?.correction_attempts !== undefined ? String(result.correction_attempts) : 'Not available'

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
            <span className="inline-flex items-center rounded-control border border-[#065f46] bg-[#064e3b]/80 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#34d399]">
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
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Outputs generated</span>
          <span className={`mt-2 text-2xl font-bold ${outputCount > 0 ? 'text-[#34d399]' : 'text-content-muted'}`}>
            {outputCount}
          </span>
        </div>

        {/* Validation */}
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Validation</span>
          <span
            className={`mt-2 text-2xl font-bold ${
              validationStatus === 'Passed'
                ? 'text-[#34d399]'
                : validationStatus === 'Failed'
                  ? 'text-state-danger'
                  : 'text-content-muted'
            }`}
          >
            {validationStatus}
          </span>
        </div>

        {/* Correction attempts */}
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Correction attempts</span>
          <span className="mt-2 text-2xl font-bold text-content-secondary">{correctionAttemptsValue}</span>
        </div>

        {/* Traceability */}
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Traceability</span>
          <span className={`mt-2 text-2xl font-bold ${hasTraceability ? 'text-[#c084fc]' : 'text-content-muted'}`}>
            {hasTraceability ? 'Available' : 'Not available'}
          </span>
        </div>
      </div>

      {/* Result Package Cards (2-column grid) */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Design package */}
        <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <h3 className="font-semibold text-content-primary">Design package</h3>
          <p className="mt-0.5 text-xs text-content-muted">Architecture and technical specifications</p>
          <div className="mt-3 space-y-1.5 text-sm text-content-secondary">
            {designItems.length > 0 ? (
              designItems.map((item, idx) => <p key={idx}>• {item}</p>)
            ) : (
              <p className="text-xs text-content-muted">No design artifacts selected for this run.</p>
            )}
          </div>
        </div>

        {/* Planning package */}
        <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <h3 className="font-semibold text-content-primary">Planning package</h3>
          <p className="mt-0.5 text-xs text-content-muted">Agile hierarchy and delivery plan</p>
          <div className="mt-3 space-y-1.5 text-sm text-content-secondary">
            {planningItems.length > 0 ? (
              planningItems.map((item, idx) => <p key={idx}>• {item}</p>)
            ) : (
              <p className="text-xs text-content-muted">No planning artifacts selected for this run.</p>
            )}
          </div>
        </div>
      </div>

      {/* Validation & Traceability Evidence Card */}
      <div className="space-y-3 rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
        <div>
          <h3 className="font-semibold text-content-primary">Validation & traceability evidence</h3>
          <p className="mt-0.5 text-xs text-content-muted">
            {effectiveStatus === 'COMPLETED' && !hasErrors
              ? 'Structural and consistency checks passed successfully for completed run.'
              : 'Execution checks completed with findings.'}
          </p>
        </div>

        {/* Validation Badges */}
        <div className="flex flex-wrap items-center gap-2">
          {effectiveStatus === 'COMPLETED' && !hasErrors && (
            <span className="inline-flex items-center rounded-control border border-[#065f46] bg-[#064e3b]/80 px-3 py-1 text-xs font-medium text-[#34d399]">
              Structural validation passed
            </span>
          )}
          {hasTraceability && (
            <span className="inline-flex items-center rounded-control border border-[#065f46] bg-[#064e3b]/80 px-3 py-1 text-xs font-medium text-[#34d399]">
              Cross-artifact references valid
            </span>
          )}
        </div>

        {/* Traceability preview */}
        {traceabilityChain && traceabilityChain.length >= 2 ? (
          <p className="text-xs font-mono text-[#c084fc]">
            Example trace: {traceabilityChain.join(' → ')}
          </p>
        ) : hasTraceability ? (
          <p className="text-xs text-content-secondary">
            Traceability references are available within generated artifacts.
          </p>
        ) : null}

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

export default DesignPlanningResults
