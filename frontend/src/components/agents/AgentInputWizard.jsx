import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'

function AgentInputWizard({
  steps,
  currentStep,
  children,
  onBack,
  onNext,
  backLabel = 'Back',
  nextLabel = 'Next',
  nextDisabled = false,
}) {
  const safeSteps = Array.isArray(steps) ? steps : []
  const activeIndex = Math.max(0, Math.min(currentStep, safeSteps.length - 1))

  return (
    <Card>
      <ol className="grid gap-2 sm:grid-cols-3" aria-label="Agent input steps">
        {safeSteps.map((step, index) => (
          <li
            key={step.id ?? step.label}
            aria-current={index === activeIndex ? 'step' : undefined}
            className={
              index === activeIndex
                ? 'rounded-control border border-accent-border bg-brand-soft px-3 py-2 text-sm font-semibold text-content-primary'
                : 'rounded-control border border-default bg-elevated px-3 py-2 text-sm text-content-secondary'
            }
          >
            <span className="mr-2 text-content-muted">{index + 1}.</span>
            {step.label}
          </li>
        ))}
      </ol>

      <div className="mt-6">{children}</div>

      <div className="mt-6 flex flex-wrap justify-between gap-3">
        <Button variant="ghost" onClick={onBack} disabled={!onBack}>
          {backLabel}
        </Button>
        <Button onClick={onNext} disabled={!onNext || nextDisabled}>
          {nextLabel}
        </Button>
      </div>
    </Card>
  )
}

export default AgentInputWizard
