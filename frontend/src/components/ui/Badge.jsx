import { cn } from '../../utils/cn.js'

const toneClasses = {
  neutral: 'border-default bg-elevated text-content-secondary',
  accent: 'border-accent-border bg-brand-soft text-content-primary',
  info: 'border-state-info/40 bg-state-info-soft text-state-info',
}

function Badge({ tone = 'neutral', className, children }) {
  return (
    <span
      data-tone={tone}
      className={cn(
        'inline-flex items-center rounded-control border px-2 py-1 text-xs font-medium',
        toneClasses[tone] ?? toneClasses.neutral,
        className,
      )}
    >
      {children}
    </span>
  )
}

export default Badge
