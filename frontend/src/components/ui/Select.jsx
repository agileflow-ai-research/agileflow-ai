import { useId } from 'react'

import { cn } from '../../utils/cn.js'
import { fieldControlClasses } from './Input.jsx'

function Select({
  id,
  label,
  options = [],
  placeholder = 'Select an option',
  error,
  helperText,
  required = false,
  disabled = false,
  className,
  selectClassName,
  ...selectProps
}) {
  const generatedId = useId()
  const selectId = id ?? generatedId
  const helperId = helperText ? `${selectId}-helper` : undefined
  const errorId = error ? `${selectId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('w-full', className)}>
      <label className="mb-2 block text-label-copy font-medium text-content-primary" htmlFor={selectId}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      <select
        {...selectProps}
        id={selectId}
        required={required}
        disabled={disabled}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={describedBy}
        className={cn(
          fieldControlClasses,
          error && 'border-state-danger',
          selectClassName,
        )}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
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

export default Select
