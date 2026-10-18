import Button from '../../ui/Button.jsx'
import { downloadJiraPlan } from '../../../services/jiraPlanExport.js'
import ArtifactViewer from '../ArtifactViewer.jsx'
import ResultsWorkspace from '../ResultsWorkspace.jsx'
import ResultsOverview from './results/ResultsOverview.jsx'

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

function DesignPlanningResults(props) {
  if (props.mode === 'detail') {
    return (
      <DetailedResultsWorkspace
        outputs={props.outputs && typeof props.outputs === 'object' ? props.outputs : props.result?.outputs || {}}
        title={props.title}
        warnings={props.warnings}
        errors={props.errors}
        actions={props.actions}
      />
    )
  }

  return <ResultsOverview {...props} />
}

export default DesignPlanningResults
