import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import {
  getPlanningErrors,
  hasAtLeastOneSpecification,
} from '../constants/agent2Config.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

const pipelineStages = [
  'Input validation',
  'Normalization',
  'Agent2Engine',
  'Structured generation',
  'Consistency validation',
  'Correction',
  'Persist results',
]

export default function GenerateDesignPlanningPanel({
  project,
  input = {},
  selectedOutputs = [],
  humanReviewApproved = false,
  runState = 'idle',
  runResult = null,
  runError = '',
  onExecuteRun,
  onNavigate,
  onResetRun,
}) {
  const hasSpecs = hasAtLeastOneSpecification(input)
  const hasOutputs = selectedOutputs.length > 0
  const planningIssues = getPlanningErrors(input, selectedOutputs)
  const isPlanningValid = Object.keys(planningIssues).length === 0
  const isApproved = humanReviewApproved

  const canRun = hasSpecs && hasOutputs && isPlanningValid && isApproved
  const isRunning = runState === 'running'

  return (
    <div className="space-y-6" data-testid="agent2-panel-GENERATE_DESIGN_PLANNING">
      {/* Prerequisite Check / Blocked Banner */}
      {!canRun && runState === 'idle' && (
        <div
          role="alert"
          aria-label="Execution prerequisites blocked"
          className="rounded-panel border border-state-danger/50 bg-state-danger/10 p-5 space-y-3"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-state-danger font-bold text-base" aria-hidden="true">
                ⚠️
              </span>
              <h3 className="font-semibold text-state-danger">
                Execution Blocked — Human Review Prerequisites Incomplete
              </h3>
            </div>
            <StatusBadge label="Blocked" tone="danger" />
          </div>
          <p className="text-sm text-content-secondary">
            Before launching Agent 2 generation, all upstream specifications, planning inputs, and output selections must be verified and approved in Node 4 (Human Review).
          </p>
          <div className="pt-1">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)}
            >
              Go to Human Review (Node 4)
            </Button>
          </div>
        </div>
      )}

      {/* Execution Pipeline Card (Matches S2-05) */}
      <Card className="border-default bg-[#150c2a] p-5 space-y-3">
        <div>
          <h3 className="text-card-heading font-semibold text-content-primary">
            Execution pipeline
          </h3>
          <p className="mt-1 text-sm text-content-muted">
            Provider generation is combined with deterministic checks.
          </p>
        </div>
        <div
          className="flex flex-wrap items-center gap-2 pt-1"
          aria-label="Execution pipeline stages"
        >
          {pipelineStages.map((stage) => (
            <span
              key={stage}
              className="inline-flex items-center gap-1.5 rounded-control border border-[#3c2463] bg-[#211438] px-3 py-1.5 text-xs font-medium text-content-primary"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden="true" />
              {stage}
            </span>
          ))}
        </div>
      </Card>

      {/* State: IDLE & Ready to Run */}
      {runState === 'idle' && canRun && (
        <Card className="border border-default bg-[#150c2a] p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-default/40 pb-4">
            <div>
              <h3 className="text-card-heading font-semibold text-content-primary">
                Ready to launch Agent 2 generation
              </h3>
              <p className="mt-1 text-sm text-content-muted">
                Specifications, planning inputs, and output deliverables are verified.
              </p>
            </div>
            <StatusBadge label="Ready to Run" tone="success" />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 text-sm">
            <div className="rounded-control border border-default bg-[#0b0517] p-3.5 space-y-1">
              <span className="block text-xs font-medium text-content-muted">Model Provider</span>
              <span className="block font-medium text-content-primary">
                Qwen (Local llama.cpp inference via 127.0.0.1:8080)
              </span>
            </div>
            <div className="rounded-control border border-default bg-[#0b0517] p-3.5 space-y-1">
              <span className="block text-xs font-medium text-content-muted">Selected Outputs ({selectedOutputs.length})</span>
              <span className="block font-mono text-xs text-[#a78bfa] truncate" title={selectedOutputs.join(', ')}>
                {selectedOutputs.join(', ')}
              </span>
            </div>
          </div>

          <div className="pt-2">
            <Button
              type="button"
              variant="primary"
              size="large"
              disabled={!canRun || isRunning}
              onClick={onExecuteRun}
            >
              Start Agent 2 Generation
            </Button>
          </div>
        </Card>
      )}

      {/* State: RUNNING */}
      {runState === 'running' && (
        <div className="space-y-6">
          <Card className="border border-brand/50 bg-[#241344]/80 p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-default/40 pb-4">
              <div className="flex items-center gap-3">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-brand-purple border-t-transparent" />
                <div>
                  <h3 className="text-card-heading font-semibold text-content-primary">
                    Agent 2 is Processing
                  </h3>
                  <p className="mt-0.5 text-xs text-content-muted">
                    Autonomous design and planning pipeline executing against local Qwen inference.
                  </p>
                </div>
              </div>
              <StatusBadge label="RUNNING" tone="info" />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {/* Current activity card */}
              <div className="rounded-control border border-default bg-[#0b0517] p-4 space-y-2">
                <h4 className="text-sm font-semibold text-content-primary">Current activity</h4>
                <p className="text-xs text-content-secondary">
                  Generating and validating the selected Agent 2 outputs.
                </p>
                <ul className="mt-2 space-y-1 text-xs text-content-muted">
                  <li>• Evaluating consistency across {selectedOutputs.length} selected artifact{selectedOutputs.length === 1 ? '' : 's'}.</li>
                  <li>• Deterministic verification in progress.</li>
                </ul>
              </div>

              {/* Run evidence card */}
              <div className="rounded-control border border-default bg-[#0b0517] p-4 space-y-2">
                <h4 className="text-sm font-semibold text-content-primary">Run evidence</h4>
                <p className="text-xs text-content-secondary">
                  Safe machine-readable state only.
                </p>
                <ul className="mt-2 space-y-1 text-xs text-content-muted" aria-label="Run evidence details">
                  <li>
                    • Run status: <span className="font-semibold text-[#fbbf24]">RUNNING</span>
                  </li>
                  <li>
                    • Project: {project?.name || 'Project'}
                    {project?.domain ? ` · ${project.domain}` : ''}
                  </li>
                  <li>
                    • Selected outputs ({selectedOutputs.length}): {selectedOutputs.join(', ')}
                  </li>
                  {Number(input.development_team_count) > 0 && (
                    <li>• Development team count: {input.development_team_count}</li>
                  )}
                  {Number(input.sprint_duration) > 0 && (
                    <li>• Sprint duration: {input.sprint_duration} days</li>
                  )}
                </ul>
              </div>
            </div>

            <div className="pt-2">
              <Button
                type="button"
                variant="primary"
                size="large"
                disabled
                loading
                loadingLabel="Processing with local Qwen..."
              >
                Generating...
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* State: COMPLETED */}
      {runState === 'completed' && runResult && (
        <Card className="border border-[#065f46] bg-[#064e3b]/20 p-6 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-default/40 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[#34d399] font-bold text-lg">✓</span>
                <h3 className="text-card-heading font-semibold text-content-primary">
                  Agent 2 Execution Completed
                </h3>
              </div>
              <p className="mt-1 text-xs text-content-muted">
                Run ID: <span className="font-mono text-content-primary">{runResult.run_id}</span>
              </p>
            </div>
            <StatusBadge label="COMPLETED" tone="success" />
          </div>

          <div className="grid gap-3 sm:grid-cols-3 text-xs">
            <div className="rounded-control border border-default bg-[#0b0517] p-3 space-y-1">
              <span className="text-content-muted">Outputs Generated</span>
              <p className="text-base font-semibold text-content-primary">
                {Object.keys(runResult.outputs || {}).length} of {runResult.selected_outputs?.length ?? selectedOutputs.length}
              </p>
            </div>
            <div className="rounded-control border border-default bg-[#0b0517] p-3 space-y-1">
              <span className="text-content-muted">Correction Attempts</span>
              <p className="text-base font-semibold text-content-primary">
                {runResult.correction_attempts ?? 0}
              </p>
            </div>
            <div className="rounded-control border border-default bg-[#0b0517] p-3 space-y-1">
              <span className="text-content-muted">Execution Mode</span>
              <p className="text-base font-semibold text-content-primary">
                {runResult.run_mode || 'STANDALONE'}
              </p>
            </div>
          </div>

          {runResult.warnings?.length > 0 && (
            <div className="rounded-control border border-[#b45309]/50 bg-[#78350f]/20 p-3 text-xs text-[#fbbf24] space-y-1">
              <strong className="block font-semibold">Warnings ({runResult.warnings.length}):</strong>
              <ul className="list-disc pl-4 space-y-0.5">
                {runResult.warnings.map((w, i) => (
                  <li key={i}>{w.message || w}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button
              type="button"
              variant="primary"
              onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS)}
            >
              View Design Results (Node 6)
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS)}
              className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
            >
              View Planning Results (Node 7)
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onResetRun}
              className="text-xs text-content-muted hover:text-content-primary"
            >
              Start another run
            </Button>
          </div>
        </Card>
      )}

      {/* State: FAILED */}
      {runState === 'failed' && (
        <Card className="border border-state-danger/50 bg-state-danger/10 p-6 space-y-4" role="alert">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-default/40 pb-4">
            <div className="flex items-center gap-2">
              <span className="text-state-danger font-bold text-lg" aria-hidden="true">✕</span>
              <h3 className="text-card-heading font-semibold text-state-danger">
                Agent 2 Execution Failed
              </h3>
            </div>
            <StatusBadge label="FAILED" tone="danger" />
          </div>

          <p className="text-sm text-state-danger">
            {runError || 'The design and planning run could not be completed.'}
          </p>

          {runResult?.correction_attempts !== undefined && (
            <p className="text-xs text-content-muted">
              Correction attempts consumed: <span className="font-semibold">{runResult.correction_attempts}</span>
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button
              type="button"
              variant="primary"
              onClick={onExecuteRun}
            >
              Retry Generation
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)}
              className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
            >
              Back to Human Review
            </Button>
          </div>
        </Card>
      )}

      {/* Safety note card (Matches S2-05) */}
      <Card className="border border-[#1e3a8a]/60 bg-[#0c1836]/70 p-4 space-y-1">
        <p className="text-sm font-medium text-[#93c5fd]">
          Deterministic user-input errors are rejected before model execution and do not consume correction attempts.
        </p>
        <p className="text-xs text-[#60a5fa]/80">
          Generated-output correction is bounded by the existing engine policy. No internal prompts, chain-of-thought, or provider secrets are exposed.
        </p>
      </Card>

      {/* Footer navigation */}
      <div className="flex justify-between border-t border-default/60 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)}
          disabled={isRunning}
          className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
        >
          Back — Human Review
        </Button>
      </div>
    </div>
  )
}
