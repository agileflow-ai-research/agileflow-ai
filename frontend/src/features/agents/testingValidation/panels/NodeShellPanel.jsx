function NodeShellPanel({ definition, availability, children, note }) {
  return (
    <section className="space-y-5" aria-label={`${definition.title} details`}>
      <div>
        <h3 className="text-card-heading font-semibold text-content-primary">{definition.title}</h3>
        <p className="mt-2 text-sm text-content-secondary">{definition.purpose}</p>
      </div>
      <div className="rounded-control border border-default bg-elevated p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">Current availability</p>
        <p className="mt-1 font-semibold text-content-primary">{availability}</p>
      </div>
      {children}
      <div>
        <h4 className="font-semibold text-content-primary">Future internal stages</h4>
        <ul className="mt-2 grid gap-2 sm:grid-cols-2">
          {definition.futureStages.map((stage) => (
            <li key={stage} className="rounded-control border border-default bg-surface px-3 py-2 text-sm text-content-secondary">{stage}</li>
          ))}
        </ul>
      </div>
      <p className="rounded-control border border-default bg-brand-soft p-4 text-sm text-content-secondary">{note}</p>
    </section>
  )
}

export default NodeShellPanel
