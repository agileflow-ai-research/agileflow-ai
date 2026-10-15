import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import { cn } from '../../utils/cn.js'

function AgentInputWizard({
  steps,
  currentStep,
  children,
  onBack,
  onNext,
  backLabel = 'Back',
  nextLabel = 'Next',
  nextDisabled = false,
  actions,
  className,
}) {
  const safeSteps = Array.isArray(steps) ? steps : []
  const activeIndex = Math.max(0, Math.min(currentStep, safeSteps.length - 1))

  return (
    <Card className={cn('p-card', className)}>
      <ol
        className={`grid gap-3 ${safeSteps.length === 5 ? 'grid-cols-2 sm:grid-cols-5' : 'sm:grid-cols-3'}`}
        aria-label="Agent input steps"
      >
        {safeSteps.map((step, index) => (
          <li
            key={step.id ?? step.label}
            aria-current={index === activeIndex ? 'step' : undefined}
            className={
              index === activeIndex
                ? 'min-h-[68px] rounded-card border border-accent-border bg-[#251642] p-4 text-sm font-semibold text-content-primary transition-colors'
                : 'min-h-[68px] rounded-card border border-default bg-[#140b27] p-4 text-sm font-medium text-content-secondary transition-colors'
            }
          >
            <span className="mr-2 text-content-muted">{index + 1}</span>
            <span>{step.label}</span>
          </li>
        ))}
      </ol>

      <div className="mt-6">{children}</div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        {actions ?? (
          <>
            <Button variant="ghost" onClick={onBack} disabled={!onBack}>
              {backLabel}
            </Button>
            <Button onClick={onNext} disabled={!onNext || nextDisabled}>
              {nextLabel}
            </Button>
          </>
        )}
      </div>
    </Card>
  )
}

export default AgentInputWizard
