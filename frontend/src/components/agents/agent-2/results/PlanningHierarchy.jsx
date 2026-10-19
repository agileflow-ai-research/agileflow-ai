import Button from '../../../ui/Button.jsx'

function formatPriority(priority) {
  if (!priority) return ''
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

function getStoryTitle(story) {
  if (story.title) return story.title
  if (story.goal) {
    if (story.actor) {
      return `${story.actor} · ${story.goal}`
    }
    return story.goal
  }
  return 'Untitled Story'
}

function PlanningHierarchy({
  title = 'Agile Planning Hierarchy',
  subtitle = 'Epic → Feature → User Story → Task with stable IDs and source references',
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

  const epics = Array.isArray(safeOutputs.EPICS)
    ? safeOutputs.EPICS
    : Array.isArray(safeOutputs.JIRA_PLAN?.epics)
      ? safeOutputs.JIRA_PLAN.epics
      : []

  const features = Array.isArray(safeOutputs.FEATURES) ? safeOutputs.FEATURES : []

  const stories = Array.isArray(safeOutputs.USER_STORIES)
    ? safeOutputs.USER_STORIES
    : Array.isArray(safeOutputs.JIRA_PLAN?.stories)
      ? safeOutputs.JIRA_PLAN.stories
      : []

  const tasks = Array.isArray(safeOutputs.TASKS)
    ? safeOutputs.TASKS
    : Array.isArray(safeOutputs.JIRA_PLAN?.tasks)
      ? safeOutputs.JIRA_PLAN.tasks
      : []

  const backlog = Array.isArray(safeOutputs.PRODUCT_BACKLOG) ? safeOutputs.PRODUCT_BACKLOG : []

  const hasPlanningOutputs =
    epics.length > 0 ||
    features.length > 0 ||
    stories.length > 0 ||
    tasks.length > 0 ||
    backlog.length > 0

  // Build relationships safely based on actual reference fields returned by backend
  const epicIds = new Set(epics.map((e) => e.id))
  const featureIds = new Set(features.map((f) => f.id))
  const storyIds = new Set(stories.map((s) => s.id))

  // Unlinked items detection
  const unlinkedFeatures =
    epics.length > 0
      ? features.filter((f) => !epicIds.has(f.epic_id))
      : []

  const unlinkedStories =
    features.length > 0
      ? stories.filter((s) => !featureIds.has(s.feature_id))
      : epics.length > 0
        ? stories.filter((s) => !epicIds.has(s.epic_id))
        : []

  const unlinkedTasks =
    stories.length > 0
      ? tasks.filter((t) => !storyIds.has(t.story_id))
      : features.length > 0
        ? tasks.filter((t) => !featureIds.has(t.feature_id))
        : epics.length > 0
          ? tasks.filter((t) => !epicIds.has(t.epic_id))
          : tasks

  const hasUnlinked =
    unlinkedFeatures.length > 0 || unlinkedStories.length > 0 || unlinkedTasks.length > 0

  return (
    <section aria-labelledby="planning-hierarchy-heading" className="space-y-6">
      {/* Top breadcrumb bar matching S2-08 PNG */}
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

      {/* Header with Hierarchy valid badge matching PNG */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            id="planning-hierarchy-heading"
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
                ? 'border-state-danger/40 bg-state-danger/10 text-state-danger'
                : 'border-[#065f46] bg-[#064e3b]/80 text-[#34d399]'
            }`}
          >
            {isFailed ? 'Validation findings' : 'Hierarchy valid'}
          </span>
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

      {/* Empty state if no planning hierarchy outputs were returned */}
      {!hasPlanningOutputs && (
        <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-8 text-center">
          <p className="text-sm text-content-muted">
            No planning hierarchy artifacts were generated for this run.
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

      {/* Product Backlog (only if returned by backend) */}
      {backlog.length > 0 && (
        <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-5 space-y-3">
          <div>
            <h3 className="font-semibold text-content-primary">Product backlog</h3>
            <p className="mt-0.5 text-xs text-content-muted">
              {backlog.length} prioritized backlog {backlog.length === 1 ? 'item' : 'items'}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="Product backlog items">
              <thead>
                <tr className="border-b border-[#2d1b4e] text-content-muted">
                  <th className="pb-2 font-medium">ID</th>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Title</th>
                  <th className="pb-2 font-medium">Priority</th>
                  <th className="pb-2 font-medium">Parent</th>
                  <th className="pb-2 font-medium">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2d1b4e]/50 font-mono">
                {backlog.map((item, idx) => (
                  <tr key={item.item_id || idx} className="hover:bg-[#1f123d]/40 transition-colors">
                    <td className="py-2 text-content-primary font-semibold">{item.item_id}</td>
                    <td className="py-2 text-content-muted">{item.item_type}</td>
                    <td className="py-2 font-sans text-content-secondary">{item.title}</td>
                    <td className="py-2 text-content-secondary">{formatPriority(item.priority)}</td>
                    <td className="py-2 text-content-muted">{item.parent_id || '—'}</td>
                    <td className="py-2 text-content-muted">{item.source_refs?.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Main Hierarchy Card matching S2-08 PNG */}
      {(epics.length > 0 || features.length > 0 || stories.length > 0 || tasks.length > 0) && (
        <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-5 space-y-4">
          <div>
            <h3 className="font-semibold text-content-primary">Product backlog hierarchy</h3>
            <p className="mt-0.5 text-xs text-content-muted">
              {epics.length > 0 && `${epics.length} ${epics.length === 1 ? 'epic' : 'epics'}`}
              {features.length > 0 && ` · ${features.length} ${features.length === 1 ? 'feature' : 'features'}`}
              {stories.length > 0 && ` · ${stories.length} ${stories.length === 1 ? 'story' : 'stories'}`}
              {tasks.length > 0 && ` · ${tasks.length} ${tasks.length === 1 ? 'task' : 'tasks'}`}
            </p>
          </div>

          <div className="space-y-4" aria-label="Planning hierarchy tree">
            {/* If Epics exist: render Epic tree */}
            {epics.length > 0 &&
              epics.map((epic) => {
                const epicFeatures = features.filter((f) => f.epic_id === epic.id)
                const directStories =
                  features.length === 0 ? stories.filter((s) => s.epic_id === epic.id) : []

                return (
                  <div
                    key={epic.id}
                    className="rounded-control border border-[#7c3aed]/50 bg-[#1f103d]/70 p-4 space-y-3"
                  >
                    <div>
                      <h4 className="font-semibold text-content-primary text-sm sm:text-base">
                        {epic.id} · {epic.title}
                      </h4>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-content-muted">
                        {Array.isArray(epic.source_refs) && epic.source_refs.length > 0 && (
                          <span>
                            Source:{' '}
                            <span className="font-mono text-content-secondary">
                              {epic.source_refs.join(', ')}
                            </span>
                          </span>
                        )}
                        {Array.isArray(epic.source_refs) && epic.source_refs.length > 0 && epic.priority && (
                          <span>·</span>
                        )}
                        {epic.priority && (
                          <span>
                            Priority:{' '}
                            <span className="font-medium text-content-secondary">
                              {formatPriority(epic.priority)}
                            </span>
                          </span>
                        )}
                      </div>
                      {epic.outcome && (
                        <p className="mt-2 text-xs text-content-secondary">{epic.outcome}</p>
                      )}
                    </div>

                    {/* Features under Epic */}
                    {epicFeatures.map((feat) => {
                      const featStories = stories.filter((s) => s.feature_id === feat.id)

                      return (
                        <div
                          key={feat.id}
                          className="rounded-control border border-[#4c1d95]/40 bg-[#160b2d]/80 p-3.5 space-y-2.5 mt-3"
                        >
                          <div>
                            <h5 className="font-semibold text-content-primary text-sm">
                              {feat.id} · {feat.title}
                            </h5>
                            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-content-muted">
                              <span>
                                Parent:{' '}
                                <span className="font-mono text-content-secondary">{feat.epic_id}</span>
                              </span>
                              {Array.isArray(feat.source_refs) && feat.source_refs.length > 0 && (
                                <>
                                  <span>·</span>
                                  <span>
                                    Source:{' '}
                                    <span className="font-mono text-content-secondary">
                                      {feat.source_refs.join(', ')}
                                    </span>
                                  </span>
                                </>
                              )}
                            </div>
                            {feat.description && (
                              <p className="mt-1.5 text-xs text-content-secondary">{feat.description}</p>
                            )}
                          </div>

                          {/* Stories under Feature */}
                          {featStories.map((story) => {
                            const storyTasks = tasks.filter((t) => t.story_id === story.id)

                            return (
                              <div
                                key={story.id}
                                className="rounded-control border border-[#2d1b4e] bg-[#110722] p-3 space-y-2 mt-2"
                              >
                                <div>
                                  <h6 className="font-medium text-content-primary text-xs sm:text-sm">
                                    {story.id} · {getStoryTitle(story)}
                                  </h6>
                                  <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-content-muted">
                                    <span>
                                      Parent:{' '}
                                      <span className="font-mono text-content-secondary">
                                        {story.feature_id || story.epic_id}
                                      </span>
                                    </span>
                                    {story.estimate_points && (
                                      <>
                                        <span>·</span>
                                        <span>
                                          Estimate:{' '}
                                          <span className="text-content-secondary">
                                            {story.estimate_points} workload units
                                          </span>
                                        </span>
                                      </>
                                    )}
                                    {Array.isArray(story.source_refs) && story.source_refs.length > 0 && (
                                      <>
                                        <span>·</span>
                                        <span>
                                          Source:{' '}
                                          <span className="font-mono text-content-secondary">
                                            {story.source_refs.join(', ')}
                                          </span>
                                        </span>
                                      </>
                                    )}
                                    {story.priority && (
                                      <>
                                        <span>·</span>
                                        <span>
                                          Priority:{' '}
                                          <span className="text-content-secondary">
                                            {formatPriority(story.priority)}
                                          </span>
                                        </span>
                                      </>
                                    )}
                                  </div>

                                  {Array.isArray(story.acceptance_criteria) &&
                                    story.acceptance_criteria.length > 0 && (
                                      <div className="mt-2 text-xs">
                                        <span className="font-medium text-content-secondary">
                                          Acceptance criteria:
                                        </span>
                                        <ul className="list-disc pl-4 mt-0.5 space-y-0.5 text-content-muted">
                                          {story.acceptance_criteria.map((ac, acIdx) => (
                                            <li key={acIdx}>{ac}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                </div>

                                {/* Tasks under Story */}
                                {storyTasks.length > 0 && (
                                  <div className="pt-2 border-t border-[#2d1b4e]/50 space-y-1.5 font-mono text-xs">
                                    {storyTasks.map((task) => (
                                      <div
                                        key={task.id}
                                        className="text-content-secondary flex flex-wrap items-baseline gap-1.5"
                                      >
                                        <span className="font-semibold text-content-primary">
                                          {task.id}
                                        </span>
                                        <span>·</span>
                                        <span className="font-sans text-content-secondary">
                                          {task.title}
                                        </span>
                                        <span>·</span>
                                        <span className="text-content-muted">
                                          Parent:{' '}
                                          <span className="text-content-secondary">{task.story_id}</span>
                                        </span>
                                        {Array.isArray(task.depends_on) && task.depends_on.length > 0 && (
                                          <>
                                            <span>·</span>
                                            <span className="text-content-muted">
                                              Depends on{' '}
                                              <span className="text-[#a78bfa]">
                                                {task.depends_on.join(', ')}
                                              </span>
                                            </span>
                                          </>
                                        )}
                                        {task.estimate_points && (
                                          <>
                                            <span>·</span>
                                            <span className="text-content-muted">
                                              {task.estimate_points} pts
                                            </span>
                                          </>
                                        )}
                                        {Array.isArray(task.required_skills) &&
                                          task.required_skills.length > 0 && (
                                            <>
                                              <span>·</span>
                                              <span className="text-content-muted">
                                                Skills: {task.required_skills.join(', ')}
                                              </span>
                                            </>
                                          )}
                                        {Array.isArray(task.source_refs) && task.source_refs.length > 0 && (
                                          <>
                                            <span>·</span>
                                            <span className="text-content-muted">
                                              Source: {task.source_refs.join(', ')}
                                            </span>
                                          </>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}

                    {/* Direct Stories under Epic if Features were not selected */}
                    {directStories.map((story) => {
                      const storyTasks = tasks.filter((t) => t.story_id === story.id)

                      return (
                        <div
                          key={story.id}
                          className="rounded-control border border-[#2d1b4e] bg-[#110722] p-3 space-y-2 mt-2"
                        >
                          <div>
                            <h6 className="font-medium text-content-primary text-xs sm:text-sm">
                              {story.id} · {getStoryTitle(story)}
                            </h6>
                            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-content-muted">
                              <span>
                                Parent:{' '}
                                <span className="font-mono text-content-secondary">{story.epic_id}</span>
                              </span>
                              {story.estimate_points && (
                                <>
                                  <span>·</span>
                                  <span>
                                    Estimate:{' '}
                                    <span className="text-content-secondary">
                                      {story.estimate_points} workload units
                                    </span>
                                  </span>
                                </>
                              )}
                              {Array.isArray(story.source_refs) && story.source_refs.length > 0 && (
                                <>
                                  <span>·</span>
                                  <span>
                                    Source:{' '}
                                    <span className="font-mono text-content-secondary">
                                      {story.source_refs.join(', ')}
                                    </span>
                                  </span>
                                </>
                              )}
                            </div>
                          </div>

                          {/* Tasks under Story */}
                          {storyTasks.length > 0 && (
                            <div className="pt-2 border-t border-[#2d1b4e]/50 space-y-1.5 font-mono text-xs">
                              {storyTasks.map((task) => (
                                <div
                                  key={task.id}
                                  className="text-content-secondary flex flex-wrap items-baseline gap-1.5"
                                >
                                  <span className="font-semibold text-content-primary">{task.id}</span>
                                  <span>·</span>
                                  <span className="font-sans text-content-secondary">{task.title}</span>
                                  <span>·</span>
                                  <span className="text-content-muted">
                                    Parent:{' '}
                                    <span className="text-content-secondary">{task.story_id}</span>
                                  </span>
                                  {Array.isArray(task.depends_on) && task.depends_on.length > 0 && (
                                    <>
                                      <span>·</span>
                                      <span className="text-content-muted">
                                        Depends on{' '}
                                        <span className="text-[#a78bfa]">
                                          {task.depends_on.join(', ')}
                                        </span>
                                      </span>
                                    </>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )
              })}

            {/* If Epics were NOT selected, but Features exist: render Feature-rooted tree */}
            {epics.length === 0 &&
              features.length > 0 &&
              features.map((feat) => {
                const featStories = stories.filter((s) => s.feature_id === feat.id)

                return (
                  <div
                    key={feat.id}
                    className="rounded-control border border-[#4c1d95]/40 bg-[#160b2d]/80 p-4 space-y-3"
                  >
                    <div>
                      <h4 className="font-semibold text-content-primary text-sm sm:text-base">
                        {feat.id} · {feat.title}
                      </h4>
                      {feat.epic_id && (
                        <p className="mt-0.5 text-xs text-content-muted">
                          Parent:{' '}
                          <span className="font-mono text-content-secondary">{feat.epic_id}</span>
                        </p>
                      )}
                      {feat.description && (
                        <p className="mt-1 text-xs text-content-secondary">{feat.description}</p>
                      )}
                    </div>

                    {featStories.map((story) => {
                      const storyTasks = tasks.filter((t) => t.story_id === story.id)

                      return (
                        <div
                          key={story.id}
                          className="rounded-control border border-[#2d1b4e] bg-[#110722] p-3 space-y-2 mt-2"
                        >
                          <h5 className="font-medium text-content-primary text-xs sm:text-sm">
                            {story.id} · {getStoryTitle(story)}
                          </h5>
                          {storyTasks.length > 0 && (
                            <div className="pt-2 border-t border-[#2d1b4e]/50 space-y-1.5 font-mono text-xs">
                              {storyTasks.map((task) => (
                                <div
                                  key={task.id}
                                  className="text-content-secondary flex flex-wrap items-baseline gap-1.5"
                                >
                                  <span className="font-semibold text-content-primary">{task.id}</span>
                                  <span>·</span>
                                  <span className="font-sans">{task.title}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )
              })}

            {/* If neither Epics nor Features were selected, but Stories exist: render Story-rooted tree */}
            {epics.length === 0 &&
              features.length === 0 &&
              stories.length > 0 &&
              stories.map((story) => {
                const storyTasks = tasks.filter((t) => t.story_id === story.id)

                return (
                  <div
                    key={story.id}
                    className="rounded-control border border-[#2d1b4e] bg-[#110722] p-4 space-y-3"
                  >
                    <div>
                      <h4 className="font-medium text-content-primary text-sm sm:text-base">
                        {story.id} · {getStoryTitle(story)}
                      </h4>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-content-muted">
                        {story.feature_id && (
                          <span>
                            Parent:{' '}
                            <span className="font-mono text-content-secondary">
                              {story.feature_id}
                            </span>
                          </span>
                        )}
                        {story.estimate_points && (
                          <>
                            <span>·</span>
                            <span>
                              Estimate:{' '}
                              <span className="text-content-secondary">
                                {story.estimate_points} workload units
                              </span>
                            </span>
                          </>
                        )}
                        {Array.isArray(story.source_refs) && story.source_refs.length > 0 && (
                          <>
                            <span>·</span>
                            <span>
                              Source:{' '}
                              <span className="font-mono text-content-secondary">
                                {story.source_refs.join(', ')}
                              </span>
                            </span>
                          </>
                        )}
                      </div>
                      {Array.isArray(story.acceptance_criteria) &&
                        story.acceptance_criteria.length > 0 && (
                          <div className="mt-2 text-xs">
                            <span className="font-medium text-content-secondary">
                              Acceptance criteria:
                            </span>
                            <ul className="list-disc pl-4 mt-0.5 space-y-0.5 text-content-muted">
                              {story.acceptance_criteria.map((ac, acIdx) => (
                                <li key={acIdx}>{ac}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                    </div>

                    {storyTasks.length > 0 && (
                      <div className="pt-2 border-t border-[#2d1b4e]/50 space-y-1.5 font-mono text-xs">
                        {storyTasks.map((task) => (
                          <div
                            key={task.id}
                            className="text-content-secondary flex flex-wrap items-baseline gap-1.5"
                          >
                            <span className="font-semibold text-content-primary">{task.id}</span>
                            <span>·</span>
                            <span className="font-sans text-content-secondary">{task.title}</span>
                            <span>·</span>
                            <span className="text-content-muted">
                              Parent: <span className="text-content-secondary">{task.story_id}</span>
                            </span>
                            {Array.isArray(task.depends_on) && task.depends_on.length > 0 && (
                              <>
                                <span>·</span>
                                <span className="text-content-muted">
                                  Depends on{' '}
                                  <span className="text-[#a78bfa]">
                                    {task.depends_on.join(', ')}
                                  </span>
                                </span>
                              </>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
        </div>
      )}

      {/* Unlinked items section (only if parent reference cannot be safely linked) */}
      {hasUnlinked && (
        <div className="rounded-panel border border-[#3b1d54] bg-[#160c2b] p-5 space-y-3">
          <div>
            <h3 className="font-semibold text-content-primary">Unlinked items</h3>
            <p className="mt-0.5 text-xs text-content-muted">
              Planning items whose parent reference does not match any returned item in this run.
            </p>
          </div>
          <div className="space-y-2 text-xs" aria-label="Unlinked items list">
            {unlinkedFeatures.map((f) => (
              <div
                key={f.id}
                className="p-3 rounded-control border border-[#4c1d95]/40 bg-[#160b2d]/80"
              >
                <span className="font-semibold text-content-primary">{f.id}</span>
                <span className="text-content-secondary ml-1">· {f.title}</span>
                <span className="text-content-muted ml-2">(Parent: {f.epic_id || 'None'})</span>
              </div>
            ))}
            {unlinkedStories.map((s) => (
              <div
                key={s.id}
                className="p-3 rounded-control border border-[#2d1b4e] bg-[#110722]"
              >
                <span className="font-semibold text-content-primary">{s.id}</span>
                <span className="text-content-secondary ml-1">· {getStoryTitle(s)}</span>
                <span className="text-content-muted ml-2">
                  (Parent: {s.feature_id || s.epic_id || 'None'})
                </span>
              </div>
            ))}
            {unlinkedTasks.map((t) => (
              <div
                key={t.id}
                className="p-3 rounded-control border border-[#2d1b4e] bg-[#110722] font-mono"
              >
                <span className="font-semibold text-content-primary">{t.id}</span>
                <span className="font-sans text-content-secondary ml-1">· {t.title}</span>
                <span className="text-content-muted ml-2">(Parent: {t.story_id || 'None'})</span>
                {Array.isArray(t.depends_on) && t.depends_on.length > 0 && (
                  <span className="text-[#a78bfa] ml-2">
                    Depends on: {t.depends_on.join(', ')}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deterministic Planning Checks card matching PNG */}
      <div className="rounded-panel border border-[#2d1b4e] bg-[#160c2b] p-5 space-y-3">
        <div>
          <h3 className="font-semibold text-content-primary">Deterministic planning checks</h3>
          <p className="mt-0.5 text-xs text-content-muted">
            All references are checked before results are accepted.
          </p>
        </div>
        <ul
          className="space-y-1.5 text-xs text-content-secondary"
          aria-label="Deterministic planning checks"
        >
          <li className="flex items-center gap-2">
            <span className="text-[#34d399] font-bold" aria-hidden="true">
              •
            </span>
            <span>Features reference valid epics</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[#34d399] font-bold" aria-hidden="true">
              •
            </span>
            <span>Stories reference valid features</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[#34d399] font-bold" aria-hidden="true">
              •
            </span>
            <span>Tasks reference valid stories</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[#34d399] font-bold" aria-hidden="true">
              •
            </span>
            <span>Task dependencies reference valid tasks</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[#34d399] font-bold" aria-hidden="true">
              •
            </span>
            <span>Duplicate planning IDs rejected</span>
          </li>
        </ul>
      </div>

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

export default PlanningHierarchy
