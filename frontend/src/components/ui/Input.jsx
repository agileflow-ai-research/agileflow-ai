import { useId } from 'react'

import { cn } from '../../utils/cn.js'

export const fieldControlClasses =
  'w-full rounded-control border border-default bg-control px-3 py-2.5 text-content-primary outline-none transition-colors placeholder:text-content-muted focus:border-accent-border focus:ring-2 focus:ring-accent-border/20 disabled:cursor-not-allowed disabled:opacity-60'

function Input({
  id,
  label,
  error,
  helperText,
  required = false,
  disabled = false,
  className,
  inputClassName,
  trailingContent,
  ...inputProps
}) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const helperId = helperText ? `${inputId}-helper` : undefined
  const errorId = error ? `${inputId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('w-full', className)}>
      <label className="mb-2 block text-label-copy font-medium text-content-primary" htmlFor={inputId}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      <div className="relative">
        <input
          {...inputProps}
          id={inputId}
          required={required}
          disabled={disabled}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={describedBy}
          className={cn(
            fieldControlClasses,
            trailingContent && 'pr-20',
            error && 'border-state-danger',
            inputClassName,
          )}
        />
        {trailingContent && (
          <div className="absolute inset-y-0 right-2 flex items-center">{trailingContent}</div>
        )}
      </div>
      {helperText && (
        <p id={helperId} className="mt-1.5 text-helper-copy text-content-muted">
          {helperText}
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1.5 text-helper-copy text-state-danger">
          {error}
        </p>
      )}
    </div>
  )
}

export default Input
