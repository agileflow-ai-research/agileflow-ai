import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import Input from '../../../../components/ui/Input.jsx'
import Textarea from '../../../../components/ui/Textarea.jsx'
import { cn } from '../../../../utils/cn.js'
import {
  PLANNING_MODES,
  getRequiredPlanningFields,
} from '../constants/agent2Config.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export default function TechnicalPlanningPanel({
  input = {},
  selectedOutputs = [],
  errors = {},
  onUpdateField,
  onNavigate,
  onValidate,
}) {
  const planningMode = input.planning_mode || PLANNING_MODES.TIMELINE_BASED
  const requiredPlanning = getRequiredPlanningFields(selectedOutputs, input)
  const isTeamCountRequired = Boolean(requiredPlanning.development_team_count)
  const isSprintDurationRequired = Boolean(requiredPlanning.sprint_duration)
  const isStartDateRequired = Boolean(requiredPlanning.project_start_date)
  const isDurationRequired = Boolean(requiredPlanning.expected_project_duration)
  const hasContractRequiredInputs = Object.keys(requiredPlanning).length > 0
  const isSprintPlanSelected = selectedOutputs.includes('SPRINT_PLAN')

  // Check if current selection contains planning outputs
  const planningOutputCodes = [
    'PRODUCT_BACKLOG',
    'EPICS',
    'FEATURES',
    'USER_STORIES',
    'TASKS',
    'SPRINT_PLAN',
    'TASK_ASSIGNMENT',
    'JIRA_PLAN',
  ]
  const hasPlanningOutputs = selectedOutputs.some((code) =>
    planningOutputCodes.includes(code),
  )
  const isArchitectureOnly = selectedOutputs.length > 0 && !hasPlanningOutputs

  function handleContinue() {
    const isValid = onValidate ? onValidate() : true
    if (isValid && onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)
    }
  }

  function handleBack() {
    if (onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)
    }
  }

  /* Sprint Planning Method Card (shown when SPRINT_PLAN is selected) */
  const sprintPlanningMethodCard = isSprintPlanSelected ? (
    <Card className="border border-brand/50 bg-surface p-6 space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Sprint Planning Method
          </h3>
          <span className="inline-flex items-center rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand">
            SPRINT_PLAN
          </span>
        </div>
        <p className="mt-1 text-sm text-content-muted">
          Choose whether to plan sprints purely against your project timeline or additionally constrain by team capacity.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Sprint Planning Method">
        <label
          className={cn(
            'flex cursor-pointer items-start gap-3 rounded-control border p-4 transition-all',
            planningMode === PLANNING_MODES.TIMELINE_BASED
              ? 'border-brand bg-brand-soft ring-1 ring-brand'
              : 'border-default bg-elevated hover:border-brand/50 hover:bg-surface',
          )}
        >
          <input
            type="radio"
            name="planning_mode"
            value={PLANNING_MODES.TIMELINE_BASED}
            checked={planningMode === PLANNING_MODES.TIMELINE_BASED}
            onChange={() => onUpdateField?.('planning_mode', PLANNING_MODES.TIMELINE_BASED)}
            className="mt-1 h-4 w-4 accent-brand cursor-pointer"
          />
          <div className="space-y-1">
            <span className="block text-sm font-semibold text-content-primary">
              Timeline-based
            </span>
            <span className="block text-xs text-content-secondary leading-relaxed">
              Organize generated work across the project timeline.
            </span>
          </div>
        </label>

        <label
          className={cn(
            'flex cursor-pointer items-start gap-3 rounded-control border p-4 transition-all',
            planningMode === PLANNING_MODES.CAPACITY_AWARE
              ? 'border-brand bg-brand-soft ring-1 ring-brand'
              : 'border-default bg-elevated hover:border-brand/50 hover:bg-surface',
          )}
        >
          <input
            type="radio"
            name="planning_mode"
            value={PLANNING_MODES.CAPACITY_AWARE}
            checked={planningMode === PLANNING_MODES.CAPACITY_AWARE}
            onChange={() => onUpdateField?.('planning_mode', PLANNING_MODES.CAPACITY_AWARE)}
            className="mt-1 h-4 w-4 accent-brand cursor-pointer"
          />
          <div className="space-y-1">
            <span className="block text-sm font-semibold text-content-primary">
              Capacity-aware
            </span>
            <span className="block text-xs text-content-secondary leading-relaxed">
              Also consider development team size when distributing workload.
            </span>
          </div>
        </label>
      </div>
    </Card>
  ) : null

  /* 1. Required inputs card */
  const requiredInputsCard = (
    <Card className="border border-brand/50 bg-surface p-6 space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Required inputs
          </h3>
          {hasContractRequiredInputs ? (
            <span className="inline-flex items-center rounded-full bg-state-warning-soft px-2.5 py-0.5 text-xs font-semibold text-state-warning">
              Contract required
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-state-success-soft px-2.5 py-0.5 text-xs font-semibold text-state-success">
              ✓ None required
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-content-muted">
          Fields required because of selected outputs and planning method.
        </p>
      </div>

      {hasContractRequiredInputs ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {isStartDateRequired && (
            <div className="space-y-1.5">
              <Input
                label="Project start date *"
                type="date"
                value={input.project_start_date || ''}
                error={errors.project_start_date}
                onChange={(e) => onUpdateField?.('project_start_date', e.target.value)}
                placeholder="YYYY-MM-DD"
                inputClassName="bg-elevated border-default"
                required
              />
              {!errors.project_start_date && (
                <span className="block text-xs text-brand">
                  {requiredPlanning.project_start_date.reason}
                </span>
              )}
            </div>
          )}

          {isDurationRequired && (
            <div className="space-y-1.5">
              <Input
                label="Expected project duration *"
                type="text"
                value={input.expected_project_duration || ''}
                error={errors.expected_project_duration}
                onChange={(e) => onUpdateField?.('expected_project_duration', e.target.value)}
                placeholder="e.g. 3 months or 2026-12-31"
                inputClassName="bg-elevated border-default"
                required
              />
              {!errors.expected_project_duration && (
                <span className="block text-xs text-brand">
                  {requiredPlanning.expected_project_duration.reason}
                </span>
              )}
            </div>
          )}

          {isSprintDurationRequired && (
            <div className="space-y-1.5">
              <Input
                label="Sprint duration (days) *"
                type="number"
                min="1"
                value={input.sprint_duration || ''}
                error={errors.sprint_duration}
                onChange={(e) => onUpdateField?.('sprint_duration', e.target.value)}
                placeholder="Sprint duration in days (e.g. 14)"
                inputClassName="bg-elevated border-default"
                required
              />
              {!errors.sprint_duration && (
                <span className="block text-xs text-brand">
                  {requiredPlanning.sprint_duration.reason}
                </span>
              )}
            </div>
          )}

          {isTeamCountRequired && (
            <div className="space-y-1.5">
              <Input
                label="Development team count *"
                type="number"
                min="1"
                value={input.development_team_count || ''}
                error={errors.development_team_count}
                onChange={(e) => onUpdateField?.('development_team_count', e.target.value)}
                placeholder="Team count (e.g. 4)"
                inputClassName="bg-elevated border-default"
                required
              />
              {!errors.development_team_count && (
                <span className="block text-xs text-brand">
                  {requiredPlanning.development_team_count.reason}
                </span>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-control border border-state-success/40 bg-state-success-soft p-4 text-xs text-state-success">
          {selectedOutputs.length === 0
            ? 'Select outputs in Node 2 to determine if technical planning inputs are contract-required.'
            : 'Your selected outputs do not require team count or sprint duration. All planning parameters are optional.'}
        </div>
      )}
    </Card>
  )

  /* 2. Recommended inputs card */
  const recommendedInputsCard = (
    <Card className="border-default bg-surface p-6 space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Recommended inputs
          </h3>
          <span className="inline-flex items-center rounded-full bg-elevated px-2 py-0.5 text-xs text-content-muted">
            Recommended
          </span>
        </div>
        <p className="mt-1 text-sm text-content-muted">
          Useful for improving selected planning/design outputs but not contract-required.
        </p>
      </div>

      <div className="space-y-4">
        {/* If team count, sprint duration, start date, or duration were NOT contract-required, keep them accessible here */}
        {(!isTeamCountRequired || !isSprintDurationRequired || !isStartDateRequired || !isDurationRequired) && (
          <div className="grid gap-3 sm:grid-cols-2">
            {!isStartDateRequired && (
              <Input
                label="Project start date"
                type="date"
                value={input.project_start_date || ''}
                helperText="Recommended"
                onChange={(e) => onUpdateField?.('project_start_date', e.target.value)}
                placeholder="YYYY-MM-DD"
                inputClassName="bg-elevated border-default"
              />
            )}
            {!isDurationRequired && (
              <Input
                label="Expected project duration"
                value={input.expected_project_duration || ''}
                helperText="Recommended"
                onChange={(e) => onUpdateField?.('expected_project_duration', e.target.value)}
                placeholder="e.g. 3 months"
                inputClassName="bg-elevated border-default"
              />
            )}
            {!isSprintDurationRequired && (
              <Input
                label="Sprint duration (days)"
                type="number"
                min="1"
                value={input.sprint_duration || ''}
                error={errors.sprint_duration}
                helperText="Recommended"
                onChange={(e) => onUpdateField?.('sprint_duration', e.target.value)}
                placeholder="Optional sprint duration"
                inputClassName="bg-elevated border-default"
              />
            )}
            {!isTeamCountRequired && (
              <Input
                label="Development team count"
                type="number"
                min="1"
                value={input.development_team_count || ''}
                error={errors.development_team_count}
                helperText="Recommended"
                onChange={(e) => onUpdateField?.('development_team_count', e.target.value)}
                placeholder="Optional team count"
                inputClassName="bg-elevated border-default"
              />
            )}
          </div>
        )}

        <Textarea
          label="Developer Roles"
          rows={3}
          value={input.developer_roles || ''}
          helperText="Recommended"
          onChange={(e) => onUpdateField?.('developer_roles', e.target.value)}
          placeholder="e.g. 2 Frontend, 2 Backend, 1 QA"
          textareaClassName="bg-elevated border-default"
        />
        <Textarea
          label="Developer Skills"
          rows={3}
          value={input.developer_skills || ''}
          helperText="Recommended"
          onChange={(e) => onUpdateField?.('developer_skills', e.target.value)}
          placeholder="e.g. React, Python, FastAPI, Docker"
          textareaClassName="bg-elevated border-default"
        />
        <Textarea
          label="Team Composition"
          rows={3}
          value={input.team_composition || ''}
          helperText="Recommended"
          onChange={(e) => onUpdateField?.('team_composition', e.target.value)}
          placeholder="e.g. Cross-functional agile team"
          textareaClassName="bg-elevated border-default"
        />
      </div>
    </Card>
  )

  /* 3. Optional technical preferences card */
  const technicalPreferencesCard = (
    <Card
      className={cn(
        'border bg-surface p-6 space-y-4',
        isArchitectureOnly ? 'border-brand/50' : 'border-default',
      )}
    >
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Optional technical preferences
          </h3>
          {isArchitectureOnly && (
            <span className="inline-flex items-center rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand">
              Design context
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-content-muted">
          Other existing technical fields and architecture constraints.
        </p>
      </div>

      <div className="space-y-4">
        <Input
          label="Preferred Technology Stack"
          value={input.preferred_technology_stack || ''}
          helperText="Optional"
          onChange={(e) => onUpdateField?.('preferred_technology_stack', e.target.value)}
          placeholder="e.g. React 19, FastAPI, PostgreSQL"
          inputClassName="bg-elevated border-default"
        />
        <Textarea
          label="Technical Constraints"
          rows={3}
          value={input.technical_constraints || ''}
          helperText="Optional"
          onChange={(e) => onUpdateField?.('technical_constraints', e.target.value)}
          placeholder="e.g. Must run on Linux ARM64, response time < 200ms"
          textareaClassName="bg-elevated border-default"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Deployment Preference"
            value={input.deployment_preference || ''}
            helperText="Optional"
            onChange={(e) => onUpdateField?.('deployment_preference', e.target.value)}
            placeholder="e.g. Docker, AWS ECS"
            inputClassName="bg-elevated border-default"
          />
          <Input
            label="Database Preference"
            value={input.database_preference || ''}
            helperText="Optional"
            onChange={(e) => onUpdateField?.('database_preference', e.target.value)}
            placeholder="e.g. PostgreSQL 16"
            inputClassName="bg-elevated border-default"
          />
        </div>
        <Textarea
          label="UI/UX Constraints"
          rows={3}
          value={input.ui_ux_constraints || ''}
          helperText="Optional"
          onChange={(e) => onUpdateField?.('ui_ux_constraints', e.target.value)}
          placeholder="e.g. Responsive dark theme, WCAG 2.1 AA compliant"
          textareaClassName="bg-elevated border-default"
        />
        <Textarea
          label="Architecture Notes"
          rows={3}
          value={input.architecture_notes || ''}
          helperText="Optional"
          onChange={(e) => onUpdateField?.('architecture_notes', e.target.value)}
          placeholder="e.g. Clean architecture, modular monolith"
          textareaClassName="bg-elevated border-default"
        />
      </div>
    </Card>
  )

  return (
    <div className="space-y-6" data-testid="agent2-panel-TECHNICAL_PLANNING">
      {/* Top Banner: Selected outputs indicator */}
      <Card className="border-default bg-surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-content-primary">
                Selected Outputs
              </h3>
              <span className="inline-flex items-center rounded-control border border-default bg-elevated px-2.5 py-0.5 text-xs font-medium text-content-secondary">
                {selectedOutputs.length} of 14 selected
              </span>
            </div>
            <p className="mt-1 text-xs text-content-muted">
              Provide the additional technical and planning information required for your selected outputs.
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)}
            className="text-xs text-brand hover:text-content-primary hover:bg-brand-soft underline"
          >
            Change outputs (Node 2)
          </Button>
        </div>

        {selectedOutputs.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Currently selected outputs list">
            {selectedOutputs.map((code) => {
              const isPlanningTrigger = ['SPRINT_PLAN', 'TASK_ASSIGNMENT', 'JIRA_PLAN'].includes(code)
              return (
                <span
                  key={code}
                  className={cn(
                    'inline-flex items-center rounded-control border px-2 py-0.5 text-[11px] font-mono',
                    isPlanningTrigger
                      ? 'border-brand bg-brand-soft text-brand font-semibold'
                      : 'border-default bg-elevated text-content-secondary',
                  )}
                >
                  {code}
                </span>
              )
            })}
          </div>
        ) : (
          <div className="mt-3 rounded-control border border-state-warning/30 bg-state-warning/10 p-2.5 text-xs text-state-warning">
            No outputs selected yet. Output Selection (Node 2) determines which planning fields are required.
          </div>
        )}
      </Card>

      {/* Sprint Planning Method selector when SPRINT_PLAN is selected */}
      {sprintPlanningMethodCard}

      {/* Main content cards: organized conditionally */}
      {isArchitectureOnly ? (
        /* Architecture-only outputs: show technical preferences prominently, then required inputs (none required) and recommended */
        <div className="space-y-6">
          {technicalPreferencesCard}
          <div className="grid gap-6 lg:grid-cols-2">
            {requiredInputsCard}
            {recommendedInputsCard}
          </div>
        </div>
      ) : (
        /* Planning outputs or standard view: Required inputs, then Recommended & Technical */
        <div className="space-y-6">
          {requiredInputsCard}
          <div className="grid gap-6 lg:grid-cols-2">
            {recommendedInputsCard}
            {technicalPreferencesCard}
          </div>
        </div>
      )}

      {/* Conditional validation callout card */}
      <Card className="border-default bg-surface p-6">
        <h3 className="text-card-heading font-semibold text-content-primary">
          Conditional validation
        </h3>
        <p className="mt-1 text-sm text-content-muted">
          Contract-required planning parameters mirror backend validation rules:
        </p>
        <ul className="mt-4 space-y-2 text-sm text-content-secondary">
          <li className="flex items-start gap-2">
            <span className="text-content-muted" aria-hidden="true">•</span>
            <span>
              <code className="text-xs font-semibold text-content-primary">TIMELINE_BASED + SPRINT_PLAN</code> requires project_start_date + expected_project_duration + sprint_duration (team count optional)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-content-muted" aria-hidden="true">•</span>
            <span>
              <code className="text-xs font-semibold text-content-primary">CAPACITY_AWARE + SPRINT_PLAN</code> requires project_start_date + expected_project_duration + sprint_duration + development_team_count
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-content-muted" aria-hidden="true">•</span>
            <span>
              <code className="text-xs font-semibold text-content-primary">TASK_ASSIGNMENT</code> requires development_team_count
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-content-muted" aria-hidden="true">•</span>
            <span>
              <code className="text-xs font-semibold text-content-primary">JIRA_PLAN</code> does not require development_team_count; tasks remain unassigned unless requested
            </span>
          </li>
        </ul>
      </Card>

      {/* Footer navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default/60 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={handleBack}
          className="border-default bg-surface text-content-primary hover:bg-elevated"
        >
          Back — Output Selection
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={handleContinue}
        >
          Next — Human Review
        </Button>
      </div>
    </div>
  )
}
