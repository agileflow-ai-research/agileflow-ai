import { sanitizeDisplayText } from '../displayText.js'

const toneClasses = Object.freeze({
  neutral: 'border-default bg-elevated',
  info: 'border-accent-border bg-brand-soft',
  success: 'border-state-success/40 bg-state-success/10',
  warning: 'border-state-warning/40 bg-state-warning/10',
  danger: 'border-state-danger/40 bg-state-danger/10',
})

export function PresentationSection({ children, description, label, title }) {
  if (!children) return null
  return <section className="space-y-3">
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">{sanitizeDisplayText(label)}</p>
      {title ? <h3 className="mt-1 text-card-heading font-semibold text-content-primary">{sanitizeDisplayText(title)}</h3> : null}
      {description ? <p className="mt-1 text-sm text-content-secondary">{sanitizeDisplayText(description)}</p> : null}
    </div>
    {children}
  </section>
}

export function ResultBanner({ description, metrics = [], title, tone = 'neutral' }) {
  return <div role={tone === 'danger' ? 'alert' : 'status'} className={`rounded-control border p-4 ${toneClasses[tone] ?? toneClasses.neutral}`}>
    <p className="text-lg font-semibold text-content-primary">{sanitizeDisplayText(title)}</p>
    {description ? <p className="mt-1 text-sm text-content-secondary">{sanitizeDisplayText(description)}</p> : null}
    {metrics.length ? <dl className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{metrics.map((metric) => <div key={metric.label} className="rounded-control bg-surface/60 p-3"><dt className="text-xs uppercase tracking-wide text-content-muted">{sanitizeDisplayText(metric.label)}</dt><dd className="mt-1 text-xl font-semibold text-content-primary">{sanitizeDisplayText(metric.value)}</dd></div>)}</dl> : null}
  </div>
}

export function DisclosureSection({ children, summary, title }) {
  if (!children) return null
  return <details className="group overflow-hidden rounded-control border border-default bg-surface">
    <summary className="cursor-pointer list-none p-3 sm:p-4">
      <span className="flex items-center justify-between gap-4">
        <span><span className="block font-semibold text-content-primary">{sanitizeDisplayText(title)}</span>{summary ? <span className="mt-0.5 block text-sm text-content-secondary">{sanitizeDisplayText(summary)}</span> : null}</span>
        <span aria-hidden="true" className="text-content-muted transition-transform group-open:rotate-90">›</span>
      </span>
    </summary>
    <div className="border-t border-default p-3 sm:p-4">{children}</div>
  </details>
}

export function NextStep({ children }) {
  if (!children) return null
  return <section className="rounded-control border border-accent-border bg-brand-soft p-4">
    <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">Next step</p>
    <div className="mt-1 text-sm text-content-secondary">{children}</div>
  </section>
}

export function AttentionPanel({ children, title = 'Needs your attention', tone = 'warning' }) {
  return <section className={`rounded-control border p-4 ${toneClasses[tone] ?? toneClasses.warning}`}>
    <p className="font-semibold text-content-primary">{title}</p>
    <div className="mt-2 text-sm text-content-secondary">{children}</div>
  </section>
}

export function DetailLoadState({ error, onRetry, status }) {
  if (status === 'loading') return <p role="status" className="text-sm text-content-secondary">Loading persisted output...</p>
  if (status === 'error') return <div className="rounded-control border border-state-danger/40 p-3"><p className="text-sm text-state-danger">{sanitizeDisplayText(error)}</p><button type="button" className="mt-2 text-sm font-semibold text-brand-primary" onClick={onRetry}>Try again</button></div>
  return null
}

export function LoadMoreButton({ children = 'Show more', disabled, onClick }) {
  return <button type="button" className="rounded-control border border-default px-3 py-2 text-sm font-semibold text-content-primary disabled:opacity-50" disabled={disabled} onClick={onClick}>{children}</button>
}
