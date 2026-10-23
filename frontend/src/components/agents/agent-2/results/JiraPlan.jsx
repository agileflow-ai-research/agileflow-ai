import Button from '../../../ui/Button.jsx'
import { downloadJiraPlan } from '../../../../services/jiraPlanExport.js'
import JiraIntegrationSection from '../../../../features/agents/designPlanning/components/JiraIntegrationSection.jsx'

function formatPriority(priority) {
  if (!priority) return null
  switch (priority.toUpperCase()) {
    case 'HIGHEST':
      return 'Highest'
    case 'HIGH':
      return 'High'
    case 'MEDIUM':
      return 'Medium'
    case 'LOW':
      return 'Low'
    case 'LOWEST':
      return 'Lowest'
    default:
      return priority
  }
}

function getItemPriority(item, prioritiesMap, storiesMap) {
  if (prioritiesMap[item.id]) {
    return formatPriority(prioritiesMap[item.id])
  }
  if (item.priority) {
    return formatPriority(item.priority)
  }
  if (item.story_id && storiesMap[item.story_id]?.priority) {
    return formatPriority(storiesMap[item.story_id].priority)
  }
  return null
}

function getItemSprint(item, sprintItemMap, taskSprintMap, storiesMap, sprintsMap) {
  // Check direct sprint item_refs
  if (sprintItemMap[item.id]) {
    const s = sprintsMap[sprintItemMap[item.id]]
    return s?.name || sprintItemMap[item.id]
  }
  // Check task assignment sprint_id
  if (taskSprintMap[item.id]) {
    const s = sprintsMap[taskSprintMap[item.id]]
    return s?.name || taskSprintMap[item.id]
  }
  // Check parent story sprint
  if (item.story_id && sprintItemMap[item.story_id]) {
    const s = sprintsMap[sprintItemMap[item.story_id]]
    return s?.name || sprintItemMap[item.story_id]
  }
  return null
}

