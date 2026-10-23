import { useId } from 'react'

import { cn } from '../../utils/cn.js'
import { fieldControlClasses } from './Input.jsx'

function Textarea({
  id,
  label,
  error,
  helperText,
  required = false,
  disabled = false,
  rows = 5,
  className,
  textareaClassName,
  labelClassName,
  ...textareaProps
}) {
  const generatedId = useId()
  const textareaId = id ?? generatedId
  const helperId = helperText ? `${textareaId}-helper` : undefined
  const errorId = error ? `${textareaId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('w-full', className)}>
      {label && (
        <label
          className={cn(
            'mb-2 block text-label-copy font-medium text-content-primary',
            labelClassName,
          )}
          htmlFor={textareaId}
        >
          {label}
          {required && <span aria-hidden="true"> *</span>}
        </label>
      )}
      <textarea
        {...textareaProps}
        id={textareaId}
        rows={rows}
        required={required}
        disabled={disabled}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={describedBy}
        className={cn(
          fieldControlClasses,
          'min-h-28 resize-y leading-relaxed',
          error && 'border-state-danger',
          textareaClassName,
        )}
      />
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

export default Textarea
