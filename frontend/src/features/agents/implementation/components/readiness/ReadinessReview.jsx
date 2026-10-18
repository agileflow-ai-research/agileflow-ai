import Button from '../../../../../components/ui/Button.jsx'
import Card from '../../../../../components/ui/Card.jsx'

const readinessLabels = {
  READY: 'READY',
  READY_WITH_WARNINGS: 'READY WITH WARNINGS',
  NOT_READY: 'NOT READY',
}

export default function ReadinessReview({ state, onAdapt, onBack }) {
  const result = state.result
  if (!result) return null
  const grouped = {
    ERROR: result.findings.filter((item) => item.severity === 'ERROR' && !item.resolved),
    WARNING: result.findings.filter((item) => item.severity === 'WARNING' && !item.resolved),
    INFO: result.findings.filter((item) => item.severity === 'INFO' && !item.resolved),
  }
  return (
    <Card aria-labelledby="implementation-readiness-title" className="space-y-5">
      <div>
        <h3 id="implementation-readiness-title" className="text-card-heading font-semibold text-content-primary">Implementation Readiness</h3>
        <p className="mt-2 font-semibold text-content-primary">{readinessLabels[result.status]}</p>
        <p className="mt-1 text-sm text-content-secondary">
          {result.summary.errors} blocking · {result.summary.warnings} warnings · {result.summary.info} information
        </p>
      </div>
      {state.stale && <p role="alert" className="text-sm text-state-warning">Inputs changed — run readiness evaluation again.</p>}
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        {[
          ['Requirements Context', result.coverage.requirements ? 'Available' : 'Missing'],
          ['Design Context', result.coverage.design ? 'Available' : 'Missing'],
          ['Technical Context', result.coverage.implementation ? 'Available' : 'Using PP1 defaults'],
          ['Pre-code Tests', result.coverage.tests ? 'Available' : 'Missing'],
          ['Visual Context', result.coverage.visual_context_pending ? 'Pending image analysis' : 'No pending images'],
        ].map(([label, value]) => (
          <div key={label}><dt className="inline font-medium text-content-primary">{label}: </dt><dd className="inline text-content-secondary">{value}</dd></div>
        ))}
      </dl>
      <section aria-labelledby="prototype-stack-title">
        <h4 id="prototype-stack-title" className="font-semibold text-content-primary">Prototype Stack</h4>
        <ul className="mt-2 grid gap-1 text-sm text-content-secondary sm:grid-cols-2">
          {Object.values(result.effective_stack).map((value) => <li key={value}>{value}</li>)}
        </ul>
      </section>
      <section aria-labelledby="output-readiness-title">
        <h4 id="output-readiness-title" className="font-semibold text-content-primary">Output Readiness</h4>
        <ul className="mt-2 space-y-1 text-sm text-content-secondary">
          {result.output_readiness.map((item) => (
            <li key={item.output}>{item.output}: {item.ready ? 'Ready' : 'Blocked'}</li>
          ))}
        </ul>
      </section>
      {[
        ['ERROR', 'Blocking Issues'], ['WARNING', 'Warnings'], ['INFO', 'Information'],
      ].map(([severity, title]) => grouped[severity].length > 0 && (
        <section key={severity} aria-label={title}>
          <h4 className="font-semibold text-content-primary">{title}</h4>
          <div className="mt-2 space-y-3">
            {grouped[severity].map((finding) => (
              <div key={finding.finding_id} className="rounded-control border border-default p-3">
                <p className="font-medium text-content-primary">{finding.title}</p>
                <p className="mt-1 text-xs font-semibold text-content-muted">{finding.code}</p>
                <p className="mt-1 text-sm text-content-secondary">{finding.message}</p>
                {finding.provided_value && <p className="mt-2 text-sm text-content-secondary">Provided: {finding.provided_value}</p>}
                {finding.supported_value && <p className="text-sm text-content-secondary">PP1 target: {finding.supported_value}</p>}
                {finding.allowed_resolutions.includes('ADAPT_TO_SUPPORTED_STACK') && (
                  <Button className="mt-3" variant="outline" size="small" onClick={() => onAdapt(finding)} disabled={state.status === 'evaluating' || state.stale}>
                    Adapt to AgileFlow PP1 Stack
                  </Button>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}
      {result.findings.some((item) => item.resolved) && (
        <section aria-label="Human-approved resolutions">
          <h4 className="font-semibold text-content-primary">Human-approved Decisions</h4>
          {result.findings.filter((item) => item.resolved).map((item) => (
            <p key={item.finding_id} className="mt-2 text-sm text-state-success">Human decision recorded: use the AgileFlow PP1 supported stack for {item.category}.</p>
          ))}
        </section>
      )}
      <p className="text-sm text-content-secondary">This readiness review does not start an AgentRun or code generation.</p>
      {result.status === 'NOT_READY' && <Button variant="outline" onClick={onBack}>Back to Inputs</Button>}
    </Card>
  )
}

