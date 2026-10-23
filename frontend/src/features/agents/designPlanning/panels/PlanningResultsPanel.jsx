import { useMemo, useState } from 'react'

import JiraPlanView from '../../../../components/agents/agent-2/results/JiraPlan.jsx'
import PlanningHierarchy from '../../../../components/agents/agent-2/results/PlanningHierarchy.jsx'
import SprintPlanView from '../../../../components/agents/agent-2/results/SprintPlan.jsx'
import TaskAssignmentView from '../../../../components/agents/agent-2/results/TaskAssignment.jsx'
import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export default function PlanningResultsPanel({
  project,
  activeRun,
  run,
  outputs = {},
  runs = [],
  onSelectRun,
  onNavigate,
}) {
  const effectiveActiveRun = activeRun || run
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : (effectiveActiveRun?.output_manifest || effectiveActiveRun?.outputs || {})

  const hasHierarchy = Boolean(
    safeOutputs.EPICS?.length ||
    safeOutputs.USER_STORIES?.length ||
    safeOutputs.TASKS?.length ||
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
  const hasJiraPlan = Boolean(safeOutputs.JIRA_PLAN)

  const hasAnyPlanning = hasHierarchy || hasSprintPlan || hasTaskAssignment || hasJiraPlan

  const initialTab = useMemo(() => {
    if (hasHierarchy) return 'hierarchy'
    if (hasSprintPlan) return 'sprint'
    if (hasTaskAssignment) return 'tasks'
    if (hasJiraPlan) return 'jira'
    return 'hierarchy'
  }, [hasHierarchy, hasSprintPlan, hasTaskAssignment, hasJiraPlan])

  const [selectedTab, setSelectedTab] = useState(null)
  const [prevRunId, setPrevRunId] = useState(effectiveActiveRun?.run_id)

  if (effectiveActiveRun?.run_id !== prevRunId) {
    setPrevRunId(effectiveActiveRun?.run_id)
    setSelectedTab(null)
  }

  const activeTab = selectedTab || initialTab
  const setActiveTab = setSelectedTab

  const effectiveStatus = effectiveActiveRun?.status || (effectiveActiveRun ? 'COMPLETED' : 'IDLE')
  const isFailed = effectiveStatus === 'FAILED'

  if (!effectiveActiveRun && runs.length === 0) {
    return (
      <div className="space-y-6" data-testid="agent2-panel-PLANNING_RESULTS">
        <div className="rounded-panel border border-default bg-surface p-6 text-center space-y-3">
          <h2 className="text-card-heading font-semibold text-content-primary">
            No planning results recorded yet
          </h2>
          <p className="text-sm text-content-secondary max-w-lg mx-auto">
            Generate Agent 2 deliverables in Node 5 to review epics, user stories, sprint schedule, and Jira-compatible plan.
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
    <div className="space-y-6" data-testid="agent2-panel-PLANNING_RESULTS">
      {/* Top Header bar with run info and switcher */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-page-heading font-semibold tracking-tight text-content-primary">
              Planning Results
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
            Agile planning hierarchy, sprint schedule, and Jira-compatible plan
          </p>
        </div>

        {runs.length > 1 && onSelectRun && (
          <div className="flex items-center gap-2 text-xs">
            <label htmlFor="planning-results-run-select" className="text-content-muted font-medium">
              Run:
            </label>
            <select
              id="planning-results-run-select"
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

      {!hasAnyPlanning ? (
        <div className="rounded-panel border border-default bg-surface p-6 space-y-4 text-center">
          <h3 className="text-base font-semibold text-content-primary">
            No agile planning deliverables generated for this run
          </h3>
          <p className="text-sm text-content-secondary max-w-md mx-auto">
            Run <strong className="font-mono">{effectiveActiveRun?.run_id || 'active'}</strong> does not contain backlog, sprint, or Jira plan deliverables.
          </p>
          {onNavigate && (
            <div className="pt-2">
              <Button
                variant="outline"
                size="small"
                onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS)}
              >
                ← View Technical Design (Node 6)
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Sub-view navigation tabs */}
          <div className="flex flex-wrap items-center gap-2 border-b border-default pb-3" role="tablist" aria-label="Planning results views">
            {hasHierarchy && (
              <button
                type="button"
                role="tab"
                id="tab-planning-hierarchy"
                aria-selected={activeTab === 'hierarchy'}
                aria-controls="panel-planning-hierarchy"
                onClick={() => setActiveTab('hierarchy')}
                className={`rounded-control px-3 py-1.5 text-xs font-semibold transition-colors ${
                  activeTab === 'hierarchy'
                    ? 'bg-brand text-content-on-primary shadow-sm'
                    : 'bg-elevated text-content-secondary hover:text-content-primary hover:bg-elevated/80'
                }`}
              >
                Planning Hierarchy
              </button>
            )}
            {hasSprintPlan && (
              <button
                type="button"
                role="tab"
                id="tab-sprint-plan"
                aria-selected={activeTab === 'sprint'}
                aria-controls="panel-sprint-plan"
                onClick={() => setActiveTab('sprint')}
                className={`rounded-control px-3 py-1.5 text-xs font-semibold transition-colors ${
                  activeTab === 'sprint'
                    ? 'bg-brand text-content-on-primary shadow-sm'
                    : 'bg-elevated text-content-secondary hover:text-content-primary hover:bg-elevated/80'
                }`}
              >
                Sprint Plan
              </button>
            )}
            {hasTaskAssignment && (
              <button
                type="button"
                role="tab"
                id="tab-task-assignment"
                aria-selected={activeTab === 'tasks'}
                aria-controls="panel-task-assignment"
                onClick={() => setActiveTab('tasks')}
                className={`rounded-control px-3 py-1.5 text-xs font-semibold transition-colors ${
                  activeTab === 'tasks'
                    ? 'bg-brand text-content-on-primary shadow-sm'
                    : 'bg-elevated text-content-secondary hover:text-content-primary hover:bg-elevated/80'
                }`}
              >
                Task Assignment
              </button>
            )}
            {hasJiraPlan && (
              <button
                type="button"
                role="tab"
                id="tab-jira-plan"
                aria-selected={activeTab === 'jira'}
                aria-controls="panel-jira-plan"
                onClick={() => setActiveTab('jira')}
                className={`rounded-control px-3 py-1.5 text-xs font-semibold transition-colors ${
                  activeTab === 'jira'
                    ? 'bg-brand text-content-on-primary shadow-sm'
                    : 'bg-elevated text-content-secondary hover:text-content-primary hover:bg-elevated/80'
                }`}
              >
                Jira-ready Plan
              </button>
            )}
          </div>

          {/* Active Tab Content */}
          <div className="pt-2">
            {activeTab === 'hierarchy' && hasHierarchy && (
              <div id="panel-planning-hierarchy" role="tabpanel" aria-labelledby="tab-planning-hierarchy">
                <PlanningHierarchy
                  outputs={safeOutputs}
                  run={activeRun}
                  status={effectiveStatus}
                  project={project}
                  onViewSprintPlan={() => setActiveTab('sprint')}
                  onViewTaskAssignment={() => setActiveTab('tasks')}
                  onViewJiraPlan={() => setActiveTab('jira')}
                  onViewValidationHistory={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}
                />
              </div>
            )}

            {activeTab === 'sprint' && hasSprintPlan && (
              <div id="panel-sprint-plan" role="tabpanel" aria-labelledby="tab-sprint-plan">
                <SprintPlanView
                  outputs={safeOutputs}
                  run={activeRun}
                  status={effectiveStatus}
                  project={project}
                  onViewPlanningHierarchy={() => setActiveTab('hierarchy')}
                  onViewTaskAssignment={() => setActiveTab('tasks')}
                  onViewJiraPlan={() => setActiveTab('jira')}
                  onViewValidationHistory={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}
                />
              </div>
            )}

            {activeTab === 'tasks' && hasTaskAssignment && (
              <div id="panel-task-assignment" role="tabpanel" aria-labelledby="tab-task-assignment">
                <TaskAssignmentView
                  outputs={safeOutputs}
                  run={activeRun}
                  status={effectiveStatus}
                  project={project}
                  onViewPlanningHierarchy={() => setActiveTab('hierarchy')}
                  onViewSprintPlan={() => setActiveTab('sprint')}
                  onViewJiraPlan={() => setActiveTab('jira')}
                  onViewValidationHistory={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}
                />
              </div>
            )}

            {activeTab === 'jira' && hasJiraPlan && (
              <div id="panel-jira-plan" role="tabpanel" aria-labelledby="tab-jira-plan">
                <JiraPlanView
                  outputs={safeOutputs}
                  run={activeRun}
                  status={effectiveStatus}
                  project={project}
                  onViewPlanningHierarchy={() => setActiveTab('hierarchy')}
                  onViewSprintPlan={() => setActiveTab('sprint')}
                  onViewTaskAssignment={() => setActiveTab('tasks')}
                  onViewValidationHistory={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Navigation footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default/60 pt-4">
        {onNavigate ? (
          <Button
            variant="outline"
            size="small"
            onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS)}
          >
            ← Node 6 (Design Results)
          </Button>
        ) : <span />}
        {onNavigate && (
          <Button
            variant="primary"
            size="small"
            onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY)}
          >
            Node 8 (Validation &amp; Traceability) →
          </Button>
        )}
      </div>
    </div>
  )
}
