import { DisclosureSection, NextStep } from './NodePresentation.jsx'

function NodeShellPanel({ definition, availability, children, hideAvailability = true, hideHeader = true, note, showWorkflowStages = true }) {
  return (
    <section className="space-y-5" aria-label={`${definition.title} details`}>
      {!hideHeader ? <div>
        <h3 className="text-card-heading font-semibold text-content-primary">{definition.title}</h3>
        <p className="mt-2 text-sm text-content-secondary">{definition.purpose}</p>
      </div> : null}
      {!hideAvailability ? <div className="rounded-control border border-default bg-elevated p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">Current availability</p>
        <p className="mt-1 font-semibold text-content-primary">{availability}</p>
      </div> : null}
      {children}
      {showWorkflowStages && definition.futureStages?.length ? <DisclosureSection title="How Agent 4 reached this result" summary="Processing stages and research workflow">
        <ol className="grid gap-2 sm:grid-cols-2">
          {definition.futureStages.map((stage, index) => (
            <li key={stage} className="rounded-control border border-default bg-elevated px-3 py-2 text-sm text-content-secondary"><span className="mr-2 text-content-muted">{index + 1}.</span>{stage}</li>
          ))}
        </ol>
      </DisclosureSection> : null}
      <NextStep>{note}</NextStep>
    </section>
  )
}

export default NodeShellPanel
