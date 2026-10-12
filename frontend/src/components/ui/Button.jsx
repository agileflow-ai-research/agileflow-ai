import { cn } from '../../utils/cn.js'
import Spinner from './Spinner.jsx'

const variantClasses = {
  primary: 'bg-brand text-content-primary shadow-brand-glow hover:bg-brand-hover',
  secondary: 'bg-elevated text-content-primary hover:bg-brand-soft',
  outline:
    'border border-accent-border bg-transparent text-content-primary hover:bg-brand-soft',
  ghost: 'bg-transparent text-content-secondary hover:bg-elevated hover:text-content-primary',
  danger: 'bg-state-danger text-content-primary hover:opacity-90',
}

const sizeClasses = {
  small: 'min-h-10 px-3 py-2 text-sm',
  medium: 'min-h-10 px-4 py-2.5 text-sm',
  large: 'min-h-11 px-5 py-3 text-base',
}

function Button({
  variant = 'primary',
  size = 'medium',
  disabled = false,
  loading = false,
  loadingLabel = 'Loading',
  type = 'button',
  className,
  children,
  ...buttonProps
}) {
  const isDisabled = disabled || loading

  return (
    <button
      {...buttonProps}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      aria-label={loading ? loadingLabel : buttonProps['aria-label']}
      data-variant={variant}
      className={cn(
        'relative inline-flex items-center justify-center gap-2 rounded-button font-semibold transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variantClasses[variant] ?? variantClasses.primary,
        sizeClasses[size] ?? sizeClasses.medium,
        className,
      )}
    >
      {loading && (
        <Spinner
          size="small"
          label={loadingLabel}
          className="absolute"
        />
      )}
      <span className={cn(loading && 'invisible')} aria-hidden={loading || undefined}>
        {children}
      </span>
    </button>
  )
}

export default Button
