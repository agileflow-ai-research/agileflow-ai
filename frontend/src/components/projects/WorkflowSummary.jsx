import { formatEnumLabel } from '../../utils/workflowPresentation.js'
import Card from '../ui/Card.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import WorkflowBadge from '../ui/WorkflowBadge.jsx'

function SummaryItem({ label, children }) {
  return (
    <div className="min-w-0 rounded-control border border-default bg-elevated p-4">
      <dt className="text-helper-copy font-semibold uppercase tracking-wide text-content-muted">
        {label}
      </dt>
      <dd className="mt-2 text-sm text-content-primary">{children}</dd>
    </div>
  )
}

function WorkflowSummary({
  currentStage,
  currentStageOwner,
  nextStage,
  nextStageOwner,
  nextTransitionAvailable,
  approvalGate,
}) {
  return (
    <section aria-labelledby="workflow-summary-heading">
      <Card>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2
            id="workflow-summary-heading"
            className="text-section-heading font-semibold text-content-primary"
          >
            Central SDLC Orchestrator
          </h2>
          <p className="mt-1 text-sm text-content-secondary">
            Read-only workflow state reported by the Orchestrator.
          </p>
        </div>
        <StatusBadge
          label={
            nextTransitionAvailable
              ? 'Ready to continue'
              : nextStage
                ? 'Waiting for prerequisite'
                : 'Workflow complete'
          }
          tone={nextTransitionAvailable ? 'success' : nextStage ? 'warning' : 'neutral'}
        />
      </div>

      <dl className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryItem label="Current stage">
          <div className="space-y-2">
            <WorkflowBadge stage={currentStage} />
            <p className="break-words text-content-secondary">
              {currentStageOwner || 'Owner not available'}
            </p>
          </div>
        </SummaryItem>

        <SummaryItem label="Next stage">
          {nextStage ? (
            <div className="space-y-2">
              <WorkflowBadge stage={nextStage} />
              <p className="break-words text-content-secondary">
                {nextStageOwner || 'Owner not available'}
              </p>
            </div>
          ) : (
            <span className="text-content-secondary">No next stage</span>
          )}
        </SummaryItem>

        <SummaryItem label="Transition availability">
          <span className="font-medium">
            {nextTransitionAvailable
              ? 'Ready to continue'
              : nextStage
                ? 'Waiting for prerequisite'
                : 'Workflow complete'}
          </span>
        </SummaryItem>

        {approvalGate ? (
          <SummaryItem label="Approval gate">
            <StatusBadge label={formatEnumLabel(approvalGate)} tone="warning" />
          </SummaryItem>
        ) : null}
      </dl>
      </Card>
    </section>
  )
}

export default WorkflowSummary
