import Button from '../../../ui/Button.jsx'

function getItemDetails(ref, tasksMap, storiesMap, featuresMap) {
  if (tasksMap[ref]) {
    return {
      id: ref,
      type: 'TASK',
      title: tasksMap[ref].title,
      points: tasksMap[ref].estimate_points,
      parent: tasksMap[ref].story_id,
      dependsOn: tasksMap[ref].depends_on,
    }
  }
  if (storiesMap[ref]) {
    const s = storiesMap[ref]
    return {
      id: ref,
      type: 'STORY',
      title: s.title || (s.actor ? `${s.actor} · ${s.goal}` : s.goal),
      points: s.estimate_points,
      parent: s.feature_id || s.epic_id,
    }
  }
  if (featuresMap[ref]) {
    return {
      id: ref,
      type: 'FEATURE',
      title: featuresMap[ref].title,
      parent: featuresMap[ref].epic_id,
    }
  }
  return { id: ref }
}

function SprintPlan({
  outputs,
  project,
  inputs,
  run,
  title = 'Sprint Plan',
  subtitle = 'Heuristic recommendation using team count, duration, dependencies and estimated workload',
  onBackToOverview,
  onViewPlanningHierarchy,
}) {
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : {}
  const sprints = Array.isArray(safeOutputs.SPRINT_PLAN) ? safeOutputs.SPRINT_PLAN : []

  // Check if planning hierarchy is available
  const hasPlanningHierarchy = Boolean(
    safeOutputs.PRODUCT_BACKLOG ||
      safeOutputs.EPICS ||
      safeOutputs.FEATURES ||
      safeOutputs.USER_STORIES ||
      safeOutputs.TASKS,
  )

  if (sprints.length === 0) {
    return (
      <section aria-labelledby="sprint-plan-title" className="space-y-6">
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
            <h2 id="sprint-plan-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
              {title}
            </h2>
            <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
          </div>
          <div className="flex items-center gap-3 pt-1">
            <span className="inline-flex items-center rounded-control border border-[#854d0e] bg-[#78350f]/60 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#fde047]">
              Estimate only
            </span>
            {onBackToOverview && (
              <Button variant="outline" size="small" onClick={onBackToOverview}>
                ← Back to Results Overview
              </Button>
            )}
          </div>
        </div>

        {/* Empty state card */}
        <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-8 text-center space-y-3">
          <h3 className="font-semibold text-content-primary">No sprint plan generated</h3>
          <p className="text-sm text-content-muted">No sprint plan was generated for this run.</p>
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

  // Build lookup maps for artifact enrichment from real returned artifacts only
  const tasksMap = {}
  if (Array.isArray(safeOutputs.TASKS)) {
    for (const t of safeOutputs.TASKS) {
      if (t?.id) tasksMap[t.id] = t
    }
  }

  const storiesMap = {}
  if (Array.isArray(safeOutputs.USER_STORIES)) {
    for (const s of safeOutputs.USER_STORIES) {
      if (s?.id) storiesMap[s.id] = s
    }
  }

  const featuresMap = {}
  if (Array.isArray(safeOutputs.FEATURES)) {
    for (const f of safeOutputs.FEATURES) {
      if (f?.id) featuresMap[f.id] = f
    }
  }

  // Contextual inputs
  const teamCount = inputs?.development_team_count || run?.input_snapshot?.development_team_count
  const expectedDuration = inputs?.expected_project_duration || run?.input_snapshot?.expected_project_duration

  // Collect warnings across sprints
  const allSprintWarnings = []
  let hasCapacityOverflow = false
  let hasSequencingWarning = false
  let hasDurationWarning = false

  for (const s of sprints) {
    if (s.planned_points !== undefined && s.capacity_points !== undefined && s.planned_points > s.capacity_points) {
      hasCapacityOverflow = true
    }
    if (Array.isArray(s.planning_warnings)) {
      for (const w of s.planning_warnings) {
        allSprintWarnings.push({ sprintId: s.id, sprintName: s.name, warning: w })
        const lower = w.toLowerCase()
        if (lower.includes('exceeds capacity') || lower.includes('overflow')) {
          hasCapacityOverflow = true
        }
        if (lower.includes('priority') || lower.includes('sequencing') || lower.includes('dependency')) {
          hasSequencingWarning = true
        }
        if (lower.includes('duration') || lower.includes('outside')) {
          hasDurationWarning = true
        }
      }
    }
  }

  const estimateBasis =
    sprints[0]?.estimate_basis ||
    'Estimated capacity uses team count × sprint duration in days.'

  return (
    <section aria-labelledby="sprint-plan-title" className="space-y-6">
      {/* Top breadcrumb bar matching S2-09 PNG */}
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

      {/* Header row with Title, Subtitle, and Estimate only badge matching PNG */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <h2 id="sprint-plan-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
            {title}
          </h2>
          <p className="mt-1 text-sm text-content-muted">{subtitle}</p>
        </div>
        <div className="flex items-center gap-3 pt-1">
          <span className="inline-flex items-center rounded-control border border-[#854d0e] bg-[#78350f]/60 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#fde047]">
            Estimate only
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
        </div>
      </div>

      {/* Sprint Cards Row / Grid */}
      <div
        className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
        aria-label="Sprint schedule"
      >
        {sprints.map((sprint, idx) => {
          const sprintTitle = sprint.name || sprint.id || `Sprint ${idx + 1}`
          const durationText = sprint.duration_days ? `${sprint.duration_days} days` : null
          const teamText = teamCount ? `${teamCount} ${teamCount === 1 ? 'developer' : 'developers'}` : null
          const subtitleDetails = [durationText, teamText].filter(Boolean).join(' · ')

          const hasUtilization = typeof sprint.utilization_percent === 'number'
          const clampedUtilization = hasUtilization ? Math.min(100, Math.max(0, sprint.utilization_percent)) : 0
          const isOverCapacity = hasUtilization && sprint.utilization_percent > 100

          return (
            <article
              key={sprint.id || idx}
              className="flex flex-col justify-between rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-5 space-y-4"
            >
              <div className="space-y-3">
                {/* Sprint Header */}
                <div>
                  <h3 className="font-semibold text-content-primary text-base">{sprintTitle}</h3>
                  {subtitleDetails && (
                    <p className="mt-0.5 text-xs text-content-muted">{subtitleDetails}</p>
                  )}
                </div>

                {/* Capacity & Workload metrics */}
                <div className="space-y-1.5 text-xs text-content-secondary">
                  {sprint.capacity_points !== undefined && (
                    <p className="flex items-center gap-1.5">
                      <span className="text-[#a78bfa] font-bold" aria-hidden="true">•</span>
                      <span>Capacity estimate: {sprint.capacity_points} units</span>
                    </p>
                  )}
                  {sprint.planned_points !== undefined && (
                    <p className="flex items-center gap-1.5">
                      <span className="text-[#a78bfa] font-bold" aria-hidden="true">•</span>
                      <span>Planned workload: {sprint.planned_points} units</span>
                    </p>
                  )}
                  {hasUtilization && (
                    <div className="pt-1 space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-content-muted">Utilization:</span>
                        <span
                          className={`font-mono font-semibold ${
                            isOverCapacity ? 'text-state-danger' : 'text-[#34d399]'
                          }`}
                        >
                          {sprint.utilization_percent}%
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-[#2d1b4e]/80">
                        <div
                          role="progressbar"
                          aria-valuenow={sprint.utilization_percent}
                          aria-valuemin="0"
                          aria-valuemax="100"
                          className={`h-full transition-all duration-300 ${
                            isOverCapacity ? 'bg-state-danger' : 'bg-[#34d399]'
                          }`}
                          style={{ width: `${clampedUtilization}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Assigned Items */}
                {Array.isArray(sprint.item_refs) && sprint.item_refs.length > 0 && (
                  <div className="pt-2 border-t border-[#2d1b4e]/50 space-y-2">
                    <span className="text-xs font-semibold text-content-muted uppercase tracking-wider">
                      Assigned items ({sprint.item_refs.length})
                    </span>
                    <ul className="space-y-1.5 font-mono text-xs">
                      {sprint.item_refs.map((ref) => {
                        const item = getItemDetails(ref, tasksMap, storiesMap, featuresMap)
                        return (
                          <li
                            key={ref}
                            className="flex flex-wrap items-baseline gap-1.5 text-content-secondary bg-[#110722]/60 px-2 py-1 rounded-control border border-[#2d1b4e]/30"
                          >
                            <span className="font-semibold text-content-primary">{item.id}</span>
                            {item.title && (
                              <>
                                <span>·</span>
                                <span className="font-sans text-content-secondary truncate max-w-[200px]">
                                  {item.title}
                                </span>
                              </>
                            )}
                            {item.points !== undefined && (
                              <span className="text-[#a78bfa] text-[11px] ml-auto">
                                {item.points} pts
                              </span>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}

                {/* Dependency Notes */}
                {Array.isArray(sprint.dependency_notes) && sprint.dependency_notes.length > 0 && (
                  <div className="pt-2 border-t border-[#2d1b4e]/50 space-y-1">
                    <span className="text-xs font-semibold text-content-muted">Dependencies:</span>
                    <ul className="list-disc pl-4 space-y-0.5 text-xs text-content-muted">
                      {sprint.dependency_notes.map((note, idxNote) => (
                        <li key={idxNote}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Sprint-level warnings */}
                {Array.isArray(sprint.planning_warnings) && sprint.planning_warnings.length > 0 && (
                  <div className="pt-2 border-t border-[#2d1b4e]/50 space-y-1">
                    <span className="text-xs font-semibold text-state-warning">Sprint notices:</span>
                    <ul className="space-y-0.5 text-xs text-content-muted">
                      {sprint.planning_warnings.map((warning, idxW) => (
                        <li key={idxW} className="text-state-warning/90">
                          • {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </article>
          )
        })}
      </div>

      {/* Planning rationale & warnings Card matching PNG */}
      <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-5 space-y-4">
        <div>
          <h3 className="font-semibold text-content-primary">Planning rationale & warnings</h3>
          <p className="mt-0.5 text-xs text-content-muted">
            Transparent heuristic — not mathematical optimization.
          </p>
        </div>

        {/* Heuristic Badges / Chips matching PNG */}
        <div className="flex flex-wrap items-center gap-2">
          {!hasSequencingWarning ? (
            <span className="inline-flex items-center rounded-control border border-[#065f46] bg-[#064e3b]/80 px-3 py-1 text-xs font-medium text-[#34d399]">
              Dependencies scheduled in order
            </span>
          ) : (
            <span className="inline-flex items-center rounded-control border border-state-warning/40 bg-state-warning/20 px-3 py-1 text-xs font-medium text-state-warning">
              Dependency sequencing review needed
            </span>
          )}

          {!hasCapacityOverflow ? (
            <span className="inline-flex items-center rounded-control border border-[#065f46] bg-[#064e3b]/80 px-3 py-1 text-xs font-medium text-[#34d399]">
              No sprint capacity overflow detected
            </span>
          ) : (
            <span className="inline-flex items-center rounded-control border border-state-warning/40 bg-state-warning/20 px-3 py-1 text-xs font-medium text-state-warning">
              Sprint capacity overflow detected
            </span>
          )}

          {!hasDurationWarning ? (
            <span className="inline-flex items-center rounded-control border border-[#1e3a8a] bg-[#1e293b] px-3 py-1 text-xs font-medium text-[#38bdf8]">
              Expected {expectedDuration || 'project'} duration appears feasible for this estimate
            </span>
          ) : (
            <span className="inline-flex items-center rounded-control border border-state-warning/40 bg-state-warning/20 px-3 py-1 text-xs font-medium text-state-warning">
              Expected project duration constraint exceeded
            </span>
          )}
        </div>

        {/* Specific Warnings Callout if present */}
        {allSprintWarnings.length > 0 && (
          <div className="rounded-control border border-state-warning/40 bg-state-warning/10 p-3 space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-state-warning">
              Heuristic notices & warnings
            </h4>
            <ul className="space-y-1 text-xs text-content-secondary">
              {allSprintWarnings.map((item, idx) => (
                <li key={idx}>
                  • <span className="font-semibold">{item.sprintName || item.sprintId}:</span> {item.warning}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Capacity basis note matching PNG */}
        <p className="text-xs text-content-muted leading-relaxed">
          Capacity basis: development_team_count × sprint_duration_days. Values are neutral planning units, not guaranteed Scrum story points or delivery commitments.
          {estimateBasis && (
            <span className="block mt-1 text-content-muted/80">
              Backend basis: {estimateBasis}
            </span>
          )}
        </p>
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
      </div>
    </section>
  )
}

export default SprintPlan
