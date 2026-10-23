import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import { cn } from '../../../../utils/cn.js'
import {
  getPlanningErrors,
  outputGroups,
} from '../constants/agent2Config.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export default function OutputSelectionPanel({
  input = {},
  selectedOutputs = [],
  errors = {},
  onToggleOutput,
  onSelectAll,
  onClearAll,
  onNavigate,
  onValidate,
}) {
  const planningIssues = getPlanningErrors(input, selectedOutputs)
  const hasPlanningIssues = Object.keys(planningIssues).length > 0

  function handleContinue() {
    const isValid = onValidate ? onValidate() : true
    if (isValid && onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)
    }
  }

  function handleBack() {
    if (onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)
    }
  }

  return (
    <div className="space-y-6" data-testid="agent2-panel-OUTPUT_SELECTION">
      {/* Header controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-default/60 pb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-content-primary">
            Output Deliverables
          </span>
          <span className="inline-flex items-center rounded-control border border-default bg-elevated px-2.5 py-0.5 text-xs font-medium text-content-secondary">
            {selectedOutputs.length} of 14 selected
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onSelectAll}
            className="text-xs text-content-secondary hover:text-content-primary"
          >
            Select all (14)
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClearAll}
            className="text-xs text-content-muted hover:text-state-danger"
          >
            Clear all
          </Button>
        </div>
      </div>

      {/* 3 Group Cards */}
      <div className="grid gap-6 md:grid-cols-3">
        {outputGroups.map((group) => (
          <Card key={group.id} className="border-default bg-surface p-6 space-y-4">
            <div>
              <h3 className="text-card-heading font-semibold text-content-primary">
                {group.title}
              </h3>
              <p className="mt-1 text-sm text-content-muted">
                {group.subtitle}
              </p>
            </div>

            <div className="space-y-2.5">
              {group.outputs.map((output) => {
                const isSelected = selectedOutputs.includes(output.value)
                return (
                  <label
                    key={output.value}
                    className={cn(
                      'flex cursor-pointer items-start gap-3 rounded-control border p-3.5 transition-colors',
                      isSelected
                        ? 'border-brand bg-brand-soft text-content-primary'
                        : 'border-default bg-elevated text-content-secondary hover:border-brand/40 hover:text-content-primary',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      aria-label={output.label}
                      onChange={() => onToggleOutput?.(output.value)}
                      className="mt-0.5 h-4 w-4 rounded accent-brand"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        {isSelected && (
                          <span className="text-brand font-bold text-xs" aria-hidden="true">
                            ✓
                          </span>
                        )}
                        <span className="font-semibold text-sm text-content-primary">
                          {output.label}
                        </span>
                      </div>
                      <span className="block mt-0.5 font-mono text-[11px] text-content-muted">
                        {output.value}
                      </span>
                      {output.dependencyHint && (
                        <span className="mt-1.5 block text-xs text-brand">
                          Requires: {output.dependencyHint}
                        </span>
                      )}
                    </div>
                  </label>
                )
              })}
            </div>
          </Card>
        ))}
      </div>

      {/* Selection behavior callout card */}
      <Card className="border-default bg-surface p-6 space-y-2">
        <h3 className="text-card-heading font-semibold text-content-primary">
          Selection behavior
        </h3>
        <p className="text-sm text-content-secondary">
          Only selected outputs are generated, validated, persisted, and displayed.
        </p>
        <p className="text-sm text-brand">
          Cross-artifact checks are selection-aware: Agent 2 never requires an artifact that the user did not request.
        </p>
      </Card>

      {/* Conditional validation warning if planning inputs are missing */}
      {hasPlanningIssues && (
        <div
          role="note"
          aria-label="Planning requirements warning"
          className="rounded-card border border-state-warning/40 bg-state-warning-soft p-4 text-sm text-state-warning"
        >
          <strong className="font-semibold">Planning parameters required:</strong> Selected outputs include sprint or assignment deliverables. You will configure team count and sprint duration in Node 3 (Technical & Planning).
        </div>
      )}

      {/* Error alert if outputs validation failed */}
      {errors.outputs && (
        <div
          role="alert"
          className="rounded-card border border-state-danger/50 bg-state-danger/10 p-4 text-sm font-medium text-state-danger"
        >
          {errors.outputs}
        </div>
      )}

      {/* Footer navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default/60 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={handleBack}
          className="border-default bg-surface text-content-primary hover:bg-elevated"
        >
          Back — Project & Specifications
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={handleContinue}
        >
          Next — Technical & Planning
        </Button>
      </div>
    </div>
  )
}
