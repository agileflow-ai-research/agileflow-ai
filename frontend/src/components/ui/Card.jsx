import { cn } from '../../utils/cn.js'

const variantClasses = {
  default: 'border-default bg-surface',
  elevated: 'border-default bg-elevated shadow-surface',
  interactive:
    'border-default bg-surface transition-colors hover:border-accent-border hover:bg-elevated',
}

function Card({ variant = 'default', className, children, ...cardProps }) {
  return (
    <div
      {...cardProps}
      data-variant={variant}
      className={cn(
        'rounded-card border p-card',
        variantClasses[variant] ?? variantClasses.default,
        className,
      )}
    >
      {children}
    </div>
  )
}

export default Card
