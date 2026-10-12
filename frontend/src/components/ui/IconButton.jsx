import { cn } from '../../utils/cn.js'

function IconButton({ label, className, type = 'button', children, ...buttonProps }) {
  return (
    <button
      {...buttonProps}
      type={type}
      aria-label={label}
      className={cn(
        'inline-flex min-h-10 min-w-10 items-center justify-center rounded-button text-content-secondary',
        'transition-colors hover:bg-elevated hover:text-content-primary disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
    >
      {children}
    </button>
  )
}

export default IconButton
