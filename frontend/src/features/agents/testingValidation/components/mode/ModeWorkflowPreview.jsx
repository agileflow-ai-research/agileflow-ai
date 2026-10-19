import {
  AGENT4_MODES,
  TEST_GENERATION_WORKFLOW,
  VALIDATION_WORKFLOW,
  WORKFLOW_STATUS_LABELS,
} from '../../constants/workspace.js'

const workflowNotes = {
  TEST_GENERATION: 'Inputs are available now. The later stages are not yet functional and do not run.',
  VALIDATION: 'Validation is a separate workflow with its own inputs and outputs. Its execution pipeline is not part of the current rebuild, and nothing in this preview runs code.',
}

function ModeWorkflowPreview({ mode }) {
  const workflow = mode === 'TEST_GENERATION' ? TEST_GENERATION_WORKFLOW : VALIDATION_WORKFLOW
  const label = AGENT4_MODES[mode].label

  return (
    <section className="space-y-4">
      <p className="text-sm text-content-secondary">{workflowNotes[mode]}</p>
      <ol aria-label={`${label} workflow preview`} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {workflow.map((stage, index) => (
          <li
            key={stage.id}
            aria-current={stage.status === 'ACTIVE' ? 'step' : undefined}
            className={stage.status === 'ACTIVE'
              ? 'rounded-control border border-accent-border bg-brand-soft p-4'
              : 'rounded-control border border-default bg-elevated p-4'}
          >
            <span className="text-xs text-content-muted">Step {index + 1}</span>
            <span className="mt-1 block font-semibold text-content-primary">{stage.label}</span>
            <span className="mt-2 block text-xs text-content-secondary">{WORKFLOW_STATUS_LABELS[stage.status]}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

export default ModeWorkflowPreview
