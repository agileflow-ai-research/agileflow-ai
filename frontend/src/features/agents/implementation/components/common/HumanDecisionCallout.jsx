export default function HumanDecisionCallout({ eyebrow = 'Your review is required', title, description, evidence, outcome, children }) {
  return (
    <section className="rounded-control border border-state-warning/40 bg-state-warning/10 p-4" aria-label="Human decision required">
      <p className="text-xs font-semibold uppercase tracking-wider text-state-warning">{eyebrow}</p>
      <h3 className="mt-2 text-card-heading font-semibold text-content-primary">{title}</h3>
      {description ? <p className="mt-2 text-sm text-content-secondary">{description}</p> : null}
      {evidence ? <div className="mt-3 rounded-control border border-default bg-surface/60 p-3 text-sm text-content-secondary"><span className="font-medium text-content-primary">Evidence: </span>{evidence}</div> : null}
      {outcome ? <p className="mt-3 text-sm text-content-secondary"><span className="font-medium text-content-primary">After your decision: </span>{outcome}</p> : null}
      {children ? <div className="mt-4">{children}</div> : null}
    </section>
  )
}
