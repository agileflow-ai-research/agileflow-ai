import { AGENT4_MODES } from '../../constants/workspace.js'

function ModeSelectionStep({ onSelect }) {
  return (
    <section aria-labelledby="agent4-mode-title" className="space-y-4">
      <div>
        <h3 id="agent4-mode-title" className="text-card-heading font-semibold text-content-primary">
          Choose a mode
        </h3>
        <p className="mt-1 text-sm text-content-secondary">
          Each mode has its own inputs, outputs, and workflow. Choose one before continuing.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.values(AGENT4_MODES).map((mode) => (
          <button
            key={mode.value}
            type="button"
            onClick={() => onSelect(mode.value)}
            className="rounded-card border border-default bg-elevated p-5 text-left transition-colors hover:border-accent-border"
          >
            <span className="block font-semibold text-content-primary">{mode.label}</span>
            <span className="mt-2 block text-sm text-content-secondary">{mode.description}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default ModeSelectionStep
