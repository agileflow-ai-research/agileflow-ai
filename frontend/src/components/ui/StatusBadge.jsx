import { cn } from '../../utils/cn.js'

const toneClasses = {
  neutral: 'border-default bg-elevated text-content-secondary',
  info: 'border-state-info/40 bg-state-info/10 text-state-info',
  success: 'border-state-success/40 bg-state-success/10 text-state-success',
  warning: 'border-state-warning/40 bg-state-warning/10 text-state-warning',
  danger: 'border-state-danger/40 bg-state-danger/10 text-state-danger',
  accent: 'border-accent-border/50 bg-brand-soft text-highlight',
}

const dotClasses = {
  neutral: 'bg-content-muted',
  info: 'bg-state-info',
  success: 'bg-state-success',
  warning: 'bg-state-warning',
  danger: 'bg-state-danger',
  accent: 'bg-highlight',
}

function StatusBadge({ label, tone = 'neutral', className }) {
  const safeTone = toneClasses[tone] ? tone : 'neutral'

  return (
    <span
      data-tone={safeTone}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1 text-xs font-semibold',
        toneClasses[safeTone],
        className,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', dotClasses[safeTone])} aria-hidden="true" />
      {label}
    </span>
  )
}

export default StatusBadge
