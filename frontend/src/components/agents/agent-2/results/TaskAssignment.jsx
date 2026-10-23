import Button from '../../../ui/Button.jsx'

function formatConfidence(assignment) {
  if (assignment.confidence !== undefined && assignment.confidence !== null) {
    return assignment.confidence
  }
  if (assignment.confidence_score !== undefined && assignment.confidence_score !== null) {
    return assignment.confidence_score
  }
  return null
}

function getMatchReasonsText(assignment) {
  if (Array.isArray(assignment.matching_reasons) && assignment.matching_reasons.length > 0) {
    return assignment.matching_reasons.join(' · ')
  }
  const parts = []
  if (assignment.role_match && assignment.role) {
    parts.push(`${assignment.role} role`)
  }
  if (Array.isArray(assignment.skill_matches) && assignment.skill_matches.length > 0) {
    parts.push(...assignment.skill_matches)
  }
  if (parts.length > 0) {
    return parts.join(' · ')
  }
  if (assignment.rationale) {
    return assignment.rationale
  }
  return null
}

function TaskAssignment({
  outputs,
  project,
  inputs,
  run,
  title = 'Task Assignment Recommendations',
  subtitle = 'Skill-aware heuristic using supplied roles, skills, dependencies and current workload',
  onBackToOverview,
  onViewPlanningHierarchy,
  onViewSprintPlan,
  onViewJiraPlan,
  onViewValidationHistory,
}) {
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : {}
  const assignments = Array.isArray(safeOutputs.TASK_ASSIGNMENT) ? safeOutputs.TASK_ASSIGNMENT : []

  // Check if sibling planning views are available
  const hasPlanningHierarchy = Boolean(
    safeOutputs.PRODUCT_BACKLOG ||
      safeOutputs.EPICS ||
      safeOutputs.FEATURES ||
      safeOutputs.USER_STORIES ||
      safeOutputs.TASKS,
  )
  const hasSprintPlan = Boolean(
    safeOutputs.SPRINT_PLAN && (!Array.isArray(safeOutputs.SPRINT_PLAN) || safeOutputs.SPRINT_PLAN.length > 0),
  )
  const hasJiraPlan = Boolean(safeOutputs.JIRA_PLAN)

  if (assignments.length === 0) {
    return (
      <section aria-labelledby="task-assignment-title" className="space-y-6">
        {/* Top breadcrumb bar */}
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

        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
          <div>
            <h2 id="task-assignment-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
              {title}
            </h2>
            <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
          </div>
          <div className="flex items-center gap-3 pt-1">
            <span className="inline-flex items-center rounded-control border border-state-info/40 bg-state-info-soft px-3 py-1 text-xs font-semibold text-state-info">
              Explainable
            </span>
            {onBackToOverview && (
              <Button variant="outline" size="small" onClick={onBackToOverview}>
                ← Back to Results Overview
              </Button>
            )}
          </div>
        </div>

        {/* Empty state card */}
        <div className="rounded-panel border border-default bg-surface p-8 text-center space-y-3">
          <h3 className="font-semibold text-content-primary">No task assignments generated</h3>
          <p className="text-sm text-content-muted">No task assignment recommendations were generated for this run.</p>
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
            {onViewSprintPlan && hasSprintPlan && (
              <Button variant="outline" onClick={onViewSprintPlan}>
                Back to Sprint Plan
              </Button>
            )}
          </div>
        </div>
      </section>
    )
  }

  // Lookup map for task enrichment
  const tasksMap = {}
  if (Array.isArray(safeOutputs.TASKS)) {
    for (const t of safeOutputs.TASKS) {
      if (t?.id) tasksMap[t.id] = t
    }
  }

  const hasNamedDevelopers = Boolean(
    inputs?.team_composition ||
      run?.input_snapshot?.team_composition ||
      assignments.some(
        (a) =>
          a.team_slot &&
          !a.team_slot.startsWith('Team member') &&
          !a.team_slot.toLowerCase().includes('slot') &&
          !a.team_slot.toLowerCase().includes('developer'),
      ),
  )

  return (
    <section aria-labelledby="task-assignment-title" className="space-y-6">
      {/* Top breadcrumb bar matching S2-10 PNG */}
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

      {/* Header row with Title, Subtitle, and Explainable badge matching PNG */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <h2 id="task-assignment-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
            {title}
          </h2>
          <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
        </div>
        <div className="flex items-center gap-3 pt-1">
          <span className="inline-flex items-center rounded-control border border-state-info/40 bg-state-info-soft px-3 py-1 text-xs font-semibold text-state-info">
            Explainable
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
          {onViewJiraPlan && hasJiraPlan && (
            <Button variant="outline" size="small" onClick={onViewJiraPlan}>
              Jira Plan
            </Button>
          )}
          {onViewValidationHistory && (
            <Button variant="outline" size="small" onClick={onViewValidationHistory}>
              Validation & History
            </Button>
          )}
        </div>
      </div>

      {/* Recommended assignments Card matching S2-10 PNG */}
      <div className="rounded-panel border border-default bg-surface p-5 space-y-4">
        <div>
          <h3 className="font-semibold text-content-primary text-base">Recommended assignments</h3>
          <p className="mt-0.5 text-xs text-content-muted">
            {hasNamedDevelopers
              ? 'Named developers are used only because team_composition was supplied.'
              : 'Generic planning slots are used because team_composition was not supplied.'}
          </p>
        </div>

        {/* Table layout matching PNG */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs" aria-label="Task assignments">
            <thead>
              <tr className="border-b border-default text-content-muted">
                <th className="pb-3 font-semibold">Task</th>
                <th className="pb-3 font-semibold">Recommendation</th>
                <th className="pb-3 font-semibold">Match reasons</th>
                <th className="pb-3 font-semibold text-right">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default/60">
              {assignments.map((assignment, idx) => {
                const task = tasksMap[assignment.task_id]
                const taskTitle = task?.title ? `${assignment.task_id} · ${task.title}` : assignment.task_id
                const taskDependencies = Array.isArray(assignment.depends_on)
                  ? assignment.depends_on
                  : Array.isArray(task?.depends_on)
                    ? task.depends_on
                    : []

                const confidenceValue = formatConfidence(assignment)
                const matchReasonsText = getMatchReasonsText(assignment)

                return (
                  <tr key={assignment.task_id || idx} className="hover:bg-elevated/40 transition-colors">
                    {/* Task Column */}
                    <td className="py-3.5 pr-4 align-top">
                      <div className="space-y-0.5">
                        <span className="font-medium text-content-primary">
                          {taskTitle}
                        </span>
                        {assignment.sprint_id && (
                          <div className="text-[11px] text-content-muted font-mono">
                            Sprint: <span className="text-content-secondary">{assignment.sprint_id}</span>
                          </div>
                        )}
                        {taskDependencies.length > 0 && (
                          <div className="text-[11px] text-content-muted">
                            Depends on{' '}
                            <span className="text-brand font-mono">
                              {taskDependencies.join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Recommendation Column */}
                    <td className="py-3.5 pr-4 align-top">
                      <div className="space-y-0.5">
                        <div className="font-medium text-content-primary">
                          {assignment.team_slot}
                          {assignment.role && (
                            <span className="text-content-muted font-normal"> · {assignment.role}</span>
                          )}
                        </div>
                        {assignment.workload_points_before !== undefined && (
                          <div className="text-[11px] text-content-muted">
                            Workload before: {assignment.workload_points_before} pts
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Match reasons Column */}
                    <td className="py-3.5 pr-4 align-top text-content-secondary">
                      <div className="space-y-1">
                        {matchReasonsText && <span>{matchReasonsText}</span>}
                        {assignment.rationale && assignment.rationale !== matchReasonsText && (
                          <p className="text-[11px] text-content-muted">{assignment.rationale}</p>
                        )}
                      </div>
                    </td>

                    {/* Confidence Column */}
                    <td className="py-3.5 align-top text-right font-mono font-semibold text-state-success">
                      {confidenceValue !== null ? confidenceValue : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* When names are not supplied Card matching S2-10 PNG */}
      <div className="rounded-panel border border-default bg-surface p-5 space-y-2">
        <h3 className="font-semibold text-content-primary text-base">When names are not supplied</h3>
        <p className="text-xs text-content-secondary">
          Agent 2 never fabricates real employees.
        </p>
        <p className="text-xs text-content-muted">
          Example fallback: “Recommended team slot: Backend Developer” or “Team member 1” — clearly presented as a planning slot, not an actual assigned person.
        </p>
      </div>

      {/* Cyan research disclaimer banner matching S2-10 PNG */}
      <div className="rounded-panel border border-state-info/40 bg-state-info-soft p-4 text-xs text-state-info font-medium">
        These are explainable recommendations, not optimal resource-allocation claims.
      </div>

      {/* Bottom actions */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
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
        {onViewSprintPlan && hasSprintPlan && (
          <Button variant="outline" onClick={onViewSprintPlan}>
            Back to Sprint Plan
          </Button>
        )}
      </div>
    </section>
  )
}

export default TaskAssignment
