import { useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import NodeShellPanel from './NodeShellPanel.jsx'

const stageLabels = { TRACEABILITY: 'Traceability', TESTABILITY: 'Testability', FEASIBILITY: 'Feasibility', CONTEXT_DECISION: 'Context Decision' }

function words(value) {
  return value ? value.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) : 'Not available'
}

function FindingList({ title, items, tone = 'warning' }) {
  if (!items?.length) return null
  return <div className={`rounded-control border p-3 ${tone === 'danger' ? 'border-state-danger/40 bg-state-danger/10' : 'border-state-warning/40 bg-state-warning/10'}`}><h5 className="text-sm font-semibold text-content-primary">{title}</h5><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-content-secondary">{items.map((item) => <li key={item.finding_id}>{item.message}</li>)}</ul></div>
}

function ContextTestabilityPanel({ contextActionSubmitting, contextError, contextResult, definition, n4Execution, onAcknowledgeContextWarnings, onRetryContextAnalysis, statusLabel, workflowNodeStatus }) {
  const [note, setNote] = useState('')
  const status = n4Execution?.status ?? workflowNodeStatus
  const active = ['QUEUED', 'RUNNING'].includes(status)
  const waiting = status === 'WAITING_FOR_HUMAN'
  const blocked = status === 'BLOCKED'
  const failed = ['FAILED', 'INTERRUPTED'].includes(status)

  return (
    <NodeShellPanel definition={definition} availability={statusLabel} note={workflowNodeStatus === 'NOT_STARTED' ? 'Context & Testability is the next workflow node. Analysis has not started.' : 'Deterministic traceability, testability, feasibility, and context-decision evidence.'}>
      {contextError ? <p role="alert" className="text-sm text-state-danger">{contextError}</p> : null}
      {n4Execution ? <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold text-content-primary">Context &amp; Testability</h4><span className="text-sm text-content-secondary">Attempt {n4Execution.attempt_number} · {words(status)}</span></div>
        <ol className="grid gap-2 sm:grid-cols-2">{n4Execution.stages.map((stage) => <li key={stage.stage} className="rounded-control border border-default bg-elevated px-3 py-2"><span className="text-sm font-medium text-content-primary">{stageLabels[stage.stage]}</span><span className="ml-2 text-xs text-content-secondary">{words(stage.status)}</span></li>)}</ol>
        {active ? <p className="text-sm text-content-secondary">Analysis is running. This view refreshes automatically.</p> : null}
        {failed ? <div className="rounded-control border border-state-danger/40 bg-state-danger/10 p-4"><h4 className="font-semibold text-content-primary">Context analysis failed</h4><p className="mt-1 text-sm text-content-secondary">{n4Execution.error?.message || 'Context analysis was interrupted and can be retried safely.'}</p><Button className="mt-3" disabled={contextActionSubmitting} onClick={onRetryContextAnalysis}>{contextActionSubmitting ? 'Retrying…' : 'Retry Analysis'}</Button></div> : null}
      </div> : null}
      {contextResult ? <div className="mt-4 space-y-4">
        <div className={`rounded-control border p-4 ${blocked ? 'border-state-danger/40 bg-state-danger/10' : waiting ? 'border-state-warning/40 bg-state-warning/10' : 'border-default bg-elevated'}`}><h4 className="font-semibold text-content-primary">{blocked ? 'Test Planning Cannot Continue' : waiting ? 'Warnings Require Acknowledgement' : `Decision: ${words(contextResult.overall_decision)}`}</h4><p className="mt-1 text-sm text-content-secondary">{blocked ? 'Required planning context is missing for one or more selected outputs.' : waiting ? 'Review the documented limitations before continuing to test planning.' : 'Context analysis is complete.'}</p></div>
        <div className="space-y-3">{contextResult.outputs.map((output) => <article key={output.output_code} className="rounded-control border border-default bg-elevated p-4">
          <h4 className="font-semibold text-content-primary">{words(output.output_code)}</h4>
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">Testability</dt><dd className="font-medium text-content-primary">{words(output.testability_status)}</dd></div><div><dt className="text-content-muted">Generation</dt><dd className="font-medium text-content-primary">{words(output.feasibility_status)}</dd></div><div><dt className="text-content-muted">Representation</dt><dd className="font-medium text-content-primary">{words(output.recommended_representation)}</dd></div><div><dt className="text-content-muted">Decision</dt><dd className="font-medium text-content-primary">{words(output.decision)}</dd></div><div><dt className="text-content-muted">Planning</dt><dd className="font-medium text-content-primary">{output.planning_allowed ? 'Allowed' : 'Blocked'}</dd></div>{output.execution_status ? <div><dt className="text-content-muted">Execution</dt><dd className="font-medium text-content-primary">Not executed</dd></div> : null}</dl>
          {output.feasibility_status === 'SPECIFICATION_ONLY' && output.recommended_representation !== 'STRUCTURED_ARTIFACT' ? <p className="mt-3 text-sm text-content-secondary">Enough context exists to plan tests, but a trusted executable test toolchain was not provided.</p> : null}
          {output.recommended_representation === 'STRUCTURED_ARTIFACT' ? <p className="mt-3 text-sm text-content-secondary">This output is intentionally produced as a structured traceability artifact.</p> : null}
          <div className="mt-3 space-y-2"><FindingList title="Blockers" items={output.blockers} tone="danger" /><FindingList title="Warnings" items={output.warnings} /></div>
        </article>)}</div>
        {waiting ? <div className="rounded-control border border-state-warning/40 bg-state-warning/10 p-4"><label className="block text-sm font-medium text-content-primary" htmlFor="n4-warning-note">Optional acknowledgement note</label><textarea id="n4-warning-note" className="mt-2 min-h-20 w-full rounded-control border border-default bg-surface px-3 py-2 text-sm text-content-primary" maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} /><Button className="mt-3" disabled={contextActionSubmitting} onClick={() => onAcknowledgeContextWarnings(note)}>{contextActionSubmitting ? 'Submitting…' : 'Acknowledge & Continue'}</Button></div> : null}
      </div> : null}
    </NodeShellPanel>
  )
}

export default ContextTestabilityPanel
