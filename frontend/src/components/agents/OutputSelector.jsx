import { cn } from '../../utils/cn.js'

function OutputSelector({ options, selectedValues, onChange, label = 'Select outputs' }) {
  const selected = new Set(selectedValues ?? [])

  function toggle(value) {
    const next = new Set(selected)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    onChange?.([...next])
  }

  return (
    <fieldset>
      <legend className="text-card-heading font-semibold text-content-primary">{label}</legend>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {(options ?? []).map((option) => {
          const isSelected = selected.has(option.value)
          const descriptionId = `${option.value}-output-description`
          return (
            <label
              key={option.value}
              className={cn(
                'flex cursor-pointer gap-3 rounded-card border p-4 transition-colors',
                isSelected ? 'border-accent-border bg-brand-soft' : 'border-default bg-elevated',
                option.disabled && 'cursor-not-allowed opacity-60',
              )}
            >
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 accent-brand"
                checked={isSelected}
                disabled={option.disabled}
                aria-describedby={descriptionId}
                onChange={() => toggle(option.value)}
              />
              <span>
                <span className="block text-sm font-semibold text-content-primary">
                  {option.label}
                </span>
                <span id={descriptionId} className="mt-1 block text-helper-copy text-content-muted">
                  {option.disabled && option.disabledReason
                    ? option.disabledReason
                    : option.description}
                </span>
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

export default OutputSelector
