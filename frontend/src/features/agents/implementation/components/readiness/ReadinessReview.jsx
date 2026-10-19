import Button from '../../../../../components/ui/Button.jsx'
import Card from '../../../../../components/ui/Card.jsx'
import ResearchDetails from '../common/ResearchDetails.jsx'

const labels = { READY: 'READY', READY_WITH_WARNINGS: 'READY WITH WARNINGS', NOT_READY: 'NOT READY' }
const outputStatusLabels = { READY: 'Ready', READY_WITH_WARNINGS: 'Ready with warnings', NOT_READY: 'Blocked' }
const outputLabels = {
  PROJECT_STRUCTURE: 'Project Structure', FRONTEND_CODE: 'Frontend Code', BACKEND_CODE: 'Backend Code',
  DATABASE_IMPLEMENTATION: 'Database Implementation', API_IMPLEMENTATION: 'API Implementation',
  CONFIGURATION_FILES: 'Configuration Files', CONTAINER_CONFIGURATION: 'Container Configuration', GIT_SUMMARY: 'Git Summary',
}
const title = (value) => value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase())

export default function ReadinessReview({ state, onAdapt, onBack }) {
  const result = state.result
  if (!result) return null
  const findings = result.findings ?? []
  const grouped = Object.fromEntries(['ERROR', 'WARNING', 'INFO'].map((severity) => [
    severity, findings.filter((item) => item.severity === severity && !item.resolved),
  ]))
  const coverage = Array.isArray(result.coverage) ? result.coverage : []
  return (
    <Card aria-labelledby="implementation-readiness-title" className="space-y-5">
      <div>
        <h3 id="implementation-readiness-title" className="text-card-heading font-semibold text-content-primary">Implementation Readiness</h3>
        <p className="mt-2 font-semibold text-content-primary">{labels[result.status]}</p>
        <p className="mt-1 text-sm text-content-secondary">{grouped.ERROR.length} blocking · {grouped.WARNING.length} warnings</p>
      </div>
      {state.stale && <p role="alert" className="text-sm text-state-warning">The trusted specification or selected outputs changed. This result is no longer current.</p>}

      <section aria-labelledby="selected-outputs-title">
        <h4 id="selected-outputs-title" className="font-semibold text-content-primary">Selected Outputs</h4>
        <ul className="mt-2 space-y-2 text-sm text-content-secondary">
          {(result.output_readiness ?? []).map((item) => (
            <li key={item.output} className="flex items-center justify-between gap-3">
              <span>{outputLabels[item.output] ?? title(item.output)}</span>
              <span className="font-medium text-content-primary">{outputStatusLabels[item.status] ?? (item.ready ? 'Ready' : 'Blocked')}</span>
            </li>
          ))}
        </ul>
      </section>

      {coverage.length > 0 && (
        <section aria-labelledby="coverage-title">
          <h4 id="coverage-title" className="font-semibold text-content-primary">Specification Coverage</h4>
          <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
            {coverage.map((item) => <div key={item.category}><dt className="inline font-medium text-content-primary">{title(item.category)}: </dt><dd className="inline text-content-secondary">{item.present ? 'Available' : 'Missing'}</dd></div>)}
          </dl>
        </section>
      )}

      <section aria-labelledby="technology-compatibility-title">
        <h4 id="technology-compatibility-title" className="font-semibold text-content-primary">Agent 3 PP1 Implementation Stack</h4>
        <ul className="mt-2 grid gap-1 text-sm text-content-secondary sm:grid-cols-2">
          {Object.values(result.effective_stack ?? {}).map((value) => <li key={value}>{value}</li>)}
        </ul>
      </section>

      {[
        ['ERROR', 'Blocking Issues'], ['WARNING', 'Warnings'], ['INFO', 'Information'],
      ].map(([severity, heading]) => grouped[severity].length > 0 && (
        <section key={severity} aria-label={heading}>
          <h4 className="font-semibold text-content-primary">{heading}</h4>
          <div className="mt-2 space-y-3">
            {grouped[severity].map((finding) => (
              <div key={finding.finding_id} className="rounded-control border border-default p-3">
                <p className="font-medium text-content-primary">{finding.title}</p>
                <p className="mt-1 text-sm text-content-secondary">{finding.message}</p>
                {finding.provided_value && <p className="mt-2 text-sm text-content-secondary">Requested: {finding.provided_value}</p>}
                {finding.supported_value && <p className="text-sm text-content-secondary">Agent 3 PP1: {finding.supported_value}</p>}
                {finding.resolution_action === 'ADAPT_TO_SUPPORTED_STACK' && (
                  <>
                    <p className="mt-2 text-sm text-content-secondary">This approval changes the implementation plan only. It does not modify the trusted source specification.</p>
                    <Button className="mt-3" variant="outline" size="small" onClick={() => onAdapt(finding)} disabled={state.status === 'evaluating' || state.stale}>Adapt to supported stack</Button>
                  </>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}

      {findings.some((item) => item.resolved) && <p className="text-sm text-state-success">Human-approved implementation adaptation recorded. The trusted project specification remains unchanged.</p>}
      {result.status === 'NOT_READY' && <Button variant="outline" onClick={onBack}>Review Specification</Button>}
      <p className="text-sm text-content-secondary">GitHub and repository configuration are evaluated later in Delivery Setup. This review does not start an AgentRun or code generation.</p>

      <ResearchDetails description="Inspect persisted policy identity and trusted-specification traceability references.">
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div><dt className="font-medium text-content-primary">Readiness ID</dt><dd className="break-all text-content-secondary">{result.readiness_id}</dd></div>
          <div><dt className="font-medium text-content-primary">Policy version</dt><dd className="text-content-secondary">{result.policy_version}</dd></div>
          <div><dt className="font-medium text-content-primary">Project specification ID</dt><dd className="break-all text-content-secondary">{result.project_specification_id ?? 'Not available'}</dd></div>
          <div><dt className="font-medium text-content-primary">Selected-output digest</dt><dd className="break-all text-content-secondary">{result.selected_outputs_digest}</dd></div>
        </dl>
        {findings.length > 0 && <p className="mt-3 break-words text-xs text-content-muted">Finding codes: {findings.map((item) => item.issue_code ?? item.code).join(', ')}</p>}
        {coverage.some((item) => item.project_item_ids?.length) && <p className="mt-2 break-words text-xs text-content-muted">Project items: {coverage.flatMap((item) => item.project_item_ids ?? []).join(', ')}</p>}
        {result.stack_adaptation?.fingerprint && <p className="mt-2 break-all text-xs text-content-muted">Stack adaptation fingerprint: {result.stack_adaptation.fingerprint}</p>}
      </ResearchDetails>
    </Card>
  )
}
