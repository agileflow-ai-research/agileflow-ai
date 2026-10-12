import { cn } from '../../utils/cn.js'

const sizeClasses = {
  small: 'h-4 w-4 border-2',
  medium: 'h-6 w-6 border-2',
  large: 'h-9 w-9 border-3',
}

function Spinner({ size = 'medium', label = 'Loading', className }) {
  return (
    <span
      className={cn(
        'inline-block animate-spin rounded-full border-current border-r-transparent motion-reduce:animate-none',
        sizeClasses[size] ?? sizeClasses.medium,
        className,
      )}
      role="status"
      aria-label={label}
    />
  )
}

export default Spinner