function JiraPlan({
  title = 'Jira-compatible Plan',
  subtitle = 'Structured export for Progress Presentation 1 — no Jira Cloud dependency',
  result,
  run,
  outputs,
  warnings = [],
  errors = [],
  project,
  onBackToOverview,
  onViewPlanningHierarchy,
  onViewSprintPlan,
  onViewTaskAssignment,
  onViewValidationHistory,
}) {
  const safeOutputs =
    outputs && typeof outputs === 'object'
      ? outputs
      : result?.outputs || run?.output_manifest || {}

  const jiraPlan = safeOutputs.JIRA_PLAN

  const hasPlanningHierarchy = Boolean(
    safeOutputs.EPICS ||
      safeOutputs.USER_STORIES ||
      safeOutputs.TASKS ||
      safeOutputs.PRODUCT_BACKLOG,
  )
  const hasSprintPlan = Boolean(
    safeOutputs.SPRINT_PLAN &&
      (!Array.isArray(safeOutputs.SPRINT_PLAN) || safeOutputs.SPRINT_PLAN.length > 0),
  )
  const hasTaskAssignment = Boolean(
    safeOutputs.TASK_ASSIGNMENT &&
      (!Array.isArray(safeOutputs.TASK_ASSIGNMENT) || safeOutputs.TASK_ASSIGNMENT.length > 0),
  )

  // Empty state when JIRA_PLAN output is missing
  if (!jiraPlan || typeof jiraPlan !== 'object') {
    return (
      <section aria-labelledby="jira-plan-title" className="space-y-6">
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

        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
          <div>
            <h2 id="jira-plan-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
              {title}
            </h2>
            <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
          </div>
          {onBackToOverview && (
            <Button variant="outline" size="small" onClick={onBackToOverview}>
              ← Back to Results Overview
            </Button>
          )}
        </div>

        <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-8 text-center space-y-3">
          <h3 className="font-semibold text-content-primary">No Jira-compatible plan generated</h3>
          <p className="text-sm text-content-muted">No Jira-compatible plan was generated for this run.</p>
          <div className="pt-2 flex justify-center gap-3">
            {onBackToOverview && (
              <Button variant="primary" onClick={onBackToOverview}>
                Back to Results Overview
              </Button>
            )}
            {onViewPlanningHierarchy && hasPlanningHierarchy && (
              <Button variant="outline" onClick={onViewPlanningHierarchy}>
                Back to Planning Hierarchy
              </Button>
            )}
          </div>
        </div>
      </section>
    )
  }

  // Extract arrays truthfully from real JIRA_PLAN backend schema
  const epics = Array.isArray(jiraPlan.epics) ? jiraPlan.epics : []
  const stories = Array.isArray(jiraPlan.stories) ? jiraPlan.stories : []
  const tasks = Array.isArray(jiraPlan.tasks) ? jiraPlan.tasks : []
  const sprints = Array.isArray(jiraPlan.sprints) ? jiraPlan.sprints : []
  const assignments = Array.isArray(jiraPlan.assignments) ? jiraPlan.assignments : []
  const priorities = Array.isArray(jiraPlan.priorities) ? jiraPlan.priorities : []
  const syncStatus = jiraPlan.synchronization || 'NOT_PERFORMED'

  // Lookup maps
  const prioritiesMap = {}
  for (const p of priorities) {
    if (p?.item_id) prioritiesMap[p.item_id] = p.priority
  }

  const sprintsMap = {}
  const sprintItemMap = {}
  for (const s of sprints) {
    if (s?.id) {
      sprintsMap[s.id] = s
      if (Array.isArray(s.item_refs)) {
        for (const ref of s.item_refs) {
          sprintItemMap[ref] = s.id
        }
      }
    }
  }

  const taskSprintMap = {}
  for (const a of assignments) {
    if (a?.task_id && a.sprint_id) {
      taskSprintMap[a.task_id] = a.sprint_id
    }
  }

  const storiesMap = {}
  for (const s of stories) {
    if (s?.id) storiesMap[s.id] = s
  }

  // Construct hierarchical rows matching Jira standard (Epic -> Stories -> Tasks)
  const rows = []
  const processedStoryIds = new Set()
  const processedTaskIds = new Set()

  if (epics.length > 0) {
    for (const epic of epics) {
      rows.push({
        type: 'Epic',
        key: epic.id,
        summary: epic.title || epic.name || epic.description || epic.id,
        item: epic,
      })

      // Child stories
      const childStories = stories.filter((s) => s.epic_id === epic.id)
      for (const story of childStories) {
        processedStoryIds.add(story.id)
        rows.push({
          type: 'Story',
          key: story.id,
          summary: story.title || (story.goal ? (story.actor ? `${story.actor} · ${story.goal}` : story.goal) : story.id),
          item: story,
        })

        // Child tasks
        const childTasks = tasks.filter((t) => t.story_id === story.id)
        for (const task of childTasks) {
          processedTaskIds.add(task.id)
          rows.push({
            type: 'Task',
            key: task.id,
            summary: task.title || task.name || task.id,
            item: task,
          })
        }
      }
    }
  }

  // Remaining unlinked stories
  for (const story of stories) {
    if (!processedStoryIds.has(story.id)) {
      rows.push({
        type: 'Story',
        key: story.id,
        summary: story.title || (story.goal ? (story.actor ? `${story.actor} · ${story.goal}` : story.goal) : story.id),
        item: story,
      })

      const childTasks = tasks.filter((t) => t.story_id === story.id)
      for (const task of childTasks) {
        processedTaskIds.add(task.id)
        rows.push({
          type: 'Task',
          key: task.id,
          summary: task.title || task.name || task.id,
          item: task,
        })
      }
    }
  }

  // Remaining unlinked tasks
  for (const task of tasks) {
    if (!processedTaskIds.has(task.id)) {
      rows.push({
        type: 'Task',
        key: task.id,
        summary: task.title || task.name || task.id,
        item: task,
      })
    }
  }

  return (
    <section aria-labelledby="jira-plan-title" className="space-y-6">
      {/* Top breadcrumb bar matching S2-11 PNG */}
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

      {/* Header row with Title, Subtitle, and NOT SYNCHRONIZED badge matching PNG */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <h2 id="jira-plan-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
            {title}
          </h2>
          <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
        </div>
        <div className="flex items-center gap-3 pt-1">
          <span className="inline-flex items-center rounded-control border border-[#854d0e] bg-[#78350f]/60 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#fde047]">
            NOT SYNCHRONIZED
          </span>
          {onBackToOverview && (
            <Button variant="outline" size="small" onClick={onBackToOverview}>
              ← Back to Results Overview
            </Button>
          )}
          {onViewPlanningHierarchy && hasPlanningHierarchy && (
            <Button variant="outline" size="small" onClick={onViewPlanningHierarchy}>
              Planning Hierarchy
            </Button>
          )}
          {onViewSprintPlan && hasSprintPlan && (
            <Button variant="outline" size="small" onClick={onViewSprintPlan}>
              Sprint Plan
            </Button>
          )}
          {onViewTaskAssignment && hasTaskAssignment && (
            <Button variant="outline" size="small" onClick={onViewTaskAssignment}>
              Task Assignments
            </Button>
          )}
          {onViewValidationHistory && (
            <Button variant="outline" size="small" onClick={onViewValidationHistory}>
              Validation & History
            </Button>
          )}
        </div>
      </div>

      {/* Synchronization Banner matching S2-11 PNG */}
      <div className="rounded-panel border border-[#854d0e]/70 bg-[#451a03]/40 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-sm">
        <div className="font-bold text-[#fde047] tracking-tight text-base sm:text-sm">
          Synchronization: {syncStatus}
        </div>
        <div className="text-xs sm:text-sm text-content-secondary">
          No Jira credentials or remote API calls are used in the standalone MVP.
        </div>
      </div>

      {/* Summary Metrics (5 cards) matching S2-11 PNG */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" aria-label="Jira plan metrics">
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Epics</span>
          <span className="mt-2 text-2xl font-bold text-content-primary">{epics.length}</span>
        </div>
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Stories</span>
          <span className="mt-2 text-2xl font-bold text-content-primary">{stories.length}</span>
        </div>
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Tasks</span>
          <span className="mt-2 text-2xl font-bold text-content-primary">{tasks.length}</span>
        </div>
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Sprints</span>
          <span className="mt-2 text-2xl font-bold text-content-primary">{sprints.length}</span>
        </div>
        <div className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-4">
          <span className="text-xs text-content-muted">Assignments</span>
          <span className="mt-2 text-2xl font-bold text-content-primary">{assignments.length}</span>
        </div>
      </div>

      {/* Jira-ready structure Card matching S2-11 PNG */}
      <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-5 space-y-4">
        <div>
          <h3 className="font-semibold text-content-primary text-base">Jira-ready structure</h3>
          <p className="mt-0.5 text-xs text-content-muted">Persisted JIRA_PLAN output</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm" aria-label="Jira-ready structure table">
            <thead>
              <tr className="border-b border-[#2d1b4e]/80 text-xs text-content-muted font-medium">
                <th scope="col" className="pb-3 pr-4 font-medium">Type</th>
                <th scope="col" className="pb-3 pr-4 font-medium">Key</th>
                <th scope="col" className="pb-3 pr-4 font-medium">Summary</th>
                <th scope="col" className="pb-3 font-medium text-right sm:text-left">Priority / Sprint</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2d1b4e]/40">
              {rows.map((row) => {
                const priorityText = getItemPriority(row.item, prioritiesMap, storiesMap)
                const sprintText = getItemSprint(row.item, sprintItemMap, taskSprintMap, storiesMap, sprintsMap)
                const prioritySprint = [priorityText, sprintText].filter(Boolean).join(' · ')

                let typeColor = 'text-content-secondary'
                if (row.type === 'Epic') {
                  typeColor = 'text-[#c084fc]'
                } else if (row.type === 'Story') {
                  typeColor = 'text-[#60a5fa]'
                } else if (row.type === 'Task') {
                  typeColor = 'text-[#34d399]'
                }

                return (
                  <tr key={`${row.type}-${row.key}`} className="hover:bg-canvas/40 transition-colors">
                    <td className={`py-3 pr-4 font-medium text-xs ${typeColor}`}>
                      {row.type}
                    </td>
                    <td className="py-3 pr-4 font-mono text-xs font-semibold text-content-primary">
                      {row.key}
                    </td>
                    <td className="py-3 pr-4 text-content-secondary text-sm">
                      {row.summary}
                    </td>
                    <td className="py-3 text-right sm:text-left text-xs font-medium text-[#fde047]">
                      {prioritySprint || '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Truthful Warnings & Errors */}
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

      {/* Bottom Actions matching S2-11 PNG */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <Button
          variant="primary"
          onClick={() => downloadJiraPlan(jiraPlan)}
        >
          Download Jira-compatible JSON
        </Button>
        {onBackToOverview && (
          <Button variant="outline" onClick={onBackToOverview}>
            View persisted run
          </Button>
        )}
      </div>

      {/* Jira Cloud Integration & Resource Selection */}
      <JiraIntegrationSection project={project} />
    </section>
  )
}

export default JiraPlan
