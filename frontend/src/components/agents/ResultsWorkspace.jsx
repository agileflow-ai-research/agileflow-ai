import Card from '../ui/Card.jsx'

function ResultsWorkspace({ title = 'Results', sections = [], warnings = [], errors = [], actions }) {
  return (
    <section aria-labelledby="results-workspace-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="results-workspace-title" className="text-section-heading font-semibold text-content-primary">
          {title}
        </h2>
        {actions && <div>{actions}</div>}
      </div>

      {warnings.length > 0 && (
        <Card className="border-state-warning/40 bg-state-warning-soft">
          <h3 className="font-semibold text-content-primary">Warnings</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-body-copy text-content-secondary">
            {warnings.map((warning, index) => <li key={`${index}-${String(warning)}`}>{String(warning)}</li>)}
          </ul>
        </Card>
      )}

      {errors.length > 0 && (
        <Card className="border-state-danger/40 bg-state-danger-soft">
          <h3 className="font-semibold text-content-primary">Errors</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-body-copy text-content-secondary">
            {errors.map((error, index) => <li key={`${index}-${String(error)}`}>{String(error)}</li>)}
          </ul>
        </Card>
      )}

      <div className="space-y-4">
        {sections.map((section) => (
          <Card key={section.id ?? section.title}>
            <h3 className="font-semibold text-content-primary">{section.title}</h3>
            <div className="mt-3">{section.content}</div>
          </Card>
        ))}
      </div>
    </section>
  )
}

export default ResultsWorkspace
