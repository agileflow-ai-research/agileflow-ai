import ArtifactViewer from '../../../components/agents/ArtifactViewer.jsx'
import ResultsWorkspace from '../../../components/agents/ResultsWorkspace.jsx'

const labels = {
  UNIT_TEST_CASES: 'Unit Test Cases', API_TEST_CASES: 'API Test Cases',
  INTEGRATION_TEST_CASES: 'Integration Test Cases', FUNCTIONAL_TEST_CASES: 'Functional Test Cases',
  E2E_TEST_CASES: 'End-to-End Test Cases', REGRESSION_TEST_CASES: 'Regression Test Cases',
  SECURITY_TEST_CASES: 'Security Test Cases', ACCEPTANCE_TEST_CASES: 'Acceptance Test Cases',
  TEST_TRACEABILITY: 'Test Traceability', TEST_EXECUTION_REPORT: 'Test Execution Report',
  COVERAGE_REPORT: 'Coverage Report', BUG_REPORTS: 'Bug Reports',
  SECURITY_FINDINGS: 'Security Findings', CODE_QUALITY_REPORT: 'Code Quality Report',
  ACCEPTANCE_CRITERIA_VALIDATION: 'Acceptance Criteria Validation',
  FINAL_VALIDATION_REPORT: 'Final Validation Report',
}

function TestCases({ items }) {
  return <div className="space-y-3">{items.map((item) => (
    <article key={item.id} className="rounded-control border border-default bg-canvas p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="font-semibold text-content-primary">{item.title}</h4>
        <span className="font-mono text-xs text-content-muted">{item.id}</span>
      </div>
      <p className="mt-2 text-sm text-content-secondary">{item.purpose}</p>
      <p className="mt-2 text-xs font-semibold text-content-primary">
        {item.executable ? `Generated executable code · ${item.framework}` : 'Test specification · Not executable'}
      </p>
      <p className="mt-1 text-xs text-content-muted">Execution: {item.execution_status ?? 'NOT_EXECUTED'}</p>
      <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-content-secondary">
        {(item.steps ?? []).map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}
      </ol>
      <p className="mt-3 text-sm"><strong>Expected:</strong> {item.expected_result}</p>
      <p className="mt-2 text-xs text-content-muted">Sources: {(item.source_refs ?? []).join(', ')}</p>
      {item.code && <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-control bg-elevated p-3 text-xs">{item.code}</pre>}
    </article>
  ))}</div>
}

function Traceability({ items }) {
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="pb-2">Source</th><th className="pb-2">Type</th><th className="pb-2">Generated tests</th><th className="pb-2">Scope</th></tr></thead><tbody>{items.map((item, index) => <tr key={`${item.source_ref}-${index}`} className="border-t border-default"><td className="py-2">{item.source_ref}</td><td>{item.source_type}</td><td>{item.test_refs.join(', ')}</td><td>{item.scope}</td></tr>)}</tbody></table></div>
}

function StructuredReport({ value }) {
  return <pre className="overflow-x-auto whitespace-pre-wrap rounded-control bg-canvas p-3 text-xs text-content-secondary">{JSON.stringify(value, null, 2)}</pre>
}

function TestingValidationResults({ outputs, runMode, title, warnings = [], errors = [], actions }) {
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : {}
  const sections = Object.keys(labels).filter((code) => Object.hasOwn(safeOutputs, code)).map((code) => {
    const value = safeOutputs[code]
    let content = <StructuredReport value={value} />
    if (code.endsWith('_TEST_CASES')) content = <TestCases items={value} />
    if (code === 'TEST_TRACEABILITY') content = <Traceability items={value} />
    return {
      id: code, title: labels[code],
      content: <ArtifactViewer heading={labels[code]} metadata={runMode === 'TEST_GENERATION' ? 'Generated test artifact — not execution evidence' : 'Executed validation evidence or explicit skipped result'}>{content}</ArtifactViewer>,
    }
  })
  if (sections.length === 0) sections.push({ id: 'empty', title: 'No validated output', content: <p className="text-sm text-content-muted">This run produced no validated result artifact.</p> })
  return <ResultsWorkspace title={title ?? (runMode === 'TEST_GENERATION' ? 'Generated test results' : 'Testing and validation evidence')} sections={sections} warnings={warnings} errors={errors} actions={actions} />
}

export default TestingValidationResults
